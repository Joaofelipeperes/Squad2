"""Rotas do módulo atualizacoes (/api/v1/atualizacoes). Só valida a entrada e delega."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.atualizacoes.schemas import AtualizacoesOut

router = APIRouter()


@router.get("/datasets", response_model=AtualizacoesOut)
def listar_datasets(
    db: DbSession,
    user: Annotated[UsuarioAtual, Depends(require(P.ATUALIZACOES_ACESSAR))],
    orgao: str | None = None,
    periodicidade: str | None = None,
    situacao: str | None = None,
    dataset: str | None = None,
):
    """US9/US10 — tela Monitoramento de Atualizações (datasets do PDA vigente). Filtros: orgao
    (chave do órgão), periodicidade, situacao e dataset (busca por título/name)."""
    # Importação tardia: `listagem` usa o módulo pda, que importa este pacote (ciclo na carga)
    from app.modules.atualizacoes import listagem

    return listagem.listar(db, user, orgao=orgao, periodicidade=periodicidade,
                           situacao=situacao, dataset=dataset)
