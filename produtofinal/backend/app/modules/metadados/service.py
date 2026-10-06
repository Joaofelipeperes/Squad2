"""Contratos do módulo metadados — responsável: Luiza / João. Implementar conforme os PBIs citados."""


def completude(dataset, obrigatorios: list[str]) -> float:
    """PBI-49 — percentual de metadados obrigatórios preenchidos (lista em parametros)."""
    raise NotImplementedError


def datasets_sem_recurso(db):
    """PBI-51"""
    raise NotImplementedError


def recursos_formato_fechado(db, formatos_abertos: list[str]):
    """PBI-53 — exclui dicionário de dados; formato é atributo do RECURSO."""
    raise NotImplementedError
