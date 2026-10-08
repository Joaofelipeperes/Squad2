"""Rotas do módulo pda (/api/v1/pda). Só valida a entrada e delega ao service."""
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.pda import regras, service
from app.modules.pda.schemas import BaseOut, BasesOut, ImportacaoResumoOut, PlanoOut, VinculosOut

router = APIRouter()
_FLAGS_PRAZO = {"vencido", "proximo"}


@contextmanager
def _erros_http() -> Iterator[None]:
    try:
        yield
    except service.ErroPda as exc:
        raise HTTPException(exc.status_http, str(exc)) from exc


def _data_form(valor: str | None, campo: str) -> date | None:
    if valor is None or not valor.strip():
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        raise HTTPException(422, f"{campo}: use o formato aaaa-mm-dd.") from None


def _vazio(valor: str | None) -> str | None:
    return (valor.strip() or None) if valor is not None else None


# ------------------------------------------------------------------ planos (PDAs)
@router.get("/planos", response_model=list[PlanoOut])
def listar_planos(db: DbSession,
                  user: Annotated[UsuarioAtual, Depends(require(P.PDA_ACESSAR))]):
    """PDAs cadastrados (vigente primeiro)."""
    return service.listar_planos(db, user)


@router.post("/planos", response_model=ImportacaoResumoOut, status_code=status.HTTP_201_CREATED)
def importar_plano(
    db: DbSession,
    nome: Annotated[str, Form()],
    arquivo: Annotated[UploadFile, File()],
    user: Annotated[UsuarioAtual, Depends(require(P.PDA_GERENCIAR_PLANOS))],
    vigencia_inicio: Annotated[str | None, Form()] = None,
    vigencia_fim: Annotated[str | None, Form()] = None,
    definir_vigente: Annotated[bool, Form()] = False,
):
    """PBI-12 — importa a planilha de um PDA (.xlsx ou .csv, até 5 MB). multipart/form-data."""
    if regras.extensao_valida(arquivo.filename) is None:
        raise HTTPException(422, "Formato não suportado: envie a planilha do PDA em .xlsx ou .csv.")
    conteudo = arquivo.file.read(regras.TAMANHO_MAXIMO + 1)
    if len(conteudo) > regras.TAMANHO_MAXIMO:
        raise HTTPException(413, "Arquivo maior que 5 MB.")
    inicio = _data_form(vigencia_inicio, "Início da vigência")
    fim = _data_form(vigencia_fim, "Fim da vigência")
    with _erros_http():
        return service.importar_plano(
            db, nome=nome, vigencia_inicio=inicio, vigencia_fim=fim,
            definir_vigente=definir_vigente, arquivo_nome=arquivo.filename or "",
            conteudo=conteudo, importado_por=user.nome)


@router.put("/planos/{plano_id}/vigente", response_model=PlanoOut,
            dependencies=[Depends(require(P.PDA_GERENCIAR_PLANOS))])
def definir_vigente(plano_id: int, db: DbSession):
    """Define o PDA vigente (rege a tela e os indicadores de gestão)."""
    with _erros_http():
        return service.definir_vigente(db, plano_id)


@router.delete("/planos/{plano_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response, dependencies=[Depends(require(P.PDA_GERENCIAR_PLANOS))])
def excluir_plano(plano_id: int, db: DbSession):
    """Exclui um PDA não vigente e suas bases."""
    with _erros_http():
        service.excluir_plano(db, plano_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/planos/{plano_id}/vincular", response_model=VinculosOut,
             dependencies=[Depends(require(P.PDA_EDITAR_VINCULOS))])
def vincular(plano_id: int, db: DbSession):
    """PBI-12/13 — tenta resolver de novo os vínculos pendentes do PDA."""
    with _erros_http():
        return service.resolver_vinculos_pendentes(db, plano_id)


# ------------------------------------------------------------------ bases previstas
@router.get("/bases", response_model=BasesOut)
def listar_bases(
    db: DbSession,
    user: Annotated[UsuarioAtual, Depends(require(P.PDA_ACESSAR))],
    plano_id: int | None = None,
    orgao: str | None = None,
    situacao: str | None = None,
    periodicidade: str | None = None,
    ano: str | None = None,
    prazo: str | None = None,
):
    """PBI-19/20/21 — bases do PDA (vigente, se `plano_id` não for informado) com situação."""
    ano_txt, prazo = _vazio(ano), _vazio(prazo)
    if ano_txt is not None and not ano_txt.isdigit():
        raise HTTPException(422, "ano: informe um número inteiro.")
    if prazo is not None and prazo not in _FLAGS_PRAZO:
        raise HTTPException(422, "prazo: use 'vencido' ou 'proximo'.")
    with _erros_http():
        return service.listar_bases(
            db, user, plano_id=plano_id, orgao=_vazio(orgao), situacao=_vazio(situacao),
            periodicidade=_vazio(periodicidade), ano=int(ano_txt) if ano_txt else None,
            prazo=prazo)


@router.get("/bases/{base_id}", response_model=BaseOut)
def obter_base(base_id: int, db: DbSession,
               user: Annotated[UsuarioAtual, Depends(require(P.PDA_ACESSAR))]):
    """Detalhe de uma base prevista (modal da tela)."""
    with _erros_http():
        return BaseOut.model_validate(service.obter_base(db, base_id, user))
