"""Rotas do módulo relatorios (US20). Cada relatório exige também a permissão de acesso do
módulo de origem (verificada no service)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.relatorios import service
from app.modules.relatorios.schemas import PreviaOut, RelatorioOut

router = APIRouter()


def _erro(exc: service.ErroRelatorio) -> HTTPException:
    codigo = (404 if isinstance(exc, service.NaoEncontrado)
              else 403 if isinstance(exc, service.SemPermissao) else 422)
    return HTTPException(codigo, str(exc))


@router.get("", response_model=list[RelatorioOut])
def listar(user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR))]):
    return service.catalogo(user)


@router.get("/{nome}/previa", response_model=PreviaOut)
def previa(nome: str, db: DbSession,
           user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR))]):
    try:
        return service.previa(db, nome, user)
    except service.ErroRelatorio as exc:
        raise _erro(exc) from exc


@router.get("/{nome}/exportar")
def exportar(nome: str, db: DbSession,
             user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR,
                                                           P.RELATORIOS_EXPORTAR))],
             formato: Annotated[str, Query(pattern="^(xlsx|csv)$")] = "xlsx"):
    try:
        conteudo, media_type, arquivo = service.exportar(db, nome, formato, user)
    except service.ErroRelatorio as exc:
        raise _erro(exc) from exc
    return Response(conteudo, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})
