"""Acesso ao banco do módulo painel (ADR-0019): agregados do inventário por órgão (tela
Organizações). Só leitura, sempre pelas buscas genéricas de `Dao` (excluídos não contam)."""
from sqlalchemy import func, select

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.inventario.service import condicao_recurso_atual


class PainelDao(Dao):
    def organizacoes_visiveis(self, user: UsuarioAtual) -> dict[int, Organizacao]:
        stmt = filtrar_por_orgao(select(Organizacao), Organizacao.id, user)
        return {o.id: o for o in self.buscar_lista(stmt)}

    def datasets_ativos_por_orgao(self, orgao_ids) -> dict[int, int]:
        """organizacao_id → datasets ativos no portal."""
        return dict(self.buscar_linhas(
            select(Dataset.organizacao_id, func.count())
            .where(Dataset.ativo_no_portal.is_(True), Dataset.organizacao_id.in_(orgao_ids))
            .group_by(Dataset.organizacao_id)))

    def recursos_validos_por_orgao(self, orgao_ids) -> dict[int, int]:
        """organizacao_id → recursos atuais, sem dicionário de dados, de datasets ativos."""
        return dict(self.buscar_linhas(
            select(Dataset.organizacao_id, func.count(Recurso.id))
            .join(Dataset, Dataset.id == Recurso.dataset_id)
            .where(Dataset.ativo_no_portal.is_(True), Dataset.organizacao_id.in_(orgao_ids),
                   Recurso.eh_dicionario_dados.is_(False), condicao_recurso_atual())
            .group_by(Dataset.organizacao_id)))

    def datasets_por_situacao(self, user: UsuarioAtual) -> dict[bool, int]:
        """ativo_no_portal → quantidade de datasets no escopo de órgão do usuário."""
        stmt = select(Dataset.ativo_no_portal, func.count()).group_by(Dataset.ativo_no_portal)
        return dict(self.buscar_linhas(filtrar_por_orgao(stmt, Dataset.organizacao_id, user)))

    def recursos_validos(self, user: UsuarioAtual) -> list[Recurso]:
        """Recursos atuais, sem dicionário de dados, de datasets ativos, no escopo do usuário."""
        stmt = (select(Recurso).join(Dataset, Dataset.id == Recurso.dataset_id)
                .where(Dataset.ativo_no_portal.is_(True), Recurso.eh_dicionario_dados.is_(False),
                       condicao_recurso_atual()))
        return self.buscar_lista(filtrar_por_orgao(stmt, Dataset.organizacao_id, user))

    def datasets_ativos(self, user: UsuarioAtual) -> list[tuple[int, int | None]]:
        """(id, organizacao_id) dos datasets ativos no portal, no escopo de órgão do usuário."""
        stmt = select(Dataset.id, Dataset.organizacao_id).where(Dataset.ativo_no_portal.is_(True))
        return self.buscar_linhas(filtrar_por_orgao(stmt, Dataset.organizacao_id, user))

    def orgao_de_cada_dataset(self) -> dict[int, int | None]:
        return dict(self.buscar_linhas(select(Dataset.id, Dataset.organizacao_id)))
