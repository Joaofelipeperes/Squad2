"""Anonimização de recursos com publicação no CKAN (US26, PBI-91 a PBI-94; ADR-0008).

Fluxo (sempre um recurso por vez):
  1. PRÉVIA — quem tem `lgpd.aprovar_correcao` escolhe, para cada achado CONFIRMADO do recurso, o
     operador e o alcance. Em segundo plano o sistema baixa o original, guarda a cópia de segurança
     fora do banco, aplica o motor do detector3 nas colunas escolhidas e grava a versão anonimizada
     (também fora do banco). A tela mostra quantas células mudam e exemplos já anonimizados.
  2. APROVAÇÃO — publica no CKAN exatamente o arquivo da prévia (`CkanWriter`, a única escrita do
     sistema). Antes, confere se o original no portal ainda é o mesmo da prévia (hash); se mudou,
     a prévia é descartada. Os achados viram "tratado", com registro de quem aprovou e quando.
  3. REVERSÃO — reenvia a cópia do original; os achados voltam a "confirmado".
  Descartar uma prévia apaga os arquivos dela (nada foi publicado).

Salvaguardas herdadas da ADR-0008: escrita desligada por padrão (`GDA_CKAN_WRITE_ENABLED`), só
recursos `upload` (link externo → acionar o órgão), token da GEDA. Nenhum valor encontrado vai
para o banco: os itens guardam só colunas, contagens e números de linha.
"""
import hashlib
import logging
import shutil
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual, exigir_mesmo_orgao
from app.integrations.ai.base import AIProviderError
from app.integrations.ckan.client import CkanClient, CkanError
from app.integrations.ckan.writer import CkanWriteDisabled, CkanWriter
from app.modules.ia.gateway import IANaoConfigurada
from app.modules.inventario.models import Dataset, Recurso
from app.modules.lgpd import anonimizacao, deteccao, leitura, regras
from app.modules.lgpd.dao import LgpdDao
from app.modules.lgpd.models import CorrecaoPublicada, DecisaoTriagem
from app.modules.lgpd.schemas import (
    CorrecaoIn,
    CorrecaoItemOut,
    CorrecaoOut,
    CorrecoesOut,
    ExemploOut,
    OpcaoOut,
)
from app.modules.lgpd.service import ErroLgpd, Invalido, NaoEncontrado, montar_motor
from app.modules.parametros.router import obter as obter_parametro

log = logging.getLogger(__name__)

# tipo do sistema → tipo do motor (para casar os trechos detectados com o achado)
TIPO_MOTOR = {codigo: motor for motor, (codigo, _r) in regras.TIPOS.items()}


class Conflito(ErroLgpd):
    pass


# ------------------------------------------------------------------ arquivos (fora do banco)
def _pasta(correcao_id: int) -> Path:
    return Path(get_settings().lgpd_arquivos_dir) / f"correcao_{correcao_id:06d}"


