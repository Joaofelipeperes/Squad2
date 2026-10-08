"""Monitoramento do PDA — responsável: Humberto (Eixo 1).

- PBI-12: importação da planilha do PDA e vínculo das bases com o CKAN;
- PBI-13: vínculo SEMPRE pelo ID do dataset (o `name` da planilha só serve para achar o ID);
- PBI-15: dataset vinculado que sumiu do portal (excluído/privado) volta a "não publicado";
- PBI-19: situação de cada base quanto ao prazo de abertura;
- PBI-20/21: lista e filtros da tela; PBI-22: janela de alerta (parâmetro da GEDA).

Vários PDAs podem estar cadastrados; o VIGENTE rege a tela e os indicadores de gestão (decisão de
07/10/2026, Humberto — pendente de validação da GEDA). Para outros módulos (painel, relatorios,
assistente): `plano_vigente(db)` e `bases_do_plano(db, plano_id, user)`.
"""
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.atualizacoes.service import ultima_atualizacao_real
from app.modules.inventario.models import Dataset, Organizacao
from app.modules.inventario.service import recursos_atuais
from app.modules.parametros.router import obter as obter_parametro
from app.modules.pda import regras
from app.modules.pda.models import BasePrevista, PlanoPda
from app.modules.pda.schemas import (
    BaseOut,
    BasesOut,
    ImportacaoResumoOut,
    LinhaIgnoradaOut,
    OpcaoOut,
    OpcoesOut,
    PlanoOut,
)

_LOTE_IN = 500  # tamanho do lote em consultas IN (limite de parâmetros do SQLite/PostgreSQL)


# ------------------------------------------------------------------ erros de domínio
class ErroPda(Exception):
    status_http = 400


class NaoEncontrado(ErroPda):
    status_http = 404


class Conflito(ErroPda):
    status_http = 409


class Invalido(ErroPda):
    status_http = 422


_MSG_CONFLITO = ("Conflito ao gravar o PDA (nome repetido ou outro PDA definido como vigente ao "
                 "mesmo tempo). Atualize a tela e tente novamente.")


@contextmanager
def _transacao(db: Session) -> Iterator[None]:
    """Executa a gravação e o commit. Violação de índice único em QUALQUER etapa (no PostgreSQL
    ela ocorre no flush do INSERT/UPDATE, não no commit) → 409; qualquer erro → rollback."""
    try:
        yield
        db.commit()
    except IntegrityError as exc:  # corrida: mesmo nome ou dois vigentes em paralelo
        db.rollback()
        raise Conflito(_MSG_CONFLITO) from exc
    except Exception:
        db.rollback()
        raise


# ------------------------------------------------------------------ contexto de cálculo
def hoje_local() -> date:
    """Data de hoje no fuso da aplicação (America/Sao_Paulo)."""
    try:
        fuso = ZoneInfo(get_settings().timezone)
    except ZoneInfoNotFoundError:  # SO sem base de fusos: Brasília é UTC-3 fixo desde 2019
        fuso = timezone(timedelta(hours=-3))
    return datetime.now(fuso).date()


def janela_alerta_dias(db: Session) -> int:
    """PBI-22 — parâmetro `janela_alerta_prazo_dias` editável pela GEDA."""
    return int(obter_parametro(db, "janela_alerta_prazo_dias"))


# ------------------------------------------------------------------ planos
def plano_vigente(db: Session) -> PlanoPda | None:
    """PDA vigente — rege a tela e os indicadores/relatórios de gestão das bases."""
    return db.scalar(select(PlanoPda).where(PlanoPda.vigente.is_(True)).limit(1))


def _plano_ou_404(db: Session, plano_id: int) -> PlanoPda:
    plano = db.get(PlanoPda, plano_id)
    if plano is None:
        raise NaoEncontrado("PDA não encontrado.")
    return plano


@dataclass(frozen=True)
class _Contagens:
    bases: int = 0       # bases visíveis ao usuário (todas, sem escopo de órgão)
    resolvidos: int = 0  # vínculos resolvidos
    pendentes: int = 0   # vínculos pendentes


