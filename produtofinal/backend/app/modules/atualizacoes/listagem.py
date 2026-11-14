"""Indicador de atualização sobre TODOS os datasets publicados no portal (ADR-0037).

Usado pela tela Monitoramento de Atualizações, pelo painel (Dashboard e Organizações) e pelos
relatórios. Fica fora de `service.py` porque o módulo pda importa esse arquivo (evita importação
circular).

- Universo: datasets ativos no portal, no escopo de órgão do usuário — previstos no PDA vigente ou
  espontâneos (ADR-0026). O vínculo com o PDA só identifica o tipo de base; não é condição.
- Periodicidade: só o campo customizado "Atualização" do CKAN (`regras.periodicidade_ckan`).
- Última atualização real: maior `last_modified` dos recursos válidos (nunca `metadata_modified`).
"""
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.deps import UsuarioAtual
from app.modules.atualizacoes import regras
from app.modules.atualizacoes.schemas import (
    AtualizacaoLinhaOut,
    AtualizacoesOut,
    OpcaoOut,
    OpcoesAtualizacoesOut,
    ResumoAtualizacoesOut,
)
from app.modules.inventario import regras as regras_inventario
from app.modules.inventario import service as inventario
from app.modules.pda import regras as regras_pda
from app.modules.pda import service as pda

SEM_ORGAO = "sem_orgao"  # chave do filtro para dataset sem organização no inventário


@dataclass(frozen=True)
class DatasetAtualizacao:
    """Situação de atualização de um dataset publicado (mesmos campos de AtualizacaoLinhaOut)."""

    dataset_id: int
    dataset_titulo: str
    dataset_name: str | None
    orgao_chave: str  # id da organização (texto) ou "sem_orgao"
    orgao_sigla: str
    orgao_nome: str | None
    tipo_base: str  # "Prevista no PDA" | "Espontânea" (ADR-0026)
    periodicidade_declarada: str | None  # texto do campo "Atualização" no CKAN, como preenchido
    periodicidade: str  # valor do domínio (`regras.PERIODICIDADES`)
    ultima_atualizacao: datetime | None
    ultima_atualizacao_estimada: bool
    dias_desde_atualizacao: int | None
    prazo_esperado: date | None
    situacao: str


def situacoes_dos_datasets(db: Session, user: UsuarioAtual, hoje: date | None = None
                           ) -> list[DatasetAtualizacao]:
    """Cada dataset ativo no portal (escopo do usuário) com a situação de atualização,
    ordenado por órgão e título."""
    hoje = hoje or pda.hoje_local()
    orgs = inventario.organizacoes(db)
    vinculados = pda.datasets_vinculados_ao_vigente(db)
    linhas = []
    for ds in inventario.datasets_publicados(db, user):
        validos = [r for r in inventario.recursos_atuais(ds) if not r.eh_dicionario_dados]
        ultima = regras.ultima_atualizacao_real(validos)
        declarada = regras_inventario.periodicidade_declarada(ds.extras)
        periodicidade = regras.periodicidade_ckan(declarada)
        data = ultima.data  # já com fuso (UTC quando o CKAN não informa)
        org = orgs.get(ds.organizacao_id) if ds.organizacao_id is not None else None
        linhas.append(DatasetAtualizacao(
            dataset_id=ds.id, dataset_titulo=ds.titulo or ds.name, dataset_name=ds.name,
            orgao_chave=str(org.id) if org else SEM_ORGAO,
            orgao_sigla=((org.sigla or org.titulo).strip() if org else "Sem organização"),
            orgao_nome=org.titulo.strip() if org else None,
            tipo_base=regras_inventario.tipo_de_base(True, ds.id in vinculados) or "",
            periodicidade_declarada=declarada, periodicidade=periodicidade,
            ultima_atualizacao=data, ultima_atualizacao_estimada=ultima.estimada,
            dias_desde_atualizacao=(hoje - data.date()).days if data else None,
            prazo_esperado=regras.vencimento_atualizacao(periodicidade, data),
            situacao=regras.situacao_periodicidade(periodicidade, data, hoje)))
    linhas.sort(key=lambda x: (regras_pda.normalizar_texto(x.orgao_sigla),
                               regras_pda.normalizar_texto(x.dataset_titulo), x.dataset_id))
    return linhas


def _opcoes(linhas: list[DatasetAtualizacao]) -> OpcoesAtualizacoesOut:
    orgaos: dict[str, str] = {}
    for ln in linhas:  # já ordenadas por sigla: a primeira sigla de cada órgão dá o rótulo
        orgaos.setdefault(ln.orgao_chave,
                          ln.orgao_sigla + (f" — {ln.orgao_nome}" if ln.orgao_nome
                                            and ln.orgao_nome != ln.orgao_sigla else ""))
    presentes = {ln.periodicidade for ln in linhas}
    return OpcoesAtualizacoesOut(
        orgaos=sorted((OpcaoOut(valor=v, rotulo=r) for v, r in orgaos.items()),
                      key=lambda o: regras_pda.normalizar_texto(o.rotulo)),
        periodicidades=[p for p in regras.PERIODICIDADES if p in presentes],
        situacoes=list(regras.SITUACOES_ATUALIZACAO),
        tipos_base=list(regras_inventario.TIPOS_DE_BASE))


def listar(db: Session, user: UsuarioAtual, *, orgao: str | None = None,
           periodicidade: str | None = None, situacao: str | None = None,
           dataset: str | None = None, tipo_base: str | None = None) -> AtualizacoesOut:
    """US9/US10 — todos os datasets publicados no portal com a situação de atualização
    (ADR-0037). Filtros: orgao = orgao_chave; periodicidade, situacao e tipo_base = rótulo;
    dataset = trecho do título ou do name (sem acento nem caixa). Cartões e opções ignoram os
    filtros. Escopo de órgão do usuário aplicado na consulta do inventário."""
    hoje = pda.hoje_local()
    plano = pda.plano_vigente(db)
    todas = situacoes_dos_datasets(db, user, hoje)
    por_situacao = Counter(ln.situacao for ln in todas)
    busca = regras_pda.normalizar_texto(dataset or "")
    filtradas = [
        ln for ln in todas
        if (not orgao or ln.orgao_chave == orgao)
        and (not periodicidade or ln.periodicidade == periodicidade)
        and (not situacao or ln.situacao == situacao)
        and (not tipo_base or ln.tipo_base == tipo_base)
        and (not busca or busca in regras_pda.normalizar_texto(
            f"{ln.dataset_titulo} {ln.dataset_name or ''}"))
    ]
    return AtualizacoesOut(
        plano_nome=plano.nome if plano else None, hoje=hoje, total=len(todas),
        resumo=ResumoAtualizacoesOut(
            atualizados=por_situacao[regras.ATUALIZADO], atrasados=por_situacao[regras.ATRASADO],
            proximos_do_vencimento=por_situacao[regras.PROXIMO_DO_VENCIMENTO],
            sem_atualizacao_periodica=por_situacao[regras.SEM_ATUALIZACAO_PERIODICA],
            periodicidade_nao_informada=por_situacao[regras.PERIODICIDADE_NAO_INFORMADA],
            sem_data=por_situacao[regras.SEM_DATA],
            previstas_no_pda=sum(1 for ln in todas if ln.tipo_base == regras_inventario.PREVISTA),
            espontaneas=sum(1 for ln in todas if ln.tipo_base == regras_inventario.ESPONTANEA)),
        opcoes=_opcoes(todas),
        datasets=[AtualizacaoLinhaOut.model_validate(ln, from_attributes=True)
                  for ln in filtradas])
