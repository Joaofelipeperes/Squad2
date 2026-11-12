"""Acesso ao banco do módulo assistente (ADR-0019): os dados do contexto do modelo, sempre no
escopo de órgão do usuário. Só leitura, pelas buscas genéricas de `Dao` (excluídos não contam)."""
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.lgpd.models import Achado


class AssistenteDao(Dao):
    def organizacoes_visiveis(self, user: UsuarioAtual) -> list[Organizacao]:
        return self.buscar_lista(filtrar_por_orgao(select(Organizacao), Organizacao.id, user))

    def datasets_visiveis(self, user: UsuarioAtual) -> list[Dataset]:
        """Datasets com os recursos carregados em lote (sem N+1)."""
        stmt = select(Dataset).options(selectinload(Dataset.recursos))
        return self.buscar_lista(filtrar_por_orgao(stmt, Dataset.organizacao_id, user))

    def achados_por_dataset(self, user: UsuarioAtual) -> list[tuple[int, str, str, int]]:
        """(dataset.id, tipo, status, quantidade) dos achados LGPD — só contagens, nunca valores."""
        stmt = (select(Dataset.id, Achado.tipo, Achado.status, func.count(Achado.id))
                .join(Recurso, Recurso.id == Achado.recurso_id)
                .join(Dataset, Dataset.id == Recurso.dataset_id)
                .group_by(Dataset.id, Achado.tipo, Achado.status))
        return self.buscar_linhas(filtrar_por_orgao(stmt, Dataset.organizacao_id, user))
