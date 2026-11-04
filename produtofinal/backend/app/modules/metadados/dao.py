"""Acesso ao banco do módulo metadados (ADR-0019). Só leitura, pelas buscas genéricas de `Dao`."""
from sqlalchemy import select

from app.core.dao import Dao
from app.modules.inventario.models import Dataset, Recurso
from app.modules.inventario.service import condicao_recurso_atual


class MetadadosDao(Dao):
    def datasets_ativos_sem_recurso(self) -> list[Dataset]:
        """Datasets ativos no portal sem nenhum recurso ATUAL fora do dicionário de dados."""
        validos = (select(Recurso.id)
                   .where(Recurso.dataset_id == Dataset.id, Recurso.eh_dicionario_dados.is_(False),
                          condicao_recurso_atual()))
        return self.buscar_lista(select(Dataset).where(Dataset.ativo_no_portal.is_(True),
                                                       ~validos.exists()).order_by(Dataset.titulo))

    def recursos_validos_de_datasets_ativos(self) -> list[Recurso]:
        """Recursos ATUAIS (ainda no pacote do dataset), fora do dicionário de dados, de
        datasets ativos no portal."""
        return self.buscar_lista(
            select(Recurso).join(Dataset, Dataset.id == Recurso.dataset_id)
            .where(Dataset.ativo_no_portal.is_(True), Recurso.eh_dicionario_dados.is_(False),
                   condicao_recurso_atual()))
