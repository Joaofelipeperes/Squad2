"""Contratos do módulo pda — responsável: Humberto. Implementar conforme os PBIs citados."""


def importar_planilha_vinculacao(db, arquivo) -> int:
    """PBI-12 — importa a planilha GEDA (base prevista ↔ ID do dataset CKAN). Retorna nº de vínculos."""
    raise NotImplementedError


def situacao_prazo(base, hoje, janela_dias: int) -> str:
    """PBI-19 — 'Publicado' | 'Vencido' | 'Próximo do prazo' | 'No prazo' | 'Sem vínculo'."""
    raise NotImplementedError


def listar_bases(db, *, orgao=None, situacao=None, periodicidade=None, ano=None, prazo=None):
    """PBI-20/21 — alimenta a tela Monitoramento do PDA com os filtros do protótipo."""
    raise NotImplementedError
