"""Acesso ao banco do módulo inventario (ADR-0019): coletas, espelho do CKAN e tela Datasets.

Toda consulta passa pelas funções genéricas de `Dao` (registros excluídos nunca aparecem) e toda
gravação por `save_generic`/`update_generic` (auditoria preenchida). A coleta é ação do sistema
(`usuario_id` None), salvo a coleta manual, cujo registro guarda quem a pediu.
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Coleta, Dataset, DatasetSnapshot, Organizacao, Recurso


class InventarioDao(Dao):
    # ------------------------------------------------------------------ coletas
    def coleta_em_andamento(self) -> Coleta | None:
        return self.buscar_um(select(Coleta).where(Coleta.status == "executando").limit(1))

    def ultima_coleta(self) -> Coleta | None:
        return self.buscar_um(select(Coleta).order_by(Coleta.id.desc()).limit(1))

    def historico_coletas(self, limite: int) -> list[Coleta]:
        return self.buscar_lista(select(Coleta).order_by(Coleta.id.desc()).limit(limite))

    def obter_coleta(self, coleta_id: int) -> Coleta | None:
        return self.obter(Coleta, coleta_id)

    def criar_coleta(self, origem: str, solicitante: str | None) -> Coleta:
        c = self.save_generic(Coleta(origem=origem, solicitada_por=solicitante))
        self.commit()
        self.recarregar(c)
        return c

    # ------------------------------------------------------------------ espelho do CKAN
    def organizacoes_por_id_ckan(self) -> dict[str, Organizacao]:
        return {o.id_ckan: o for o in self.buscar_lista(select(Organizacao)) if o.id_ckan}

    def dataset_por_id_ckan(self, id_ckan: str) -> Dataset | None:
        return self.buscar_um(select(Dataset).where(Dataset.id_ckan == id_ckan))

    def recursos_por_id_ckan(self, ids_ckan: list[str]) -> dict[str, Recurso]:
        if not ids_ckan:
            return {}
        return {r.id_ckan: r for r in self.buscar_lista(
            select(Recurso).where(Recurso.id_ckan.in_(ids_ckan)))}

    def salvar_recurso(self, rec: Recurso) -> None:
        self.save_generic(rec)

    def marcar_fora_do_portal(self, vistos: set[str]) -> int:
        """Datasets que não vieram na coleta (excluídos ou privados no portal) — PBI-15 / US14."""
        return self.update_generic(Dataset, Dataset.id_ckan.not_in(vistos), ativo_no_portal=False)

    def gravar_fotografia(self, foto: DatasetSnapshot) -> None:
        self.save_generic(foto)

    # ------------------------------------------------------------------ tela Datasets
    @staticmethod
    def _consulta_datasets(user: UsuarioAtual):
        """Datasets com recursos em lote (sem N+1), no escopo de órgão do usuário."""
        stmt = select(Dataset).options(selectinload(Dataset.recursos))
        return filtrar_por_orgao(stmt, Dataset.organizacao_id, user)

    def datasets_visiveis(self, user: UsuarioAtual) -> list[Dataset]:
        return self.buscar_lista(self._consulta_datasets(user))

    def dataset_visivel(self, dataset_id: int, user: UsuarioAtual) -> Dataset | None:
        return self.buscar_um(self._consulta_datasets(user).where(Dataset.id == dataset_id))

    def organizacoes(self) -> dict[int, Organizacao]:
        return {o.id: o for o in self.buscar_lista(select(Organizacao))}
