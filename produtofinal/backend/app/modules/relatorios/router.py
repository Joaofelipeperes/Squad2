"""Rotas do módulo relatorios (US20). Cada relatório exige também a permissão de acesso do
módulo de origem (verificada no service)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.relatorios import service
from app.modules.relatorios.schemas import (
    OrgaoOpcaoOut,
    PreviaOut,
    RelatorioOrgaoOut,
    RelatorioOut,
    TabelaExportarIn,
)

router = APIRouter()


def _erro(exc: service.ErroRelatorio) -> HTTPException:
    codigo = (404 if isinstance(exc, service.NaoEncontrado)
              else 403 if isinstance(exc, service.SemPermissao) else 422)
    return HTTPException(codigo, str(exc))


@router.get("", response_model=list[RelatorioOut])
def listar(user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR))]):
    return service.catalogo(user)


# ------------------------------------------------------------------ relatório de um órgão
@router.post("/tabela/exportar")
def exportar_tabela(dados: TabelaExportarIn,
                    _user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_EXPORTAR))]):
    """PDF ou Excel de uma tabela das telas (Datasets, PDA, Atualizações, Organizações), com as
    linhas que o usuário vê — filtros e ordenação da tela, todas as páginas (ADR-0031)."""
    try:
        conteudo, media_type, arquivo = service.exportar_tabela(dados)
    except service.ErroRelatorio as exc:
        raise _erro(exc) from exc
    return Response(conteudo, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


@router.get("/por-orgao/orgaos", response_model=list[OrgaoOpcaoOut])
def orgaos(db: DbSession, user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR))]):
    """Órgãos que o usuário pode escolher (escopo de órgão dele)."""
    return service.orgaos_disponiveis(db, user)


@router.get("/por-orgao/{orgao}/previa", response_model=RelatorioOrgaoOut)
def previa_orgao(orgao: int, db: DbSession,
                 user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR))],
                 relatorios: Annotated[list[str] | None, Query()] = None):
    """Prévia do relatório de um órgão: uma seção por item escolhido (?relatorios=orgaos&
    relatorios=pda&...; "orgaos" = resumo do órgão, sempre a primeira seção)."""
    try:
        return service.previa_orgao(db, orgao, relatorios or [], user)
    except service.ErroRelatorio as exc:
        raise _erro(exc) from exc


@router.get("/por-orgao/{orgao}/exportar")
def exportar_orgao(orgao: int, db: DbSession,
                   user: Annotated[UsuarioAtual, Depends(require(P.RELATORIOS_ACESSAR,
                                                                 P.RELATORIOS_EXPORTAR))],
                   relatorios: Annotated[list[str] | None, Query()] = None,
                   formato: Annotated[str, Query(pattern="^(xlsx|csv|pdf)$")] = "pdf"):
    """Arquivo do relatório de um órgão (itens escolhidos): PDF com seções, XLSX com
    uma aba por seção ou CSV com as seções em sequência."""
    try:
        conteudo, media_type, arquivo = service.exportar_orgao(db, orgao, relatorios or [],
                                                               formato, user)
    except service.ErroRelatorio as exc:
        raise _erro(exc) from exc
    return Response(conteudo, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


# ------------------------------------------------------------------ relatórios gerais
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
             formato: Annotated[str, Query(pattern="^(xlsx|csv|pdf)$")] = "xlsx"):
    try:
        conteudo, media_type, arquivo = service.exportar(db, nome, formato, user)
    except service.ErroRelatorio as exc:
        raise _erro(exc) from exc
    return Response(conteudo, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})
