"""Contratos do módulo metadados — responsável: Luiza / João. Implementar conforme os PBIs
citados."""
from sqlalchemy.orm import Session

from app.modules.inventario.models import Recurso
from app.modules.metadados import regras
from app.modules.metadados.dao import MetadadosDao


def completude(dataset, obrigatorios: list[str]) -> float:
    """PBI-49 — percentual de metadados obrigatórios preenchidos (lista em parametros)."""
    raise NotImplementedError


def datasets_sem_recurso(db):
    """PBI-51"""
    raise NotImplementedError


def recursos_formato_fechado(db: Session, formatos_abertos: list[str]) -> list[Recurso]:
    """PBI-53 — recursos ATUAIS (ainda no pacote do dataset) de datasets ativos no portal, fora
    do dicionário de dados, cujo formato não está em `formatos_abertos` (parâmetro da GEDA).
    Formato é atributo do RECURSO; recurso sem formato informado conta como fechado."""
    recursos = MetadadosDao(db).recursos_validos_de_datasets_ativos()
    return [r for r in recursos if not regras.eh_formato_aberto(r.formato, formatos_abertos)]
