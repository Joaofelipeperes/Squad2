"""Contratos do módulo atualizacoes — responsável: Humberto. Implementar conforme os PBIs citados."""


def ultima_atualizacao_real(recursos) -> "datetime | None":
    """PBI-23/24 — maior last_modified entre os recursos, EXCLUINDO dicionário de dados.
    Nunca usar metadata_modified. Recurso sem last_modified → usar created e sinalizar (PBI-25)."""
    raise NotImplementedError


def situacao_periodicidade(periodicidade: str, ultima, hoje) -> str:
    """PBI-27/28 — 'Atualizado' | 'Próximo do vencimento' | 'Atrasado' | 'Sem informação'.
    Considerar a ressalva do recurso parcial (PBI-78) e ignorar correções por anonimização (PBI-79)."""
    raise NotImplementedError
