"""Acesso ao banco do módulo pda (ADR-0019). Toda consulta e gravação do módulo passa por aqui;
as funções genéricas do `Dao` já excluem os registros com `deleted` e preenchem a auditoria."""
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Dataset, Organizacao
from app.modules.pda.models import BasePrevista, PlanoPda

_LOTE_IN = 500  # tamanho do lote em consultas IN (limite de parâmetros do SQLite/PostgreSQL)
# Vínculo pendente: sem dataset, mas com o ID do CKAN ou o name informado (planilha/formulário)
_PENDENTE = and_(BasePrevista.dataset_id.is_(None),
                 or_(BasePrevista.dataset_id_ckan_planilha.is_not(None),
                     BasePrevista.dataset_name_planilha.is_not(None)))


class PdaDao(Dao):
    # ------------------------------------------------------------------ planos
    def plano(self, plano_id: int) -> PlanoPda | None:
        return self.obter(PlanoPda, plano_id)

    def plano_vigente(self) -> PlanoPda | None:
        return self.buscar_um(select(PlanoPda).where(PlanoPda.vigente.is_(True)).limit(1))

    def planos(self) -> list[PlanoPda]:
        """Vigente primeiro, depois os importados mais recentemente."""
        return self.buscar_lista(select(PlanoPda).order_by(
            PlanoPda.vigente.desc(), PlanoPda.importado_em.desc(), PlanoPda.id.desc()))

    def total_de_planos(self) -> int:
        return int(self.buscar_valor(select(func.count()).select_from(PlanoPda)) or 0)

    def nomes_de_planos(self, ignorar_id: int | None = None) -> list[str]:
        stmt = select(PlanoPda.nome)
        if ignorar_id is not None:
            stmt = stmt.where(PlanoPda.id != ignorar_id)
        return self.buscar_lista(stmt)

    def desmarcar_vigentes(self) -> None:
        self.update_generic(PlanoPda, PlanoPda.vigente.is_(True), vigente=False)

    def contagens(self, user: UsuarioAtual | None, plano_ids: list[int] | None) -> list:
        """(plano_id, bases, vínculos resolvidos, vínculos pendentes) por plano; com `user`, no
        escopo de órgão dele."""
        stmt = (select(BasePrevista.plano_id, func.count(BasePrevista.id),
                       func.count(BasePrevista.dataset_id),
                       func.coalesce(func.sum(case((_PENDENTE, 1), else_=0)), 0))
                .group_by(BasePrevista.plano_id))
        if user is not None:
            stmt = filtrar_por_orgao(stmt, BasePrevista.organizacao_id, user)
        if plano_ids is not None:
            stmt = stmt.where(BasePrevista.plano_id.in_(plano_ids))
        return self.buscar_linhas(stmt)

    def excluir_plano(self, plano: PlanoPda) -> None:
        """Exclusão lógica do plano e de todas as suas bases."""
        self.delete_generic_lote(BasePrevista, BasePrevista.plano_id == plano.id)
        self.delete_generic(plano)

    # ------------------------------------------------------------------ bases
    def base(self, base_id: int) -> BasePrevista | None:
        return self.obter(BasePrevista, base_id)

    def _consulta_bases(self, user: UsuarioAtual | None):
        """Bases com dataset, recursos e organização carregados em lote (sem N+1). Usuário
        restrito a órgão vê só as bases do próprio órgão (e não vê as sem organização)."""
        stmt = select(BasePrevista).options(
            selectinload(BasePrevista.dataset).selectinload(Dataset.recursos),
            selectinload(BasePrevista.organizacao), selectinload(BasePrevista.plano))
        return filtrar_por_orgao(stmt, BasePrevista.organizacao_id, user) if user else stmt

    def bases_do_plano(self, plano_id: int, user: UsuarioAtual | None) -> list[BasePrevista]:
        return self.buscar_lista(self._consulta_bases(user)
                                 .where(BasePrevista.plano_id == plano_id))

    def bases_do_dataset(self, dataset_id: int, user: UsuarioAtual | None) -> list[BasePrevista]:
        return self.buscar_lista(self._consulta_bases(user)
                                 .where(BasePrevista.dataset_id == dataset_id))

    def base_visivel(self, base_id: int, user: UsuarioAtual | None) -> BasePrevista | None:
        return self.buscar_um(self._consulta_bases(user).where(BasePrevista.id == base_id))

    def bases_pendentes(self, plano_id: int) -> list[BasePrevista]:
        """Bases sem dataset vinculado mas com ID do CKAN ou name informado (vínculo pendente)."""
        return self.buscar_lista(select(BasePrevista).where(
            BasePrevista.plano_id == plano_id, _PENDENTE))

    def bases_sem_organizacao(self, plano_id: int) -> list[BasePrevista]:
        return self.buscar_lista(select(BasePrevista).where(
            BasePrevista.plano_id == plano_id, BasePrevista.organizacao_id.is_(None)))

    def siglas_vinculadas(self, plano_id: int) -> list:
        """(sigla da planilha, organização do dataset) das bases do plano vinculadas por ID."""
        return self.buscar_linhas(
            select(BasePrevista.orgao_sigla, Dataset.organizacao_id)
            .join(Dataset, Dataset.id == BasePrevista.dataset_id)
            .where(BasePrevista.plano_id == plano_id))

    def atualizar_total(self, plano_id: int) -> None:
        """`total_bases` do plano = bases ativas."""
        total = self.buscar_valor(select(func.count()).select_from(BasePrevista)
                                  .where(BasePrevista.plano_id == plano_id))
        self.update_generic(PlanoPda, PlanoPda.id == plano_id, total_bases=int(total or 0))

    # ------------------------------------------------------------------ inventário (leitura)
    def dataset(self, dataset_id: int) -> Dataset | None:
        return self.obter(Dataset, dataset_id)

    def dataset_por_id_ckan(self, id_ckan: str) -> Dataset | None:
        return self.buscar_um(select(Dataset).where(Dataset.id_ckan == id_ckan))

    def organizacao(self, organizacao_id: int) -> Organizacao | None:
        return self.obter(Organizacao, organizacao_id)

    def organizacao_do_dataset(self, dataset_id: int) -> int | None:
        return self.buscar_valor(select(Dataset.organizacao_id).where(Dataset.id == dataset_id))

    def organizacoes(self, user: UsuarioAtual | None = None) -> list[Organizacao]:
        """Organizações do inventário; com `user`, só as do escopo de órgão dele."""
        stmt = select(Organizacao)
        if user is not None:
            stmt = filtrar_por_orgao(stmt, Organizacao.id, user)
        return self.buscar_lista(stmt)

    def datasets_por_id_ckan(self, ids: set[str]) -> list[Dataset]:
        """Datasets cujo `id_ckan` está em `ids` (em lotes)."""
        lista, encontrados = sorted(ids), []
        for i in range(0, len(lista), _LOTE_IN):
            encontrados += self.buscar_lista(
                select(Dataset).where(Dataset.id_ckan.in_(lista[i:i + _LOTE_IN])))
        return encontrados

    def datasets_por_name(self, names: set[str]) -> list[Dataset]:
        """Datasets cujo `name` está em `names` (em lotes)."""
        lista, encontrados = sorted(names), []
        for i in range(0, len(lista), _LOTE_IN):
            encontrados += self.buscar_lista(
                select(Dataset).where(Dataset.name.in_(lista[i:i + _LOTE_IN])))
        return encontrados

    def buscar_datasets(self, condicao, user: UsuarioAtual, limite: int) -> list:
        """(Dataset, título da organização) que atendem `condicao`, ativos no portal primeiro."""
        stmt = (select(Dataset, Organizacao.titulo)
                .outerjoin(Organizacao, Organizacao.id == Dataset.organizacao_id)
                .where(condicao)
                .order_by(Dataset.ativo_no_portal.desc(), Dataset.titulo)
                .limit(limite))
        return self.buscar_linhas(filtrar_por_orgao(stmt, Dataset.organizacao_id, user))
