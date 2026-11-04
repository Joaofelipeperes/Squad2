"""Listagem da tela Monitoramento de Atualizações. Fica fora de `service.py` porque o módulo pda
importa esse arquivo (evita importação circular)."""
from collections import Counter
from datetime import date

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
from app.modules.pda import regras as regras_pda
from app.modules.pda import service as pda


def _linha(b: pda.BaseCalculada, hoje: date) -> AtualizacaoLinhaOut:
    """Situação pela periodicidade do PDA vigente (ADR-0023); dataset fora do portal → Sem
    informação, como no Dashboard."""
    ultima = b.ultima_atualizacao
    situacao = (regras.situacao_periodicidade(b.periodicidade, ultima, hoje,
                                              b.periodicidade_original)
                if b.dataset_ativo else regras.SEM_INFORMACAO)
    return AtualizacaoLinhaOut(
        base_id=b.id, dataset_id=b.dataset_id, dataset_titulo=b.dataset_titulo or b.nome_previsto,
        dataset_name=b.dataset_name, orgao_chave=b.orgao_chave, orgao_sigla=b.orgao_sigla,
        orgao_nome=b.orgao_nome, periodicidade=b.periodicidade, ultima_atualizacao=ultima,
        ultima_atualizacao_estimada=b.ultima_atualizacao_estimada,
        dias_desde_atualizacao=(hoje - ultima.date()).days if ultima else None,
        prazo_esperado=regras.vencimento_atualizacao(b.periodicidade, ultima,
                                                     b.periodicidade_original),
        situacao=situacao)


def _opcoes(linhas: list[AtualizacaoLinhaOut]) -> OpcoesAtualizacoesOut:
    orgaos: dict[str, str] = {}
    for ln in linhas:  # já ordenadas por sigla: a primeira sigla de cada órgão dá o rótulo
        orgaos.setdefault(ln.orgao_chave,
                          ln.orgao_sigla + (f" — {ln.orgao_nome}" if ln.orgao_nome else ""))
    presentes = {ln.periodicidade for ln in linhas}
    return OpcoesAtualizacoesOut(
        orgaos=sorted((OpcaoOut(valor=v, rotulo=r) for v, r in orgaos.items()),
                      key=lambda o: regras_pda.normalizar_texto(o.rotulo)),
        periodicidades=[p for p in regras_pda.DOMINIO_PERIODICIDADE if p in presentes]
        + sorted(presentes - set(regras_pda.DOMINIO_PERIODICIDADE)),
        situacoes=list(regras.SITUACOES_ATUALIZACAO))


def listar(db: Session, user: UsuarioAtual, *, orgao: str | None = None,
           periodicidade: str | None = None, situacao: str | None = None,
           dataset: str | None = None) -> AtualizacoesOut:
    """US9/US10 — datasets vinculados às bases do PDA vigente, com a situação de atualização.
    Filtros: orgao = orgao_chave; periodicidade e situacao = rótulo; dataset = trecho do título ou
    do name (sem acento nem caixa). Cartões e opções ignoram os filtros. Escopo de órgão do
    usuário aplicado por `pda.bases_do_plano`."""
    hoje = pda.hoje_local()
    plano = pda.plano_vigente(db)
    bases = pda.bases_do_plano(db, plano.id, user, hoje=hoje) if plano else []
    todas = [_linha(b, hoje) for b in bases if b.dataset_id]
    por_situacao = Counter(ln.situacao for ln in todas)
    busca = regras_pda.normalizar_texto(dataset or "")
    filtradas = [
        ln for ln in todas
        if (not orgao or ln.orgao_chave == orgao)
        and (not periodicidade or ln.periodicidade == periodicidade)
        and (not situacao or ln.situacao == situacao)
        and (not busca or busca in regras_pda.normalizar_texto(
            f"{ln.dataset_titulo} {ln.dataset_name or ''}"))
    ]
    return AtualizacoesOut(
        plano_nome=plano.nome if plano else None, hoje=hoje, total=len(todas),
        resumo=ResumoAtualizacoesOut(
            atualizados=por_situacao[regras.ATUALIZADO], atrasados=por_situacao[regras.ATRASADO],
            proximos_do_vencimento=por_situacao[regras.PROXIMO_DO_VENCIMENTO],
            sem_informacao=por_situacao[regras.SEM_INFORMACAO]
            + por_situacao[regras.SEM_PERIODICIDADE]),
        opcoes=_opcoes(todas), datasets=filtradas)
