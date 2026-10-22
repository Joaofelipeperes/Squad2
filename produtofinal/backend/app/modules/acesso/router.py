"""API do módulo acesso. Login é a única rota pública do sistema (além de /saude)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.core.deps import CurrentUser, DbSession, UsuarioAtual, publico, require, require_qualquer
from app.core.permissoes import META, P, por_modulo
from app.core.security import create_access_token
from app.modules.acesso import service
from app.modules.acesso.schemas import (
    GrupoPermissoesOut, LogAcessoOut, LoginIn, OrgaoResumo, PapelIn, PapelOut, PermissaoOut,
    SessaoOut, TokenOut, UsuarioIn, UsuarioOut,
)

router = APIRouter()
GERENCIA = require_qualquer(P.ACESSO_GERENCIAR_USUARIOS, P.ACESSO_GERENCIAR_PAPEIS)


def _erro(exc: Exception):
    raise HTTPException(422, str(exc))


def _usuario_ou_404(db, usuario_id: int):
    u = service.usuario_por_id(db, usuario_id)
    if u is None:
        raise HTTPException(404, "Usuário não encontrado.")
    return u


def _papel_ou_404(db, papel_id: int):
    p = service.papel_por_id(db, papel_id)
    if p is None:
        raise HTTPException(404, "Papel não encontrado.")
    return p


@router.post("/login", response_model=TokenOut, dependencies=[Depends(publico)])
def login(body: LoginIn, db: DbSession, request: Request):
    request.state.usuario = body.email.lower()  # log de acesso: inclui tentativas que falham
    u = service.autenticar(db, body.email, body.senha)
    if not u:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    return TokenOut(access_token=create_access_token(u.id), sessao=service.sessao_out(db, u))


@router.get("/me", response_model=SessaoOut)
def me(user: CurrentUser, db: DbSession):
    return service.sessao_out(db, service.usuario_por_id(db, user.id))


# ------------------------------------------------------------------ catálogo e órgãos
@router.get("/catalogo", response_model=list[GrupoPermissoesOut], dependencies=[Depends(GERENCIA)])
def catalogo():
    return [GrupoPermissoesOut(modulo=m, permissoes=[
        PermissaoOut(codigo=str(p), rotulo=META[p].rotulo, descricao=META[p].descricao,
                     sensivel=META[p].sensivel) for p in perms]) for m, perms in por_modulo().items()]


@router.get("/orgaos", response_model=list[OrgaoResumo],
            dependencies=[Depends(require(P.ACESSO_GERENCIAR_USUARIOS))])
def orgaos(db: DbSession):
    return service.listar_orgaos(db)


# ------------------------------------------------------------------ usuários
@router.get("/usuarios", response_model=list[UsuarioOut],
            dependencies=[Depends(require(P.ACESSO_GERENCIAR_USUARIOS))])
def listar_usuarios(db: DbSession):
    return service.listar_usuarios(db)


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def criar_usuario(body: UsuarioIn, db: DbSession,
                  editor: UsuarioAtual = Depends(require(P.ACESSO_GERENCIAR_USUARIOS))):
    try:
        return service.usuario_out(db, service.salvar_usuario(db, body, editor=editor))
    except service.ErroAcesso as exc:
        _erro(exc)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioOut)
def atualizar_usuario(usuario_id: int, body: UsuarioIn, db: DbSession,
                      editor: UsuarioAtual = Depends(require(P.ACESSO_GERENCIAR_USUARIOS))):
    u = _usuario_ou_404(db, usuario_id)
    try:
        return service.usuario_out(db, service.salvar_usuario(db, body, u, editor=editor))
    except service.ErroAcesso as exc:
        _erro(exc)



# ------------------------------------------------------------------ papéis
@router.get("/papeis", response_model=list[PapelOut], dependencies=[Depends(GERENCIA)])
def listar_papeis(db: DbSession):
    return service.listar_papeis(db)


@router.post("/papeis", response_model=PapelOut, status_code=201)
def criar_papel(body: PapelIn, db: DbSession,
                editor: UsuarioAtual = Depends(require(P.ACESSO_GERENCIAR_PAPEIS))):
    try:
        return service.papel_out(db, service.salvar_papel(db, body, editor=editor))
    except service.ErroAcesso as exc:
        _erro(exc)


@router.put("/papeis/{papel_id}", response_model=PapelOut)
def atualizar_papel(papel_id: int, body: PapelIn, db: DbSession,
                    editor: UsuarioAtual = Depends(require(P.ACESSO_GERENCIAR_PAPEIS))):
    p = _papel_ou_404(db, papel_id)
    try:
        return service.papel_out(db, service.salvar_papel(db, body, p, editor=editor))
    except service.ErroAcesso as exc:
        _erro(exc)


@router.delete("/papeis/{papel_id}", status_code=204)
def excluir_papel(papel_id: int, db: DbSession,
                  editor: UsuarioAtual = Depends(require(P.ACESSO_GERENCIAR_PAPEIS))):
    p = _papel_ou_404(db, papel_id)
    try:
        service.excluir_papel(db, p, editor=editor)
    except service.ErroAcesso as exc:
        _erro(exc)


# ------------------------------------------------------------------ log de acesso
@router.get("/logs", response_model=list[LogAcessoOut],
            dependencies=[Depends(require(P.ACESSO_VER_LOGS))])
def listar_logs(db: DbSession, usuario: str | None = None, desde: datetime | None = None,
                ate: datetime | None = None, limite: int = Query(200, ge=1, le=5000)):
    """Mais recentes primeiro. `usuario` filtra por trecho do e-mail."""
    return service.listar_logs(db, usuario, desde, ate, limite)
