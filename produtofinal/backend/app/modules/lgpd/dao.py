"""Acesso ao banco do módulo lgpd (ADR-0019): achados, decisões, varreduras e anonimizações.

Toda consulta passa pelas buscas genéricas de `Dao` (registros excluídos nunca aparecem) e toda
gravação por `save_generic`/`delete_generic` (auditoria preenchida). Varredura e prévia rodam em
segundo plano como ação do sistema (`usuario_id` None); o pedido guarda quem o fez.
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.ia.models import PerfilProvedorIA, VinculoTarefaIA
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.lgpd.models import Achado, CorrecaoPublicada, DecisaoTriagem, Varredura

EM_FILA = ("pendente", "executando")


class LgpdDao(Dao):
    # ------------------------------------------------------------------ inventário (leitura)
    def organizacoes(self) -> dict[int, Organizacao]:
        return {o.id: o for o in self.buscar_lista(select(Organizacao))}

    def recurso(self, recurso_id: int | None) -> Recurso | None:
        return self.obter(Recurso, recurso_id)

    def dataset(self, dataset_id: int | None) -> Dataset | None:
        return self.obter(Dataset, dataset_id)

    def recurso_e_dataset(self, recurso_id: int, user: UsuarioAtual | None
                          ) -> tuple[Recurso, Dataset] | None:
        """Recurso e seu dataset, no escopo de órgão do usuário (None = sistema, sem escopo)."""
        stmt = (select(Recurso, Dataset).join(Dataset, Dataset.id == Recurso.dataset_id)
                .options(selectinload(Dataset.recursos)).where(Recurso.id == recurso_id))
        if user is not None:
            stmt = filtrar_por_orgao(stmt, Dataset.organizacao_id, user)
        linha = self.buscar(stmt).first()
        return (linha[0], linha[1]) if linha else None

    def datasets_ativos(self, user: UsuarioAtual | None, dataset_id: int | None = None
                        ) -> list[Dataset]:
        """Datasets ativos no portal com os recursos (sem N+1), no escopo do usuário."""
        stmt = (select(Dataset).options(selectinload(Dataset.recursos))
                .where(Dataset.ativo_no_portal))
        if dataset_id is not None:
            stmt = stmt.where(Dataset.id == dataset_id)
        if user is not None:
            stmt = filtrar_por_orgao(stmt, Dataset.organizacao_id, user)
        return self.buscar_lista(stmt)

    def modelo_da_tarefa(self, tarefa: str) -> str | None:
        """Nome do modelo do perfil vinculado à tarefa de IA (só para exibir na varredura)."""
        v = self.buscar_um(select(VinculoTarefaIA).where(VinculoTarefaIA.tarefa == tarefa))
        p = self.obter(PerfilProvedorIA, v.perfil_id) if v and v.perfil_id else None
        return p.modelo if p else None

    # ------------------------------------------------------------------ achados
    @staticmethod
    def _consulta_achados(user: UsuarioAtual | None):
        stmt = (select(Achado, Recurso, Dataset)
                .join(Recurso, Recurso.id == Achado.recurso_id)
                .join(Dataset, Dataset.id == Recurso.dataset_id))
        return filtrar_por_orgao(stmt, Dataset.organizacao_id, user) if user else stmt

    def achados_visiveis(self, user: UsuarioAtual) -> list[tuple[Achado, Recurso, Dataset]]:
        return self.buscar_linhas(self._consulta_achados(user))

    def achado_visivel(self, achado_id: int, user: UsuarioAtual
                       ) -> tuple[Achado, Recurso, Dataset] | None:
        return self.buscar(self._consulta_achados(user).where(Achado.id == achado_id)).first()

    def achados_por_id(self, ids: list[int]) -> dict[int, Achado]:
        if not ids:
            return {}
        return {a.id: a for a in self.buscar_lista(select(Achado).where(Achado.id.in_(ids)))}

    def achados_do_recurso(self, recurso_id: int) -> list[Achado]:
        return self.buscar_lista(select(Achado).where(Achado.recurso_id == recurso_id))

    def achados_confirmados(self, recurso_id: int, user: UsuarioAtual
                            ) -> list[tuple[Achado, Recurso, Dataset]]:
        return self.buscar_linhas(self._consulta_achados(user).where(
            Achado.recurso_id == recurso_id, Achado.status == "confirmado"))

    def decisoes(self, achado_id: int) -> list[DecisaoTriagem]:
        return self.buscar_lista(select(DecisaoTriagem).where(DecisaoTriagem.achado_id == achado_id)
                                 .order_by(DecisaoTriagem.momento.desc(), DecisaoTriagem.id.desc()))

    def achados_com_decisao(self, ids: list[int]) -> set[int]:
        if not ids:
            return set()
        return set(self.buscar_lista(select(DecisaoTriagem.achado_id)
                                     .where(DecisaoTriagem.achado_id.in_(ids))))

    # ------------------------------------------------------------------ varreduras
    @staticmethod
    def _consulta_varreduras(user: UsuarioAtual):
        stmt = (select(Varredura, Recurso, Dataset)
                .join(Recurso, Recurso.id == Varredura.recurso_id)
                .join(Dataset, Dataset.id == Recurso.dataset_id))
        return filtrar_por_orgao(stmt, Dataset.organizacao_id, user)

    def varreduras(self, user: UsuarioAtual, limite: int
                   ) -> list[tuple[Varredura, Recurso, Dataset]]:
        return self.buscar_linhas(self._consulta_varreduras(user)
                                  .order_by(Varredura.id.desc()).limit(limite))

    def varreduras_em_andamento(self, user: UsuarioAtual) -> int:
        return self.buscar_valor(filtrar_por_orgao(
            select(func.count(Varredura.id)).join(Recurso, Recurso.id == Varredura.recurso_id)
            .join(Dataset, Dataset.id == Recurso.dataset_id)
            .where(Varredura.status.in_(EM_FILA)), Dataset.organizacao_id, user)) or 0

    def pendentes_do_escopo(self, user: UsuarioAtual) -> list[Varredura]:
        return self.buscar_lista(filtrar_por_orgao(
            select(Varredura).join(Recurso, Recurso.id == Varredura.recurso_id)
            .join(Dataset, Dataset.id == Recurso.dataset_id)
            .where(Varredura.status == "pendente"), Dataset.organizacao_id, user))

    def recursos_analisados(self, user: UsuarioAtual) -> int:
        return self.buscar_valor(filtrar_por_orgao(
            select(func.count(func.distinct(Varredura.recurso_id)))
            .join(Recurso, Recurso.id == Varredura.recurso_id)
            .join(Dataset, Dataset.id == Recurso.dataset_id)
            .where(Varredura.status == "ok"), Dataset.organizacao_id, user)) or 0

    def ultima_varredura_concluida(self) -> dict[int, datetime]:
        """recurso.id → início da última varredura concluída (ok ou ignorada)."""
        return {rid: quando for rid, quando in self.buscar_linhas(
            select(Varredura.recurso_id, func.max(Varredura.iniciada_em))
            .where(Varredura.status.in_(("ok", "ignorado"))).group_by(Varredura.recurso_id))}

    def em_fila(self) -> list[Varredura]:
        return self.buscar_lista(select(Varredura).where(Varredura.status.in_(EM_FILA)))

    def varredura(self, varredura_id: int) -> Varredura | None:
        return self.obter(Varredura, varredura_id)

    # ------------------------------------------------------------------ anonimizações
    def correcao(self, correcao_id: int) -> CorrecaoPublicada | None:
        return self.obter(CorrecaoPublicada, correcao_id)

    def correcao_visivel(self, correcao_id: int, user: UsuarioAtual
                         ) -> tuple[CorrecaoPublicada, Recurso, Dataset] | None:
        stmt = (select(CorrecaoPublicada, Recurso, Dataset)
                .join(Recurso, Recurso.id == CorrecaoPublicada.recurso_id)
                .join(Dataset, Dataset.id == Recurso.dataset_id)
                .where(CorrecaoPublicada.id == correcao_id))
        return self.buscar(filtrar_por_orgao(stmt, Dataset.organizacao_id, user)).first()

    def correcoes(self, user: UsuarioAtual, limite: int
                  ) -> list[tuple[CorrecaoPublicada, Recurso, Dataset]]:
        stmt = (select(CorrecaoPublicada, Recurso, Dataset)
                .join(Recurso, Recurso.id == CorrecaoPublicada.recurso_id)
                .join(Dataset, Dataset.id == Recurso.dataset_id)
                .order_by(CorrecaoPublicada.id.desc()).limit(limite))
        return self.buscar_linhas(filtrar_por_orgao(stmt, Dataset.organizacao_id, user))

    def correcao_aberta(self, recurso_id: int) -> CorrecaoPublicada | None:
        """Prévia ou publicação em andamento para o recurso (só uma por vez)."""
        return self.buscar_um(select(CorrecaoPublicada).where(
            CorrecaoPublicada.recurso_id == recurso_id,
            CorrecaoPublicada.status.in_(("gerando_previa", "previa", "publicando", "revertendo"))))
