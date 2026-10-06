"""Regras da página de configuração de IA: CRUD de perfis, vínculos e teste de conexão."""
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.config import get_settings
from app.integrations.ai.base import AIProviderError, ChatMessage, ChatRequest, ProviderConfig
from app.integrations.ai.policy import TAREFAS, PoliticaIAViolada, TarefaIA, verificar
from app.integrations.ai.registry import available_kinds, build_provider, provider_class
from app.modules.ia.models import PerfilProvedorIA, VinculoTarefaIA
from app.modules.ia.schemas import (
    PerfilIn, PerfilOut, TarefaOut, TesteConexaoIn, TesteConexaoOut, TipoProvedorOut, VinculoIn,
)


class ErroConfiguracaoIA(ValueError):
    pass


# ------------------------------------------------------------------ tipos
def listar_tipos() -> list[TipoProvedorOut]:
    return [
        TipoProvedorOut(
            tipo=c.kind, rotulo=c.label, descricao=c.description, url_padrao=c.default_base_url,
            exige_chave=c.requires_api_key, local_por_padrao=c.local_by_default,
            modelos_sugeridos=c.suggested_models, campos=c.fields(),
        )
        for c in available_kinds()
    ]


# ------------------------------------------------------------------ perfis
def to_out(p: PerfilProvedorIA) -> PerfilOut:
    return PerfilOut(
        id=p.id, nome=p.nome, tipo=p.tipo, modelo=p.modelo, base_url=p.base_url,
        tem_chave=bool(p.api_key_cifrada), api_key_dica=p.api_key_dica,
        execucao_local=p.execucao_local, temperatura=p.temperatura, max_tokens=p.max_tokens,
        timeout_s=p.timeout_s, ativo=p.ativo, atualizado_em=p.updated_at,
    )


def config_do_perfil(p: PerfilProvedorIA) -> ProviderConfig:
    return ProviderConfig(
        kind=p.tipo, model=p.modelo, base_url=p.base_url,
        api_key=crypto.decrypt(p.api_key_cifrada) if p.api_key_cifrada else None,
        timeout_s=p.timeout_s, temperature=p.temperatura, max_tokens=p.max_tokens, extra=p.extra,
    )


def salvar_perfil(db: Session, dados: PerfilIn, perfil: PerfilProvedorIA | None = None):
    cls = provider_class(dados.tipo)  # valida o tipo
    perfil = perfil or PerfilProvedorIA()
    perfil.nome, perfil.tipo, perfil.modelo = dados.nome.strip(), dados.tipo, dados.modelo.strip()
    perfil.base_url = (dados.base_url or "").strip() or None
    perfil.execucao_local = dados.execucao_local
    perfil.temperatura, perfil.max_tokens = dados.temperatura, dados.max_tokens
    perfil.timeout_s, perfil.ativo = dados.timeout_s, dados.ativo
    if dados.api_key is not None:
        chave = dados.api_key.strip()
        perfil.api_key_cifrada = crypto.encrypt(chave) if chave else None
        perfil.api_key_dica = crypto.hint(chave) if chave else None
    if cls.requires_api_key and not perfil.api_key_cifrada:
        raise ErroConfiguracaoIA(f"O provedor {cls.label} exige chave de API.")
    _validar_vinculos_do_perfil(db, perfil)
    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def _validar_vinculos_do_perfil(db: Session, perfil: PerfilProvedorIA) -> None:
    """Impede que editar um perfil (ex.: desmarcar 'local') quebre a política de uma tarefa."""
    if perfil.id is None:
        return
    permitir = get_settings().ia_permitir_externo_para_sensivel
    vinculos = db.scalars(select(VinculoTarefaIA).where(
        (VinculoTarefaIA.perfil_id == perfil.id) |
        (VinculoTarefaIA.perfil_fallback_id == perfil.id))).all()
    for v in vinculos:
        try:
            verificar(TarefaIA(v.tarefa), perfil.execucao_local, permitir)
        except PoliticaIAViolada as exc:
            raise ErroConfiguracaoIA(f"{exc} Troque o vínculo antes de alterar este perfil.")


