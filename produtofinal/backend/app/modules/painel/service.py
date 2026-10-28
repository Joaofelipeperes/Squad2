"""Contratos do módulo painel — responsável: João. Implementar conforme os PBIs citados."""
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.core.deps import UsuarioAtual
from app.modules.atualizacoes import regras as regras_atualizacao
from app.modules.inventario.models import Organizacao
from app.modules.inventario.service import ultima_coleta
from app.modules.metadados import regras as regras_metadados
from app.modules.metadados.service import datasets_sem_recurso, recursos_formato_fechado
from app.modules.painel.dao import PainelDao
from app.modules.painel.schemas import (
    AlertaOut,
    ContagemOut,
    KpisOut,
    OrganizacaoOut,
    OrganizacoesOut,
    PlanoResumoOut,
    VisaoGeralOut,
)
from app.modules.parametros.router import obter as obter_parametro
from app.modules.pda import service as pda
from app.modules.pda.regras import (
    EM_ATRASO,
    PRAZO_VENCIDO,
    PROXIMO_DO_PRAZO,
    PUBLICADO,
    SEM_RECURSO,
    SITUACOES,
    chave_sigla,
    normalizar_texto,
)

AGUARDANDO_VINCULO = "Aguardando vínculo"
ATUALIZACAO_ATRASADA = "Atualização atrasada"
ALERTAS_MAXIMO = 10  # por tipo de alerta
TIPOS_DE_ALERTA = ("PDA", "Atualização", "Inventário")
# Prioridade dos alertas (menor primeiro); "Prazo vencido" sem vínculo não é alerta: o atraso
# não está confirmado (ver pda.md)
_PRIORIDADE = {EM_ATRASO: 0, ATUALIZACAO_ATRASADA: 1, SEM_RECURSO: 2, PROXIMO_DO_PRAZO: 3,
               "Dataset sem recurso": 4}


def situacao_atualizacao(base, hoje: date) -> str:
    """Situação de atualização de uma base do PDA vigente (ADR-0020): sem vínculo → "Aguardando
    vínculo"; dataset fora do portal → "Sem informação"; senão a regra por periodicidade do
    módulo atualizacoes sobre a última atualização real do dataset vinculado."""
    if not base.dataset_id:
        return AGUARDANDO_VINCULO
    if not base.dataset_ativo:
        return regras_atualizacao.SEM_INFORMACAO
    return regras_atualizacao.situacao_periodicidade(
        base.periodicidade, base.ultima_atualizacao, hoje, base.periodicidade_original)


def kpis(db: Session, user: UsuarioAtual, bases: list, *, orgaos: int, datasets: dict[bool, int],
         recursos: int, sem_recurso: int, atualizacoes_atrasadas: int) -> KpisOut:
    """PBI-56 — cartões da Visão Geral a partir das bases do PDA vigente e do inventário.
    Atualizações em atraso só entre as bases vinculadas (None sem nenhuma); dados pessoais (lgpd)
    fica None."""
    vinculadas = [b for b in bases if b.dataset_id]
    return KpisOut(
        orgaos_monitorados=orgaos, orgaos_no_pda=len({b.orgao_chave for b in bases}),
        bases_previstas=len(bases), bases_vinculadas=len(vinculadas),
        bases_publicadas=sum(1 for b in bases if b.situacao == PUBLICADO),
        bases_em_atraso=(sum(1 for b in vinculadas if b.situacao == EM_ATRASO)
                         if vinculadas else None),
        bases_prazo_vencido=sum(1 for b in bases if b.situacao == PRAZO_VENCIDO),
        datasets_publicados=datasets.get(True, 0), datasets_fora_do_portal=datasets.get(False, 0),
        recursos_monitorados=recursos, datasets_sem_recurso=sem_recurso,
        atualizacoes_em_atraso=atualizacoes_atrasadas if vinculadas else None)


