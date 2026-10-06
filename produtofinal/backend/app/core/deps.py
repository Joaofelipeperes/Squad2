"""Dependências FastAPI compartilhadas e o PORTÃO ÚNICO de controle de acesso.

Toda rota declara uma destas dependências (o main.py recusa subir rota sem nenhuma delas):

    Depends(publico)                       sem login (apenas /acesso/login e /saude)
    Depends(autenticado)                   qualquer usuário logado
    Depends(require(P.X))                  exige a permissão X
    Depends(require(P.X, P.Y))             exige X e Y
    Depends(require_qualquer(P.X, P.Y))    exige X ou Y

Nas consultas por órgão, use `filtrar_por_orgao(stmt, Model.coluna_orgao, user)`.
"""
from dataclasses import dataclass, field
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissoes import META, P
from app.core.security import decode_access_token

DbSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)
_MARCA = "_gda_acesso"  # atributo que identifica dependências de controle de acesso


@dataclass(frozen=True)
class UsuarioAtual:
    """Identidade + permissões resolvidas para a requisição corrente."""

    id: int
    email: str
    nome: str
    orgao_id: str | None
    papeis: list[str]
    permissoes: frozenset[str] = field(default_factory=frozenset)

    def pode(self, permissao: P | str) -> bool:
        return str(permissao) in self.permissoes

    @property
    def restrito_a_orgao(self) -> bool:
        return self.orgao_id is not None


def _marcar(fn, valor):
    setattr(fn, _MARCA, valor)
    return fn


def get_current_user(
    db: DbSession,
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UsuarioAtual:
    from app.modules.acesso.service import carregar_usuario_atual  # import tardio evita ciclo

    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária.")
    try:
        payload = decode_access_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada.")
    user = carregar_usuario_atual(db, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inativo ou inexistente.")
    return user


def publico() -> None:
    """Marca explícita de rota aberta. Use com parcimônia."""


_marcar(publico, "publico")


def autenticado(user: Annotated[UsuarioAtual, Depends(get_current_user)]) -> UsuarioAtual:
    return user


_marcar(autenticado, "autenticado")


def _negar(faltando: list[str]):
    rotulos = ", ".join(META[P(p)].rotulo for p in faltando)
    raise HTTPException(status.HTTP_403_FORBIDDEN, f"Seu perfil não permite: {rotulos}.")


def require(*permissoes: P):
    """Exige TODAS as permissões informadas. Devolve o UsuarioAtual."""
    if not permissoes:
        raise ValueError("require() precisa de ao menos uma permissão.")

    def _dep(user: Annotated[UsuarioAtual, Depends(get_current_user)]) -> UsuarioAtual:
        faltando = [str(p) for p in permissoes if not user.pode(p)]
        if faltando:
            _negar(faltando)
        return user

    return _marcar(_dep, tuple(str(p) for p in permissoes))


def require_qualquer(*permissoes: P):
    """Exige AO MENOS UMA das permissões informadas."""

    def _dep(user: Annotated[UsuarioAtual, Depends(get_current_user)]) -> UsuarioAtual:
        if not any(user.pode(p) for p in permissoes):
            _negar([str(p) for p in permissoes])
        return user

    return _marcar(_dep, tuple(str(p) for p in permissoes))


def filtrar_por_orgao(stmt, coluna_orgao, user: UsuarioAtual):
    """Aplica o escopo de órgão a uma consulta SQLAlchemy. Usuário sem órgão vê tudo."""
    return stmt.where(coluna_orgao == user.orgao_id) if user.restrito_a_orgao else stmt


def exigir_mesmo_orgao(user: UsuarioAtual, orgao_id: str | None) -> None:
    """Para ações sobre um registro específico (ex.: enviar recurso para o dataset X)."""
    if user.restrito_a_orgao and orgao_id != user.orgao_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registro de outro órgão.")


# ------------------------------------------------------------------ verificação na subida
def controle_de_acesso(route) -> object | None:
    """Retorna a marca de acesso da rota (procura recursivamente nas dependências)."""
    pilha = list(route.dependant.dependencies)
    while pilha:
        dep = pilha.pop()
        marca = getattr(dep.call, _MARCA, None)
        if marca is not None:
            return marca
        pilha.extend(dep.dependencies)
    return None


CurrentUser = Annotated[UsuarioAtual, Depends(autenticado)]
