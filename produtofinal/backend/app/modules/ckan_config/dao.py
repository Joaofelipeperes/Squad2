"""Acesso ao banco dos perfis de conexão do CKAN (ADR-0024)."""
from sqlalchemy import select

from app.core.dao import Dao
from app.modules.ckan_config.models import CkanPerfil


class CkanConfigDao(Dao):
    def listar(self) -> list[CkanPerfil]:
        return self.buscar_lista(select(CkanPerfil).order_by(CkanPerfil.nome))

    def por_id(self, perfil_id: int) -> CkanPerfil | None:
        return self.obter(CkanPerfil, perfil_id)

    def por_nome(self, nome: str) -> CkanPerfil | None:
        return self.buscar_um(select(CkanPerfil).where(CkanPerfil.nome == nome))

    def selecionado(self) -> CkanPerfil | None:
        return self.buscar_um(select(CkanPerfil).where(CkanPerfil.selecionado.is_(True)))

    def existe_algum(self) -> bool:
        return self.buscar_um(select(CkanPerfil)) is not None

    def salvar(self, *perfis: CkanPerfil) -> None:
        self.save_generic(*perfis)

    def excluir(self, perfil: CkanPerfil) -> None:
        self.delete_generic(perfil)

    def limpar_selecao(self) -> None:
        """Tira a seleção de todos os perfis (antes de marcar um novo)."""
        self.update_generic(CkanPerfil, selecionado=False)