def _gravar(caminho: Path, conteudo: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    caminho.write_bytes(conteudo)
    caminho.chmod(0o600)


def _apagar_arquivos(c: CorrecaoPublicada) -> None:
    shutil.rmtree(_pasta(c.id), ignore_errors=True)
    c.caminho_previa = None
    c.caminho_backup = None


def _nome_arquivo(r: Recurso) -> str:
    nome = (r.url or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return nome or (r.nome or f"recurso_{r.id}.csv")


def _sal() -> str:
    s = get_settings()
    return (s.lgpd_sal_hash or s.secret_key).get_secret_value()


def escrita_habilitada() -> bool:
    s = get_settings()
    return bool(s.ckan_write_enabled and s.ckan_write_api_token)


# ------------------------------------------------------------------ consulta
def _exemplos(c: CorrecaoPublicada) -> dict[int, list[ExemploOut]]:
    """Valores já anonimizados das linhas de exemplo, lidos do arquivo da prévia (só em memória)."""
    if not c.caminho_previa or not Path(c.caminho_previa).exists():
        return {}
    alvo: dict[tuple[str, int], dict[int, int]] = {}  # (tabela, i) → {linha: achado_id}
    for it in c.itens:
        if it.get("indice") is not None:
            for n in it.get("linhas_exemplo", []):
                alvo.setdefault((it["tabela"], it["indice"]), {})[n] = it["achado_id"]
    saida: dict[int, list[ExemploOut]] = {}
    try:
        tabelas = leitura.ler(Path(c.caminho_previa).read_bytes(), c.formato)
    except (leitura.ArquivoInvalido, leitura.FormatoNaoSuportado):
        return {}
    for tab in tabelas:
        colunas = {i: m for (t, i), m in alvo.items() if t == tab.nome}
        if not colunas:
            continue
        for bloco in tab.blocos:
            for n, valores in bloco:
                for i, linhas in colunas.items():
                    if n in linhas and i < len(valores):
                        saida.setdefault(linhas[n], []).append(ExemploOut(linha=n, valor=valores[i]))
    return saida


def _out(c: CorrecaoPublicada, r: Recurso | None, ds: Dataset | None,
         com_exemplos: bool = False) -> CorrecaoOut:
    exemplos = _exemplos(c) if com_exemplos and c.status == "previa" else {}
    itens = [CorrecaoItemOut(
        achado_id=it["achado_id"], tipo=it["tipo"], tipo_rotulo=regras.rotulo_tipo(it["tipo"]),
        coluna=it["coluna"], operador=it["operador"],
        operador_rotulo=anonimizacao.OPERADORES.get(it["operador"], it["operador"]),
        alcance=it["alcance"], ocorrencias=it.get("ocorrencias", 0),
        alteradas=it.get("alteradas", 0), aviso=it.get("aviso"),
        exemplos=exemplos.get(it["achado_id"], [])) for it in c.itens or []]
    return CorrecaoOut(
        id=c.id, recurso_id=c.recurso_id, recurso_nome=r.nome if r else None,
        dataset_titulo=ds.titulo.strip() if ds else None, recurso_url_type=r.url_type if r else None,
        status=c.status, solicitada_por=c.solicitada_por, solicitada_em=c.created,
        celulas_alteradas=c.celulas_alteradas, nome_arquivo=c.nome_arquivo,
        aprovado_por=c.aprovado_por, aprovado_em=c.aprovado_em, justificativa=c.justificativa,
        publicada_em=c.publicada_em, revertida_por=c.revertida_por, revertida_em=c.revertida_em,
        motivo_reversao=c.motivo_reversao, erro=c.erro, itens=itens)


def listar(db: Session, user: UsuarioAtual, limite: int = 30) -> CorrecoesOut:
    linhas = LgpdDao.de(db, user).correcoes(user, min(limite, 200))
    return CorrecoesOut(
        escrita_habilitada=escrita_habilitada(),
        operadores=[OpcaoOut(valor=k, rotulo=v) for k, v in anonimizacao.OPERADORES.items()],
        alcances=[OpcaoOut(valor=k, rotulo=v) for k, v in anonimizacao.ALCANCES.items()],
        correcoes=[_out(c, r, ds) for c, r, ds in linhas])


def _obter(db: Session, correcao_id: int, user: UsuarioAtual):
    linha = LgpdDao.de(db, user).correcao_visivel(correcao_id, user)
    if linha is None:
        raise NaoEncontrado("Correção não encontrada.")
    return linha


def obter(db: Session, correcao_id: int, user: UsuarioAtual) -> CorrecaoOut:
    c, r, ds = _obter(db, correcao_id, user)
    return _out(c, r, ds, com_exemplos=True)


def arquivo_previa(db: Session, correcao_id: int, user: UsuarioAtual) -> tuple[Path, str]:
    """Arquivo anonimizado da prévia, para conferência completa antes de aprovar."""
    c, _r, ds = _obter(db, correcao_id, user)
    exigir_mesmo_orgao(user, ds.organizacao_id)
    if c.status != "previa" or not c.caminho_previa or not Path(c.caminho_previa).exists():
        raise Conflito("Só a prévia pronta pode ser baixada.")
    return Path(c.caminho_previa), c.nome_arquivo or Path(c.caminho_previa).name


# ------------------------------------------------------------------ 1. prévia
def solicitar_previa(db: Session, dados: CorrecaoIn, user: UsuarioAtual) -> CorrecaoPublicada:
    """Valida o pedido e cria a correção `gerando_previa` (o arquivo é gerado em segundo plano)."""
    dao = LgpdDao.de(db, user)
    par = dao.recurso_e_dataset(dados.recurso_id, user)
    r, ds = par if par else (None, None)
    if r is None or ds is None:
        raise NaoEncontrado("Recurso não encontrado.")
    exigir_mesmo_orgao(user, ds.organizacao_id)
    if r.url_type != "upload":
        raise Invalido("O arquivo deste recurso está hospedado fora do portal (link externo): o "
                       "sistema não pode substituí-lo. Acione o órgão responsável.")
    formato = leitura.formato_do_recurso(r.formato, r.nome or r.url)
    if formato not in leitura.FORMATOS_SUPORTADOS:
        raise Invalido(f"Formato {formato or 'desconhecido'} ainda não pode ser anonimizado.")
    if dao.correcao_aberta(r.id):
        raise Conflito("Já existe uma correção aberta para este recurso: publique ou descarte "
                       "a prévia antes de gerar outra.")
    achados = dao.achados_por_id([i.achado_id for i in dados.itens])
    itens = []
    for i in dados.itens:
        a = achados.get(i.achado_id)
        if a is None or a.recurso_id != r.id:
            raise Invalido(f"O achado {i.achado_id} não é deste recurso.")
        if a.status != "confirmado":
            raise Invalido(f"O achado {i.achado_id} ({regras.rotulo_tipo(a.tipo)} em "
                           f"“{a.coluna}”) precisa estar confirmado para ser anonimizado.")
        if a.tipo not in TIPO_MOTOR:
            raise Invalido(f"Tipo {a.tipo} sem detector para anonimizar.")
        itens.append({"achado_id": a.id, "tipo": a.tipo, "coluna": a.coluna,
                      "operador": i.operador, "alcance": i.alcance,
                      "ocorrencias": a.ocorrencias, "alteradas": 0, "linhas_exemplo": []})
    if len({(it["coluna"], it["tipo"]) for it in itens}) != len(itens):
        raise Invalido("O mesmo achado foi informado duas vezes.")
    c = CorrecaoPublicada(recurso_id=r.id, status="gerando_previa", formato=formato,
                          solicitada_por=user.email, itens=itens, nome_arquivo=_nome_arquivo(r))
    dao.save_generic(c)
    dao.commit()
    return c


def gerar_previa(db: Session, c: CorrecaoPublicada, client: CkanClient | None = None) -> None:
    """Baixa o original, guarda a cópia, aplica os operadores e grava a versão anonimizada.
    Nunca levanta: erro fica registrado na correção (e os arquivos são apagados)."""
    dao = LgpdDao(db)
    r = dao.recurso(c.recurso_id)
    ds = dao.dataset(r.dataset_id)
    proprio = client is None
    client = client or CkanClient()
    try:
        url = client.url_download(r.id_ckan, ds.id_ckan if ds else None, r.url, r.url_type)
        limite = int(obter_parametro(db, "tamanho_maximo_recurso_lgpd_mb")) * 1024 * 1024
        original = client.baixar(url, limite)
        pasta = _pasta(c.id)
        backup, previa = pasta / "original" / c.nome_arquivo, pasta / "anonimizado" / c.nome_arquivo
        _gravar(backup, original)
        c.caminho_backup, c.hash_original = str(backup), hashlib.sha256(original).hexdigest()

        itens = [dict(it) for it in c.itens]
        planos: dict[tuple[str, int], list[anonimizacao.ItemPlano]] = {}
        tabelas = leitura.ler(original, c.formato)
        nomes = {regras.nome_da_coluna(t.nome, col): (t.nome, i)
                 for t in tabelas for i, col in enumerate(t.colunas)}
        for it in itens:
            pos = nomes.get(it["coluna"])
            if pos is None:
                it["aviso"] = "Coluna não encontrada no arquivo atual (o recurso mudou?)."
                continue
            it["tabela"], it["indice"] = pos
            planos.setdefault(pos, []).append(anonimizacao.ItemPlano(
                chave=str(it["achado_id"]), tabela=pos[0], indice_coluna=pos[1], tipo=it["tipo"],
                tipo_motor=TIPO_MOTOR[it["tipo"]], operador=it["operador"], alcance=it["alcance"]))
        motor = (montar_motor(db) if any(p.alcance == "detectados" for ps in planos.values()
                                         for p in ps) else None)
        cache: dict = {}
        alteracoes = anonimizacao.Alteracoes()
        for tab in tabelas:
            colunas = {i: ps for (t, i), ps in planos.items() if t == tab.nome}
            if not colunas:
                continue

            def analisar(valores, i, tab=tab):
                nome = regras.nome_da_coluna(tab.nome, tab.colunas[i])
                return deteccao.analisar_coluna(motor.analisador, valores, cache=cache,
                                                chave_coluna=nome)

            anonimizacao.planejar(colunas, tab.blocos, analisar, _sal(), alteracoes, tab.nome)
        por_id = {p.chave: p for ps in planos.values() for p in ps}
        for it in itens:
            p = por_id.get(str(it["achado_id"]))
            if p is not None:
                it["alteradas"], it["linhas_exemplo"] = p.alteradas, p.linhas_exemplo
                if p.alteradas == 0 and not it.get("aviso"):
                    it["aviso"] = ("Nenhuma célula encontrada agora para este achado; com alcance "
                                   "'só os trechos detectados', tente 'a célula inteira'.")
        c.itens = itens
        if not len(alteracoes):
            raise Invalido("Nada a anonimizar: nenhuma célula seria alterada.")
        _gravar(previa, anonimizacao.reescrever(original, c.formato, alteracoes))
        c.caminho_previa, c.celulas_alteradas = str(previa), len(alteracoes)
        c.status, c.erro = "previa", None
        dao.save_generic(c)
        dao.commit()
    except (CkanError, leitura.ArquivoInvalido, leitura.FormatoNaoSuportado, Invalido) as exc:
        _falhar(dao, c, str(exc))
    except (AIProviderError, IANaoConfigurada) as exc:
        _falhar(dao, c, f"Modelo local indisponível para reencontrar os trechos: {exc}")
    except Exception as exc:
        log.exception("Prévia da correção %s falhou", c.id)
        _falhar(dao, c, f"Erro inesperado: {type(exc).__name__}: {exc}")
    finally:
        if proprio:
            client.close()


def _falhar(dao: LgpdDao, c: CorrecaoPublicada, mensagem: str) -> None:
    dao.rollback()
    _apagar_arquivos(c)
    c.status, c.erro = "erro", mensagem[:2000]
    dao.save_generic(c)
    dao.commit()


def executar_previa(correcao_id: int) -> None:
    with SessionLocal() as db:
        c = LgpdDao(db).correcao(correcao_id)
        if c is not None and c.status == "gerando_previa":
            gerar_previa(db, c)


# ------------------------------------------------------------------ 2. aprovação e publicação
def _decidir_achados(dao: LgpdDao, c: CorrecaoPublicada, status: str, usuario: str, texto: str):
    achados = dao.achados_por_id([it["achado_id"] for it in c.itens if it.get("alteradas")])
    for a in achados.values():
        a.status = status
        dao.save_generic(a, DecisaoTriagem(achado_id=a.id, decisao=status,
                                           justificativa=texto[:1000], usuario=usuario,
                                           momento=utcnow()))


def _writer() -> CkanWriter:
    return CkanWriter()


def aprovar(db: Session, correcao_id: int, justificativa: str | None, user: UsuarioAtual,
            client: CkanClient | None = None) -> CorrecaoOut:
    """PBI-92/93 — publica no CKAN o arquivo da prévia, se o original não mudou desde então."""
    c, r, ds = _obter(db, correcao_id, user)
    dao = LgpdDao.de(db, user)
    exigir_mesmo_orgao(user, ds.organizacao_id)
    if c.status != "previa":
        raise Conflito("Só uma prévia pronta pode ser aprovada.")
    try:
        writer = _writer()
    except CkanWriteDisabled as exc:
        raise Conflito(f"{exc} A prévia continua disponível.") from exc
    proprio = client is None
    client = client or CkanClient()
    try:
        atual = client.baixar(client.url_download(r.id_ckan, ds.id_ckan, r.url, r.url_type),
                              int(obter_parametro(db, "tamanho_maximo_recurso_lgpd_mb")) * 1048576)
    except CkanError as exc:
        raise Conflito(f"Não foi possível conferir o arquivo atual no portal: {exc}") from exc
    finally:
        if proprio:
            client.close()
    if hashlib.sha256(atual).hexdigest() != c.hash_original:
        _apagar_arquivos(c)
        c.status, c.erro = "descartada", ("O arquivo mudou no portal depois da prévia; ela foi "
                                          "descartada. Gere outra.")
        dao.save_generic(c)
        dao.commit()
        raise Conflito(c.erro)
    c.status, c.aprovado_por, c.aprovado_em = "publicando", user.email, utcnow()
    c.justificativa = (justificativa or "").strip() or None
    dao.save_generic(c)
    dao.commit()
    try:
        writer.replace_resource_file(r.id_ckan, Path(c.caminho_previa), note=(
            f"Anonimização LGPD aprovada por {user.email} (correção #{c.id})"))
    except (httpx.HTTPError, RuntimeError, OSError) as exc:
        c.status, c.erro = "previa", f"Falha ao publicar no CKAN (nada foi alterado): {exc}"[:2000]
        c.aprovado_por = c.aprovado_em = None
        dao.save_generic(c)
        dao.commit()
        raise Conflito(c.erro) from exc
    c.status, c.publicada_em, c.erro = "publicada", utcnow(), None
    dao.save_generic(c)
    _decidir_achados(dao, c, "tratado", user.email,
                     f"Anonimização publicada no CKAN (correção #{c.id})"
                     + (f": {c.justificativa}" if c.justificativa else ""))
    dao.commit()
    return _out(c, r, ds)


def descartar(db: Session, correcao_id: int, user: UsuarioAtual) -> CorrecaoOut:
    c, r, ds = _obter(db, correcao_id, user)
    exigir_mesmo_orgao(user, ds.organizacao_id)
    if c.status not in ("previa", "erro", "gerando_previa"):
        raise Conflito("Correção publicada não pode ser descartada; use a reversão.")
    _apagar_arquivos(c)
    c.status = "descartada"
    dao = LgpdDao.de(db, user)
    dao.save_generic(c)
    dao.commit()
    return _out(c, r, ds)


# ------------------------------------------------------------------ 3. reversão
def reverter(db: Session, correcao_id: int, motivo: str, user: UsuarioAtual) -> CorrecaoOut:
    """PBI-94 — reenvia a cópia do original; os achados voltam a "confirmado"."""
    c, r, ds = _obter(db, correcao_id, user)
    exigir_mesmo_orgao(user, ds.organizacao_id)
    if c.status != "publicada":
        raise Conflito("Só uma correção publicada pode ser revertida.")
    if not c.caminho_backup or not Path(c.caminho_backup).exists():
        raise Conflito("A cópia do original não está mais disponível (política de retenção).")
    try:
        writer = _writer()
    except CkanWriteDisabled as exc:
        raise Conflito(str(exc)) from exc
    dao = LgpdDao.de(db, user)
    c.status = "revertendo"
    dao.save_generic(c)
    dao.commit()
    try:
        writer.replace_resource_file(r.id_ckan, Path(c.caminho_backup), note=(
            f"Reversão da anonimização LGPD por {user.email} (correção #{c.id})"))
    except (httpx.HTTPError, RuntimeError, OSError) as exc:
        c.status, c.erro = "publicada", f"Falha ao reverter no CKAN: {exc}"[:2000]
        dao.save_generic(c)
        dao.commit()
        raise Conflito(c.erro) from exc
    c.status, c.revertida_por, c.revertida_em = "revertida", user.email, utcnow()
    c.motivo_reversao, c.erro = motivo.strip(), None
    dao.save_generic(c)
    _decidir_achados(dao, c, "confirmado", user.email,
                     f"Anonimização revertida (correção #{c.id}): {c.motivo_reversao}")
    dao.commit()
    return _out(c, r, ds)