def _contagens(db: Session, user: UsuarioAtual | None = None,
               plano_ids: list[int] | None = None) -> dict[int, _Contagens]:
    """plano_id → contagens das bases. Com `user`, aplica o escopo de órgão (usuário restrito só
    conta as bases do próprio órgão, como em `GET /bases`)."""
    pendente = and_(BasePrevista.dataset_id.is_(None),
                    BasePrevista.dataset_name_planilha.is_not(None))
    stmt = (select(BasePrevista.plano_id, func.count(BasePrevista.id),
                   func.count(BasePrevista.dataset_id),
                   func.coalesce(func.sum(case((pendente, 1), else_=0)), 0))
            .group_by(BasePrevista.plano_id))
    if user is not None:
        stmt = filtrar_por_orgao(stmt, BasePrevista.organizacao_id, user)
    if plano_ids is not None:
        stmt = stmt.where(BasePrevista.plano_id.in_(plano_ids))
    return {pid: _Contagens(int(n), int(res), int(pend))
            for pid, n, res, pend in db.execute(stmt)}


def _utc(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


def plano_out(plano: PlanoPda, contagens: _Contagens | None = None, *,
              restrito: bool = False) -> PlanoOut:
    """`restrito=True` (usuário restrito a órgão): `total_bases` passa a ser o total de bases do
    órgão dele (`contagens.bases`), coerente com `total_previstas` de `GET /bases`."""
    c = contagens or _Contagens()
    return PlanoOut(
        id=plano.id, nome=plano.nome, vigencia_inicio=plano.vigencia_inicio,
        vigencia_fim=plano.vigencia_fim, vigente=plano.vigente, arquivo_nome=plano.arquivo_nome,
        importado_por=plano.importado_por, importado_em=_utc(plano.importado_em),
        total_bases=c.bases if restrito else plano.total_bases,
        vinculos_resolvidos=c.resolvidos, vinculos_pendentes=c.pendentes)


def _restrito(user: UsuarioAtual | None) -> bool:
    return user is not None and user.restrito_a_orgao


def _plano_out_db(db: Session, plano: PlanoPda, user: UsuarioAtual | None = None) -> PlanoOut:
    return plano_out(plano, _contagens(db, user, [plano.id]).get(plano.id),
                     restrito=_restrito(user))


def listar_planos(db: Session, user: UsuarioAtual | None = None) -> list[PlanoOut]:
    """PDAs cadastrados: vigente primeiro, depois os importados mais recentemente. Totais e
    vínculos respeitam o escopo de órgão do `user`."""
    planos = db.scalars(select(PlanoPda).order_by(
        PlanoPda.vigente.desc(), PlanoPda.importado_em.desc(), PlanoPda.id.desc())).all()
    contagens = _contagens(db, user)
    return [plano_out(p, contagens.get(p.id), restrito=_restrito(user)) for p in planos]


def _tornar_unico_vigente(db: Session, plano: PlanoPda) -> None:
    """Desmarca todos e marca o escolhido, nessa ordem (o índice único parcial
    `uq_pda_plano_vigente` recusaria dois vigentes ao mesmo tempo)."""
    db.execute(update(PlanoPda).where(PlanoPda.vigente.is_(True)).values(vigente=False))
    plano.vigente = True
    db.flush()


def definir_vigente(db: Session, plano_id: int) -> PlanoOut:
    """Escolhe o PDA vigente (há no máximo um). Troca concorrente → 409."""
    plano = _plano_ou_404(db, plano_id)
    if not plano.vigente:
        with _transacao(db):
            _tornar_unico_vigente(db, plano)
    return _plano_out_db(db, plano)


def excluir_plano(db: Session, plano_id: int) -> None:
    """Exclui um PDA não vigente e suas bases (o vigente não pode ser excluído)."""
    plano = _plano_ou_404(db, plano_id)
    if plano.vigente:
        raise Conflito("O PDA vigente não pode ser excluído. Defina outro PDA como vigente antes.")
    # Exclusão explícita das bases: o SQLite só aplica ON DELETE CASCADE com PRAGMA foreign_keys
    db.execute(delete(BasePrevista).where(BasePrevista.plano_id == plano.id))
    db.delete(plano)
    db.commit()


# ------------------------------------------------------------------ importação (PBI-12/13)
def _corte(valor: str | None, tamanho: int) -> str | None:
    return valor[:tamanho] if valor else valor


def _nome_em_uso(db: Session, nome: str) -> bool:
    """Checagem prévia, só para a mensagem amigável; quem garante a unicidade sem diferenciar
    maiúsculas é o índice `uq_pda_plano_nome_ci` (lower(nome))."""
    return db.scalar(select(func.count()).select_from(PlanoPda)
                     .where(func.lower(PlanoPda.nome) == nome.lower())) > 0 or \
        nome.casefold() in {n.casefold() for n in db.scalars(select(PlanoPda.nome))}


def _datasets_por_name(db: Session, names: set[str]) -> dict[str, Dataset]:
    """name → Dataset do inventário, usado SÓ para descobrir o ID (PBI-13). Se o inventário tiver
    mais de um dataset com o mesmo name (ex.: excluído e recriado), prefere o ativo no portal;
    persistindo a ambiguidade, não resolve."""
    encontrados: dict[str, list[Dataset]] = {}
    lista = sorted(names)
    for i in range(0, len(lista), _LOTE_IN):
        for ds in db.scalars(select(Dataset).where(Dataset.name.in_(lista[i:i + _LOTE_IN]))):
            encontrados.setdefault(ds.name, []).append(ds)
    resultado: dict[str, Dataset] = {}
    for name, candidatos in encontrados.items():
        ativos = [d for d in candidatos if d.ativo_no_portal] or candidatos
        if len(ativos) == 1:
            resultado[name] = ativos[0]
    return resultado


def importar_plano(db: Session, *, nome: str, vigencia_inicio: date | None,
                   vigencia_fim: date | None, definir_vigente: bool, arquivo_nome: str,
                   conteudo: bytes, importado_por: str | None) -> ImportacaoResumoOut:
    """PBI-12/13 — importa a planilha de um PDA (atômico: qualquer erro → nada gravado).

    Vínculo: name extraído da URL "Disponível no Portal" → `Dataset.ckan_id` do inventário
    ("resolvido"); name sem dataset no inventário → "pendente" (resolver depois com
    `resolver_vinculos_pendentes`); sem URL → "sem_vinculo". Órgão da base: o do dataset
    vinculado; sem vínculo, o das bases da MESMA sigla vinculadas por ID neste PDA (se todas
    apontarem para uma só organização); por fim, `regras.casar_orgao`. O primeiro PDA cadastrado
    vira vigente mesmo sem `definir_vigente`. O arquivo bruto não é gravado.
    """
    nome = re.sub(r"\s+", " ", nome or "").strip()
    if not nome:
        raise Invalido("Informe o nome do PDA.")
    if len(nome) > 200:
        raise Invalido("O nome do PDA deve ter no máximo 200 caracteres.")
    if vigencia_inicio and vigencia_fim and vigencia_fim < vigencia_inicio:
        raise Invalido("O fim da vigência não pode ser anterior ao início.")
    if _nome_em_uso(db, nome):
        raise Conflito(f'Já existe um PDA chamado "{nome}".')
    try:
        lida = regras.ler_planilha(conteudo, arquivo_nome)
    except regras.PlanilhaInvalida as exc:
        raise Invalido(str(exc)) from exc
    if not lida.linhas:
        raise Invalido("Nenhuma base prevista encontrada na planilha (verifique se as colunas "
                       '"Órgão" e "Base de Dados" estão preenchidas).')

    with _transacao(db):
        names = [regras.extrair_name_da_url(ln.disponivel_no_portal) for ln in lida.linhas]
        datasets = _datasets_por_name(db, {n for n in names if n})
        vinculados = [datasets.get(n) if n else None for n in names]
        org_por_evidencia = regras.orgao_por_evidencia(
            (ln.orgao_sigla, ds.organizacao_id)
            for ln, ds in zip(lida.linhas, vinculados, strict=True) if ds is not None)
        orgaos = [(o.ckan_id, o.name, o.titulo, o.sigla)
                  for o in db.scalars(select(Organizacao)).all()]
        orgao_por_sigla: dict[str, str | None] = {}
        sem_correspondencia: set[str] = set()
        resolvidos = pendentes = sem_vinculo = 0

        primeiro_pda = db.scalar(select(func.count()).select_from(PlanoPda)) == 0
        plano = PlanoPda(nome=nome, vigencia_inicio=vigencia_inicio, vigencia_fim=vigencia_fim,
                         vigente=False, arquivo_nome=_corte(arquivo_nome, 300),
                         importado_por=_corte(importado_por, 200), importado_em=utcnow(),
                         total_bases=len(lida.linhas))
        for ln, name, ds in zip(lida.linhas, names, vinculados, strict=True):
            if ds is not None:
                resolvidos += 1
            elif name:
                pendentes += 1
            else:
                sem_vinculo += 1
            # 1) base vinculada: o órgão do dataset prevalece sobre a heurística pela sigla
            organizacao_id = ds.organizacao_id if ds is not None else None
            # 2) evidência por ID: outras bases da mesma sigla vinculadas a UMA organização
            if organizacao_id is None:
                organizacao_id = org_por_evidencia.get(regras.chave_sigla(ln.orgao_sigla))
            # 3) heurística pela sigla (nunca chuta)
            if organizacao_id is None:
                if ln.orgao_sigla not in orgao_por_sigla:
                    orgao_por_sigla[ln.orgao_sigla] = regras.casar_orgao(ln.orgao_sigla, orgaos)
                organizacao_id = orgao_por_sigla[ln.orgao_sigla]
            if organizacao_id is None:
                sem_correspondencia.add(ln.orgao_sigla)
            plano.bases.append(BasePrevista(
                orgao_sigla=_corte(ln.orgao_sigla, 100), organizacao_id=organizacao_id,
                nome_previsto=_corte(ln.nome_previsto, 500), descricao=ln.descricao,
                unidade_responsavel=_corte(ln.unidade_responsavel, 500),
                prazo_abertura=ln.prazo,
                periodicidade=regras.normalizar_periodicidade(ln.periodicidade_original),
                periodicidade_original=_corte(ln.periodicidade_original, 100),
                politicas_publicas=_corte(ln.politicas_publicas, 500),
                possui_conteudo_sigiloso=ln.possui_conteudo_sigiloso,
                dataset_id=ds.ckan_id if ds is not None else None,
                dataset_name_planilha=_corte(name, 200), linha_planilha=ln.linha,
                classificacao="pda"))

        if definir_vigente or primeiro_pda:
            _tornar_unico_vigente(db, plano)
        db.add(plano)
        db.flush()

    return ImportacaoResumoOut(
        plano=plano_out(plano, _Contagens(len(lida.linhas), resolvidos, pendentes)),
        bases_importadas=len(lida.linhas),
        linhas_ignoradas=[LinhaIgnoradaOut(linha=n, motivo=m) for n, m in lida.ignoradas],
        vinculos_resolvidos=resolvidos, vinculos_pendentes=pendentes, sem_vinculo=sem_vinculo,
        orgaos_sem_correspondencia=sorted(sem_correspondencia, key=regras.normalizar_texto),
        tem_coluna_prazo=lida.tem_coluna_prazo,
        tem_coluna_portal=lida.tem_coluna_portal,
        colunas_opcionais_ausentes=lida.colunas_opcionais_ausentes)


def _completar_orgao_por_evidencia(db: Session, plano_id: int) -> int:
    """Bases do plano SEM organização herdam a organização das bases da mesma sigla vinculadas
    por ID, quando todas apontam para uma só organização. Nunca sobrescreve organização já
    definida. Retorna quantas bases foram completadas."""
    vinculadas = db.execute(
        select(BasePrevista.orgao_sigla, Dataset.organizacao_id)
        .join(Dataset, Dataset.ckan_id == BasePrevista.dataset_id)
        .where(BasePrevista.plano_id == plano_id)).all()
    mapa = regras.orgao_por_evidencia((sigla, org) for sigla, org in vinculadas)
    if not mapa:
        return 0
    completadas = 0
    for base in db.scalars(select(BasePrevista).where(
            BasePrevista.plano_id == plano_id, BasePrevista.organizacao_id.is_(None))):
        organizacao_id = mapa.get(regras.chave_sigla(base.orgao_sigla))
        if organizacao_id:
            base.organizacao_id = organizacao_id
            completadas += 1
    return completadas


def resolver_vinculos_pendentes(db: Session, plano_id: int) -> dict[str, int]:
    """PBI-12/13 — tenta de novo SÓ as bases com `dataset_id` nulo e name da planilha (ex.: o
    dataset foi publicado depois da importação). Vínculo já resolvido nunca é recalculado pelo
    nome. Depois, as bases do plano sem organização herdam a organização das bases da mesma sigla
    vinculadas por ID (organização única). Retorna os vínculos resolvidos nesta execução e os que
    continuam pendentes."""
    _plano_ou_404(db, plano_id)
    pendentes = db.scalars(select(BasePrevista).where(
        BasePrevista.plano_id == plano_id, BasePrevista.dataset_id.is_(None),
        BasePrevista.dataset_name_planilha.is_not(None))).all()
    datasets = _datasets_por_name(db, {b.dataset_name_planilha for b in pendentes})
    resolvidos = 0
    for base in pendentes:
        ds = datasets.get(base.dataset_name_planilha)
        if ds is None:
            continue
        base.dataset_id = ds.ckan_id
        if ds.organizacao_id:
            base.organizacao_id = ds.organizacao_id
        resolvidos += 1
    db.flush()
    _completar_orgao_por_evidencia(db, plano_id)
    db.commit()
    return {"vinculos_resolvidos": resolvidos, "vinculos_pendentes": len(pendentes) - resolvidos}


# ------------------------------------------------------------------ situação (PBI-15/19/22)
@dataclass(frozen=True)
class BaseCalculada:
    """Base prevista com situação calculada sobre o inventário (mesmos campos de BaseOut)."""

    id: int
    plano_id: int
    plano_nome: str
    orgao_sigla: str
    orgao_chave: str
    orgao_nome: str | None
    nome_previsto: str
    descricao: str | None
    unidade_responsavel: str | None
    periodicidade: str
    periodicidade_original: str | None
    politicas_publicas: str | None
    possui_conteudo_sigiloso: bool | None
    prazo_abertura: date | None
    vinculo: str  # resolvido | pendente | sem_vinculo
    dataset_id: str | None
    dataset_name: str | None
    dataset_titulo: str | None
    dataset_name_planilha: str | None
    dataset_ativo: bool | None
    data_publicacao: datetime | None  # metadata_created do dataset vinculado e ativo
    recursos_validos: int
    formatos: tuple[str, ...]  # formatos dos recursos válidos, sem repetição
    ultima_atualizacao: datetime | None
    ultima_atualizacao_estimada: bool
    situacao: str
    flag_prazo: str  # vencido | proximo | ""
    classificacao: str


def orgao_chave(organizacao_id: str | None, orgao_sigla: str) -> str:
    """Chave do filtro de órgão: ID da organização ou 'sigla:<SIGLA>' sem correspondência."""
    if organizacao_id:
        return organizacao_id
    return "sigla:" + regras.chave_sigla(orgao_sigla)


def calcular_base(base: BasePrevista, plano_nome: str, hoje: date, janela_dias: int
                  ) -> BaseCalculada:
    ds = base.dataset if base.dataset_id else None
    # Só os recursos que ainda estão no pacote do dataset (recurso apagado do CKAN não conta)
    recursos = recursos_atuais(ds) if ds is not None else []
    validos = [r for r in recursos if not r.eh_dicionario_dados]  # dicionário nunca conta
    ultima = ultima_atualizacao_real(recursos)
    ativo = ds.ativo_no_portal if ds is not None else None
    return BaseCalculada(
        id=base.id, plano_id=base.plano_id, plano_nome=plano_nome, orgao_sigla=base.orgao_sigla,
        orgao_chave=orgao_chave(base.organizacao_id, base.orgao_sigla),
        orgao_nome=base.organizacao.titulo if base.organizacao is not None else None,
        nome_previsto=base.nome_previsto, descricao=base.descricao,
        unidade_responsavel=base.unidade_responsavel, periodicidade=base.periodicidade,
        periodicidade_original=base.periodicidade_original,
        politicas_publicas=base.politicas_publicas,
        possui_conteudo_sigiloso=base.possui_conteudo_sigiloso,
        prazo_abertura=base.prazo_abertura,
        vinculo=("resolvido" if base.dataset_id else
                 "pendente" if base.dataset_name_planilha else "sem_vinculo"),
        dataset_id=base.dataset_id,
        dataset_name=ds.name if ds is not None else None,
        dataset_titulo=ds.titulo if ds is not None else None,
        dataset_name_planilha=base.dataset_name_planilha, dataset_ativo=ativo,
        data_publicacao=(_utc(ds.metadata_created)
                         if ds is not None and ativo and ds.metadata_created else None),
        recursos_validos=len(validos),
        formatos=tuple(sorted({r.formato for r in validos if r.formato})),
        ultima_atualizacao=ultima.data,
        ultima_atualizacao_estimada=ultima.estimada,
        situacao=regras.situacao_base(vinculada=ds is not None, dataset_ativo=ativo,
                                      recursos_validos=len(validos), prazo=base.prazo_abertura,
                                      hoje=hoje, janela_dias=janela_dias),
        flag_prazo=regras.flag_prazo(base.prazo_abertura, hoje, janela_dias),
        classificacao=base.classificacao,
    )


def _consulta_bases(user: UsuarioAtual | None):
    """Bases com dataset, recursos e organização carregados em lote (sem N+1). Usuário restrito
    a órgão vê só as bases do próprio órgão (e não vê as sem organização)."""
    stmt = select(BasePrevista).options(
        selectinload(BasePrevista.dataset).selectinload(Dataset.recursos),
        selectinload(BasePrevista.organizacao))
    return filtrar_por_orgao(stmt, BasePrevista.organizacao_id, user) if user else stmt


def _ordem(b: BaseCalculada):
    return regras.normalizar_texto(b.orgao_sigla), regras.normalizar_texto(b.nome_previsto), b.id


def bases_do_plano(db: Session, plano_id: int, user: UsuarioAtual | None = None, *,
                   hoje: date | None = None, janela_dias: int | None = None
                   ) -> list[BaseCalculada]:
    """PBI-19 — bases do PDA com situação calculada, ordenadas por órgão e nome. Para painel,
    relatórios e assistente. `user=None` = sem escopo de órgão (uso interno consolidado)."""
    plano = _plano_ou_404(db, plano_id)
    hoje = hoje or hoje_local()
    janela = janela_alerta_dias(db) if janela_dias is None else janela_dias
    bases = db.scalars(_consulta_bases(user).where(BasePrevista.plano_id == plano.id)).all()
    return sorted((calcular_base(b, plano.nome, hoje, janela) for b in bases), key=_ordem)


def _opcoes(bases: list[BaseCalculada]) -> OpcoesOut:
    orgaos: dict[str, str] = {}
    for b in bases:  # já ordenadas por sigla: a primeira sigla de cada órgão dá o rótulo
        orgaos.setdefault(b.orgao_chave,
                          b.orgao_sigla + (f" — {b.orgao_nome}" if b.orgao_nome else ""))
    presentes = {b.periodicidade for b in bases}
    return OpcoesOut(
        orgaos=sorted((OpcaoOut(valor=v, rotulo=r) for v, r in orgaos.items()),
                      key=lambda o: regras.normalizar_texto(o.rotulo)),
        periodicidades=[p for p in regras.DOMINIO_PERIODICIDADE if p in presentes]
        + sorted(presentes - set(regras.DOMINIO_PERIODICIDADE)),
        anos=sorted({b.prazo_abertura.year for b in bases if b.prazo_abertura}, reverse=True),
    )


def listar_bases(db: Session, user: UsuarioAtual, *, plano_id: int | None = None,
                 orgao: str | None = None, situacao: str | None = None,
                 periodicidade: str | None = None, ano: int | None = None,
                 prazo: str | None = None) -> BasesOut:
    """PBI-20/21 — tela Monitoramento do PDA. Sem `plano_id` usa o PDA vigente. Filtros:
    orgao = orgao_chave; situacao = rótulo; periodicidade = normalizada; ano = ano do prazo;
    prazo = 'vencido' | 'proximo' (janela do PBI-22)."""
    hoje, janela = hoje_local(), janela_alerta_dias(db)
    plano = _plano_ou_404(db, plano_id) if plano_id is not None else plano_vigente(db)
    if plano is None:
        return BasesOut(plano=None, hoje=hoje, janela_alerta_dias=janela, total_previstas=0,
                        opcoes=OpcoesOut(orgaos=[], periodicidades=[], anos=[]), bases=[])
    todas = bases_do_plano(db, plano.id, user, hoje=hoje, janela_dias=janela)
    filtradas = [
        b for b in todas
        if (not orgao or b.orgao_chave == orgao)
        and (not situacao or b.situacao == situacao)
        and (not periodicidade or b.periodicidade == periodicidade)
        and (ano is None or (b.prazo_abertura is not None and b.prazo_abertura.year == ano))
        and (not prazo or b.flag_prazo == prazo)
    ]
    return BasesOut(plano=_plano_out_db(db, plano, user), hoje=hoje, janela_alerta_dias=janela,
                    total_previstas=len(todas), opcoes=_opcoes(todas),
                    bases=[BaseOut.model_validate(b) for b in filtradas])


def obter_base(db: Session, base_id: int, user: UsuarioAtual) -> BaseCalculada:
    """Detalhe de uma base (modal da tela). Base de outro órgão para usuário restrito → 404."""
    base = db.scalar(_consulta_bases(user).where(BasePrevista.id == base_id)
                     .options(selectinload(BasePrevista.plano)))
    if base is None:
        raise NaoEncontrado("Base prevista não encontrada.")
    return calcular_base(base, base.plano.nome, hoje_local(), janela_alerta_dias(db))
