"""API do módulo acesso. Login é a única rota pública do sistema (além de /saude)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, UsuarioAtual, publico, require, require_qualquer
from app.core.permissoes import META, P, por_modulo
from app.core.security import create_access_token
from app.modules.acesso import service
from app.modules.acesso.models import Papel, Usuario
from app.modules.acesso.schemas import (
    GrupoPermissoesOut, LoginIn, OrgaoResumo, PapelIn, PapelOut, PermissaoOut, SessaoOut,
    TokenOut, UsuarioIn, UsuarioOut,
)

router = APIRouter()
GERENCIA = require_qualquer(P.ACESSO_GERENCIAR_USUARIOS, P.ACESSO_GERENCIAR_PAPEIS)


def _erro(exc: Exception):
    raise HTTPException(422, str(exc))


@router.post("/login", response_model=TokenOut, dependencies=[Depends(publico)])
def login(body: LoginIn, db: DbSession):
    u = service.autenticar(db, body.email, body.senha)
    if not u:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    return TokenOut(access_token=create_access_token(u.id), sessao=service.sessao_out(db, u))


@router.get("/me", response_model=SessaoOut)
def me(user: CurrentUser, db: DbSession):
    return service.sessao_out(db, db.get(Usuario, user.id))


# ------------------------------------------------------------------ catálogo e órgãos
@router.get("/catalogo", response_model=list[GrupoPermissoesOut], dependencies=[Depends(GERENCIA)])
def catalogo():
    return [GrupoPermissoesOut(modulo=m, permissoes=[
        PermissaoOut(codigo=str(p), rotulo=META[p].rotulo, descricao=META[p].descricao,
                     sensivel=META[p].sensivel) for p in perms]) for m, perms in por_modulo().items()]


@router.get("/orgaos", response_model=list[OrgaoResumo],
            dependencies=[Depends(require(P.ACESSO_GERENCIAR_USUARIOS))])
def orgaos(db: DbSession):
    from app.modules.inventario.models import Organizacao

    return [OrgaoResumo(ckan_id=o.ckan_id, titulo=o.titulo)
            for o in db.scalars(select(Organizacao).order_by(Organizacao.titulo)).all()]


# ------------------------------------------------------------------ usuários
@router.get("/usuarios", response_model=list[UsuarioOut],
            dependencies=[Depends(require(P.ACESSO_GERENCIAR_USUARIOS))])
def listar_usuarios(db: DbSession):
    return [service.usuario_out(db, u)
            for u in db.scalars(select(Usuario).order_by(Usuario.nome)).all()]


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
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(404, "Usuário não encontrado.")
    try:
        return service.usuario_out(db, service.salvar_usuario(db, body, u, editor=editor))
    except service.ErroAcesso as exc:
        _erro(exc)


# ------------------------------------------------------------------ papéis
@router.get("/papeis", response_model=list[PapelOut], dependencies=[Depends(GERENCIA)])
def listar_papeis(db: DbSession):
    return [service.papel_out(db, p) for p in db.scalars(select(Papel).order_by(Papel.id)).all()]


@router.post("/papeis", response_model=PapelOut, status_code=201,
             dependencies=[Depends(require(P.ACESSO_GERENCIAR_PAPEIS))])
def criar_papel(body: PapelIn, db: DbSession):
    try:
        return service.papel_out(db, service.salvar_papel(db, body))
    except service.ErroAcesso as exc:
        _erro(exc)


@router.put("/papeis/{papel_id}", response_model=PapelOut,
            dependencies=[Depends(require(P.ACESSO_GERENCIAR_PAPEIS))])
def atualizar_papel(papel_id: int, body: PapelIn, db: DbSession):
    p = db.get(Papel, papel_id)
    if p is None:
        raise HTTPException(404, "Papel não encontrado.")
    try:
        return service.papel_out(db, service.salvar_papel(db, body, p))
    except service.ErroAcesso as exc:
        _erro(exc)


@router.delete("/papeis/{papel_id}", status_code=204,
               dependencies=[Depends(require(P.ACESSO_GERENCIAR_PAPEIS))])
def excluir_papel(papel_id: int, db: DbSession):
    p = db.get(Papel, papel_id)
    if p is None:
        raise HTTPException(404, "Papel não encontrado.")
    try:
        service.excluir_papel(db, p)
    except service.ErroAcesso as exc:
        _erro(exc)
