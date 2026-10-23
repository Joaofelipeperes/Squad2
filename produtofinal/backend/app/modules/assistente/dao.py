"""Acesso ao banco do módulo assistente (ADR-0019): contagens agregadas para o contexto do
modelo. Só leitura, pelas buscas genéricas de `Dao` (excluídos não contam)."""
from sqlalchemy import func, select

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.inventario.service import condicao_recurso_atual


class AssistenteDao(Dao):
    def organizacoes_visiveis(self, user: UsuarioAtual) -> list[Organizacao]:
        return self.buscar_lista(filtrar_por_orgao(select(Organizacao), Organizacao.id, user))

    def datasets_ativos(self, organizacao_id: int) -> int:
        return self.buscar_valor(select(func.count()).select_from(Dataset).where(
            Dataset.organizacao_id == organizacao_id, Dataset.ativo_no_portal))

    def recursos_validos(self, organizacao_id: int) -> int:
        """Recursos dos datasets ativos que ainda estão no portal; dicionário de dados não conta."""
        return self.buscar_valor(select(func.count()).select_from(Recurso).join(Dataset).where(
            Dataset.organizacao_id == organizacao_id, Dataset.ativo_no_portal,
            condicao_recurso_atual(), Recurso.eh_dicionario_dados.is_(False)))
