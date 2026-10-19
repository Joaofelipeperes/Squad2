"""Contratos do módulo metadados — responsável: Luiza / João. Implementar conforme os PBIs
citados."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventario.models import Dataset, Recurso
from app.modules.inventario.service import condicao_recurso_atual
from app.modules.metadados import regras


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
    stmt = (select(Recurso).join(Dataset, Dataset.ckan_id == Recurso.dataset_id)
            .where(Dataset.ativo_no_portal.is_(True), Recurso.eh_dicionario_dados.is_(False),
                   condicao_recurso_atual()))
    return [r for r in db.scalars(stmt) if not regras.eh_formato_aberto(r.formato,
                                                                       formatos_abertos)]