def visao_geral(db: Session, user: UsuarioAtual) -> VisaoGeralOut:
    """US19 — tela Visão Geral (Dashboard): cartões, bases do PDA VIGENTE por situação do PDA e
    por situação de atualização (periodicidade do PDA, ADR-0020) e alertas prioritários. Tudo no
    escopo de órgão do usuário e a partir da última coleta (`ultima_coleta`, PBI-58)."""
    dao = PainelDao.de(db, user)
    hoje = pda.hoje_local()
    orgs = dao.organizacoes_visiveis(user)
    plano = pda.plano_vigente(db)
    bases = pda.bases_do_plano(db, plano.id, user) if plano else []
    recursos = dao.recursos_validos(user)
    sem_recurso = [d for d in datasets_sem_recurso(db)
                   if not user.restrito_a_orgao or d.organizacao_id in orgs]

    por_situacao = Counter(b.situacao for b in bases)
    atualizacao = {b.id: situacao_atualizacao(b, hoje) for b in bases}
    por_atualizacao = Counter(atualizacao.values())
    rotulos_atualizacao = [*regras_atualizacao.SITUACOES_ATUALIZACAO, AGUARDANDO_VINCULO]
    estimadas = sum(1 for b in bases if b.dataset_id and b.ultima_atualizacao_estimada)

    alertas = [AlertaOut(tipo="PDA", orgao=b.orgao_nome or b.orgao_sigla, item=b.nome_previsto,
                         situacao=b.situacao, prazo=b.prazo_abertura,
                         destino=f"/pda?orgao={b.orgao_chave}")
               for b in bases if b.situacao in _PRIORIDADE]
    alertas += [AlertaOut(tipo="Atualização", orgao=b.orgao_nome or b.orgao_sigla,
                          item=b.nome_previsto, situacao=ATUALIZACAO_ATRASADA,
                          prazo=regras_atualizacao.vencimento_atualizacao(
                              b.periodicidade, b.ultima_atualizacao, b.periodicidade_original),
                          destino=f"/pda?orgao={b.orgao_chave}")
                for b in bases if atualizacao[b.id] == regras_atualizacao.ATRASADO]
    alertas += [AlertaOut(tipo="Inventário",
                          orgao=orgs[d.organizacao_id].titulo if d.organizacao_id in orgs else None,
                          item=d.titulo or d.name or "", situacao="Dataset sem recurso", prazo=None,
                          destino="/datasets")
                for d in sem_recurso]
    alertas.sort(key=lambda a: (_PRIORIDADE[a.situacao], a.prazo or date.max,
                                normalizar_texto(a.orgao), normalizar_texto(a.item)))
    por_tipo = Counter(a.tipo for a in alertas)
    # Os mais prioritários de CADA tipo: um tipo numeroso não esconde os outros
    primeiros = [a for t in TIPOS_DE_ALERTA for a in [x for x in alertas if x.tipo == t]
                 [:ALERTAS_MAXIMO]]
    primeiros.sort(key=alertas.index)
    coleta = ultima_coleta(db)
    return VisaoGeralOut(
        plano=PlanoResumoOut(id=plano.id, nome=plano.nome) if plano else None, hoje=hoje,
        ultima_coleta=coleta.finalizada_em if coleta else None,
        kpis=kpis(db, user, bases, orgaos=len(orgs), datasets=dao.datasets_por_situacao(user),
                  recursos=len(recursos), sem_recurso=len(sem_recurso),
                  atualizacoes_atrasadas=por_atualizacao.get(regras_atualizacao.ATRASADO, 0)),
        situacoes_pda=[ContagemOut(rotulo=s, total=por_situacao.get(s, 0)) for s in SITUACOES],
        situacoes_atualizacao=[ContagemOut(rotulo=r, total=por_atualizacao.get(r, 0))
                               for r in rotulos_atualizacao],
        atualizacao_estimada=estimadas, alertas=primeiros, total_alertas=len(alertas),
        alertas_por_tipo={t: por_tipo.get(t, 0) for t in TIPOS_DE_ALERTA})


def indice_atencao_por_orgao(db):
    """PBI-76/84 — critério documentado e auditável (PBI-59)."""
    raise NotImplementedError


def organizacoes(db: Session, user: UsuarioAtual) -> OrganizacoesOut:
    """US19 — tela Organizações: por órgão, o inventário do portal (datasets ativos, recursos e
    recursos em formato fechado) e as bases do PDA VIGENTE (previstas, vinculadas, publicadas,
    em atraso entre as vinculadas e próximas do prazo). Respeita o escopo de órgão do usuário.
    Indicadores que dependem de vínculo, de regra ainda não definida ou de outro módulo vêm como
    None."""
    dao = PainelDao.de(db, user)
    orgs = dao.organizacoes_visiveis(user)
    datasets = dao.datasets_ativos_por_orgao(orgs)
    recursos = dao.recursos_validos_por_orgao(orgs)

    abertos = list(obter_parametro(db, "formatos_abertos"))
    org_do_dataset = dao.orgao_de_cada_dataset()
    fechados: dict[int, Counter] = defaultdict(Counter)
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
        org_id = organizacao.id if organizacao else None
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

    linhas = [linha(pda.orgao_chave(org_id, ""), o) for org_id, o in orgs.items()]
    linhas += [linha(chave, None) for chave in por_chave if chave.startswith("sigla:")]
    linhas.sort(key=lambda o: (normalizar_texto(o.nome), o.chave))
    return OrganizacoesOut(
        plano=PlanoResumoOut(id=plano.id, nome=plano.nome) if plano else None,
        hoje=pda.hoje_local(), formatos_abertos=abertos, organizacoes=linhas)
