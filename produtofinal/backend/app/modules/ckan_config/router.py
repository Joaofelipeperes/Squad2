"""Rotas de Configurações CKAN (ADR-0024) — perfis de conexão e troca do CKAN em uso."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.ckan_config import service
from app.modules.ckan_config.schemas import PerfilCkanIn, PerfilCkanOut

router = APIRouter()

Gestor = Depends(require(P.CKAN_CONFIG_GERENCIAR))


@router.get("/perfis", response_model=list[PerfilCkanOut])
def listar(db: DbSession, _user: UsuarioAtual = Gestor):
    return service.listar(db)


@router.post("/perfis", response_model=PerfilCkanOut, status_code=201)
def criar(body: PerfilCkanIn, db: DbSession, user: UsuarioAtual = Gestor):
    try:
        return service.criar(db, body, user)
    except service.NomeEmUso as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.put("/perfis/{perfil_id}", response_model=PerfilCkanOut)
def atualizar(perfil_id: int, body: PerfilCkanIn, db: DbSession, user: UsuarioAtual = Gestor):
    try:
        return service.atualizar(db, perfil_id, body, user)
    except service.PerfilNaoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.NomeEmUso as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.delete("/perfis/{perfil_id}", status_code=204)
def excluir(perfil_id: int, db: DbSession, user: UsuarioAtual = Gestor):
    try:
        service.excluir(db, perfil_id, user)
    except service.PerfilNaoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.NomeEmUso as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/perfis/{perfil_id}/selecionar", response_model=PerfilCkanOut)
def selecionar(perfil_id: int, db: DbSession, user: UsuarioAtual = Gestor):
    """Passa a usar este CKAN em todo o sistema (vale na hora; não apaga os dados já coletados)."""
    try:
        return service.selecionar(db, perfil_id, user)
    except service.PerfilNaoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