# ------------------------------------------------------------------ teste de conexão
def testar(db: Session, dados: TesteConexaoIn) -> TesteConexaoOut:
    api_key = dados.api_key
    if not api_key and dados.perfil_id:
        salvo = db.get(PerfilProvedorIA, dados.perfil_id)
        if salvo and salvo.api_key_cifrada:
            api_key = crypto.decrypt(salvo.api_key_cifrada)
    cfg = ProviderConfig(kind=dados.tipo, model=dados.modelo, base_url=dados.base_url or None,
                         api_key=api_key or None, timeout_s=20)
    t0 = time.perf_counter()
    try:
        modelos = build_provider(cfg).list_models()
    except AIProviderError as exc:
        return TesteConexaoOut(ok=False, mensagem=str(exc))
    ms = int((time.perf_counter() - t0) * 1000)
    msg = f"Conexão estabelecida. {len(modelos)} modelo(s) disponível(is)."
    if dados.modelo not in ("teste", "") and modelos and dados.modelo not in modelos:
        msg += f" Atenção: '{dados.modelo}' não aparece na lista do provedor."
    return TesteConexaoOut(ok=True, mensagem=msg, latencia_ms=ms, modelos=modelos)


def testar_resposta(db: Session, perfil: PerfilProvedorIA) -> TesteConexaoOut:
    """Envia uma mensagem curta ao modelo configurado (teste ponta a ponta do perfil salvo)."""
    try:
        resp = build_provider(config_do_perfil(perfil)).chat(ChatRequest(
            messages=[ChatMessage(role="user", content="Responda apenas: OK")], max_tokens=16))
    except AIProviderError as exc:
        return TesteConexaoOut(ok=False, mensagem=str(exc))
    return TesteConexaoOut(ok=True, latencia_ms=resp.latency_ms,
                           mensagem=f"Modelo respondeu: {resp.text.strip()[:80]!r}")


# ------------------------------------------------------------------ tarefas / vínculos
def listar_tarefas(db: Session) -> list[TarefaOut]:
    permitir = get_settings().ia_permitir_externo_para_sensivel
    saida = []
    for tarefa, meta in TAREFAS.items():
        v = db.get(VinculoTarefaIA, tarefa.value)
        saida.append(TarefaOut(
            tarefa=tarefa, rotulo=meta.rotulo, descricao=meta.descricao, sensivel=meta.sensivel,
            user_story=meta.user_story, perfil_id=v.perfil_id if v else None,
            perfil_fallback_id=v.perfil_fallback_id if v else None,
            somente_local=meta.sensivel and not permitir,
        ))
    return saida


def vincular(db: Session, tarefa: TarefaIA, dados: VinculoIn, usuario: str) -> None:
    permitir = get_settings().ia_permitir_externo_para_sensivel
    for pid in (dados.perfil_id, dados.perfil_fallback_id):
        if pid is None:
            continue
        p = db.get(PerfilProvedorIA, pid)
        if p is None or not p.ativo:
            raise ErroConfiguracaoIA(f"Perfil {pid} inexistente ou inativo.")
        try:
            verificar(tarefa, p.execucao_local, permitir)
        except PoliticaIAViolada as exc:
            raise ErroConfiguracaoIA(str(exc)) from exc
    if dados.perfil_fallback_id and dados.perfil_fallback_id == dados.perfil_id:
        raise ErroConfiguracaoIA("O perfil de contingência deve ser diferente do principal.")
    v = db.get(VinculoTarefaIA, tarefa.value) or VinculoTarefaIA(tarefa=tarefa.value)
    v.perfil_id, v.perfil_fallback_id, v.alterado_por = (dados.perfil_id,
                                                        dados.perfil_fallback_id, usuario)
    db.add(v)
    db.commit()
