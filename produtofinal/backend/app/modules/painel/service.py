"""Contratos do módulo painel — responsável: João. Implementar conforme os PBIs citados."""
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.inventario.service import condicao_recurso_atual
from app.modules.metadados import regras as regras_metadados
from app.modules.metadados.service import recursos_formato_fechado
from app.modules.painel.schemas import OrganizacaoOut, OrganizacoesOut, PlanoResumoOut
from app.modules.parametros.router import obter as obter_parametro
from app.modules.pda import service as pda
from app.modules.pda.regras import (
    EM_ATRASO,
    PROXIMO_DO_PRAZO,
    PUBLICADO,
    chave_sigla,
    normalizar_texto,
)


def kpis(db) -> dict:
    """PBI-56 — órgãos, bases previstas/publicadas, atrasadas, desatualizadas, alertas LGPD."""
    raise NotImplementedError


def indice_atencao_por_orgao(db):
    """PBI-76/84 — critério documentado e auditável (PBI-59)."""
    raise NotImplementedError


def organizacoes(db: Session, user: UsuarioAtual) -> OrganizacoesOut:
    """US19 — tela Organizações: por órgão, o inventário do portal (datasets ativos, recursos e
    recursos em formato fechado) e as bases do PDA VIGENTE (previstas, vinculadas, publicadas,
    em atraso entre as vinculadas e próximas do prazo). Respeita o escopo de órgão do usuário.
    Indicadores que dependem de vínculo, de regra ainda não definida ou de outro módulo vêm como
    None."""
    orgs = {o.ckan_id: o for o in db.scalars(
        filtrar_por_orgao(select(Organizacao), Organizacao.ckan_id, user))}

    datasets = dict(db.execute(
        select(Dataset.organizacao_id, func.count())
        .where(Dataset.ativo_no_portal.is_(True), Dataset.organizacao_id.in_(orgs))
        .group_by(Dataset.organizacao_id)).all())
    recursos = dict(db.execute(
        select(Dataset.organizacao_id, func.count(Recurso.ckan_id))
        .join(Dataset, Dataset.ckan_id == Recurso.dataset_id)
        .where(Dataset.ativo_no_portal.is_(True), Dataset.organizacao_id.in_(orgs),
               Recurso.eh_dicionario_dados.is_(False), condicao_recurso_atual())
        .group_by(Dataset.organizacao_id)).all())

    abertos = list(obter_parametro(db, "formatos_abertos"))
    org_do_dataset = dict(db.execute(select(Dataset.ckan_id, Dataset.organizacao_id)).all())
    fechados: dict[str, Counter] = defaultdict(Counter)
    for r in recursos_formato_fechado(db, abertos):
        org = org_do_dataset.get(r.dataset_id)
        if org in orgs:
            fechados[org][regras_metadados.normalizar_formato(r.formato)] += 1

    plano = pda.plano_vigente(db)
    bases = pda.bases_do_plano(db, plano.id, user) if plano else []
    por_chave: dict[str, list] = defaultdict(list)
    for b in bases:
        por_chave[b.orgao_chave].append(b)

    def linha(chave: str, organizacao: Organizacao | None) -> OrganizacaoOut:
        bs = por_chave.get(chave, [])
        vinculadas = [b for b in bs if b.dataset_id]
        siglas = Counter(chave_sigla(b.orgao_sigla) for b in bs)
        nome = organizacao.titulo.strip() if organizacao else chave.removeprefix("sigla:")
        org_id = organizacao.ckan_id if organizacao else None
        return OrganizacaoOut(
            chave=chave, organizacao_id=org_id, nome=nome,
            siglas=[s for s, _ in siglas.most_common()],
            datasets_no_portal=datasets.get(org_id, 0), recursos_validos=recursos.get(org_id, 0),
            recursos_formato_fechado=sum(fechados[org_id].values()) if org_id else 0,
            formatos_fechados=dict(fechados[org_id].most_common()) if org_id else {},
            bases_previstas=len(bs),
            bases_vinculadas=len(vinculadas),
            bases_publicadas=sum(1 for b in bs if b.situacao == PUBLICADO),
            bases_em_atraso=(sum(1 for b in vinculadas if b.situacao == EM_ATRASO)
                             if vinculadas else None),
            bases_proximas_do_prazo=sum(1 for b in bs if b.situacao == PROXIMO_DO_PRAZO))

    linhas = [linha(ckan_id, o) for ckan_id, o in orgs.items()]
    linhas += [linha(chave, None) for chave in por_chave if chave.startswith("sigla:")]
    linhas.sort(key=lambda o: (normalizar_texto(o.nome), o.chave))
    return OrganizacoesOut(
        plano=PlanoResumoOut(id=plano.id, nome=plano.nome) if plano else None,
        hoje=pda.hoje_local(), formatos_abertos=abertos, organizacoes=linhas)
