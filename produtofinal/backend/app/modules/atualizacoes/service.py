"""Contratos do módulo atualizacoes — responsável: Humberto. Implementar conforme os PBIs citados."""
from app.modules.atualizacoes import regras
from app.modules.atualizacoes.regras import UltimaAtualizacao


def ultima_atualizacao_real(recursos) -> UltimaAtualizacao:
    """PBI-23/24 — maior last_modified entre os recursos, EXCLUINDO dicionário de dados.
    Nunca usar metadata_modified. Recurso sem last_modified → usar created e sinalizar (PBI-25).

    Implementado em `regras.ultima_atualizacao_real` (função pura): devolve
    `UltimaAtualizacao(data, estimada)`; `estimada=True` quando a data veio de `created`.
    Também usado pelo módulo pda (coluna "Última atualização" do Monitoramento do PDA).
    """
    return regras.ultima_atualizacao_real(recursos)


def situacao_periodicidade(periodicidade: str | None, ultima, hoje) -> str:
    """PBI-27/28 — 'Atualizado' | 'Próximo do vencimento' | 'Atrasado' | 'Sem atualização
    periódica' | 'Periodicidade não informada' | 'Sem data de atualização' (ADR-0037).
    `periodicidade` = campo "Atualização" do CKAN. Implementado em
    `regras.situacao_periodicidade` (função pura). Ainda não considera a ressalva do recurso
    parcial (PBI-78) nem as correções por anonimização (PBI-79). A lista de todos os datasets
    publicados com a situação está em `listagem.situacoes_dos_datasets`."""
    return regras.situacao_periodicidade(periodicidade, ultima, hoje)
