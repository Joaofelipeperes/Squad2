"""Consultas e gravações do módulo ia (ADR-0019): perfis, vínculos tarefa → perfil e uso."""
from sqlalchemy import or_, select

from app.core.dao import Dao
from app.modules.ia.models import PerfilProvedorIA, UsoIA, VinculoTarefaIA


class IaDao(Dao):
    # ------------------------------------------------------------------ perfis
    def perfil(self, perfil_id: int | None) -> PerfilProvedorIA | None:
        return self.obter(PerfilProvedorIA, perfil_id)

    def perfil_por_nome(self, nome: str) -> PerfilProvedorIA | None:
        return self.buscar_um(select(PerfilProvedorIA).where(PerfilProvedorIA.nome == nome))

    def perfis(self) -> list[PerfilProvedorIA]:
        return self.buscar_lista(select(PerfilProvedorIA).order_by(PerfilProvedorIA.nome))

    def excluir_perfil(self, perfil: PerfilProvedorIA) -> None:
        """Exclusão lógica; vínculos que ainda apontassem para ele ficam sem perfil (como o antigo
        ON DELETE SET NULL)."""
        self.update_generic(VinculoTarefaIA, VinculoTarefaIA.perfil_id == perfil.id,
                            perfil_id=None)
        self.update_generic(VinculoTarefaIA, VinculoTarefaIA.perfil_fallback_id == perfil.id,
                            perfil_fallback_id=None)
        self.delete_generic(perfil)

    # ------------------------------------------------------------------ vínculos
    def vinculo(self, tarefa: str) -> VinculoTarefaIA | None:
        return self.buscar_um(select(VinculoTarefaIA).where(VinculoTarefaIA.tarefa == tarefa))

    def vinculos_do_perfil(self, perfil_id: int) -> list[VinculoTarefaIA]:
        return self.buscar_lista(select(VinculoTarefaIA).where(or_(
            VinculoTarefaIA.perfil_id == perfil_id,
            VinculoTarefaIA.perfil_fallback_id == perfil_id)))

    # ------------------------------------------------------------------ uso
    def registrar_uso(self, uso: UsoIA) -> None:
        self.save_generic(uso)
        self.commit()

    def usos(self, limite: int) -> list[UsoIA]:
        return self.buscar_lista(select(UsoIA).order_by(UsoIA.momento.desc()).limit(limite))
