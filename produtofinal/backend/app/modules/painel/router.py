"""Rotas do módulo painel. Endpoints são adicionados à medida que os PBIs forem implementados."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.painel import service
from app.modules.painel.schemas import OrganizacoesOut

router = APIRouter()


@router.get("/organizacoes", response_model=OrganizacoesOut)
def organizacoes(db: DbSession, user: Annotated[UsuarioAtual, Depends(require(P.PAINEL_ACESSAR))]):
    """US19 — situação consolidada por órgão (tela Organizações)."""
    return service.organizacoes(db, user)
