"""Rotas do módulo rastreabilidade (US14, US29)."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.rastreabilidade import regras, service
from app.modules.rastreabilidade.schemas import DiffOut, EventosOut

router = APIRouter()


def _vazio(valor: str | None) -> str | None:
    return (valor.strip() or None) if valor is not None else None


@router.get("/eventos", response_model=EventosOut)
def listar_eventos(db: DbSession, user: UsuarioAtual = Depends(require(P.RASTREABILIDADE_ACESSAR)),
                   tipo: str | None = None, orgao: int | None = None,
                   dataset: str | None = None, busca: str | None = None,
                   desde: datetime | None = None, ate: datetime | None = None,
                   ordem: Literal["recentes", "antigos"] = "recentes",
                   limite: int = service.LIMITE_PADRAO):
    """Linha do tempo de alterações (tela Rastreabilidade, PBI-85). `tipo` aceita o código
    (inclusao, alteracao, exclusao, privacao, recurso_atualizado) ou o rótulo da tela; `orgao`
    é o `id` da organização; `dataset` é o ID do CKAN; `busca` procura no título ou nome do
    dataset; `desde`/`ate` em ISO 8601 (com fuso); `ordem` por data: recentes (padrão) ou
    antigos."""
    tipo = _vazio(tipo)
    if tipo and tipo not in regras.TIPOS:
        tipo = next((k for k, v in regras.TIPOS.items() if v == tipo), tipo)
    return service.listar_eventos(db, user, tipo=tipo, orgao=orgao,
                                  dataset=_vazio(dataset), busca=_vazio(busca),
                                  desde=desde, ate=ate, ordem=ordem, limite=limite)


@router.get("/eventos/{evento_id}/diff", response_model=DiffOut)
def diff_evento(evento_id: int, db: DbSession,
                user: UsuarioAtual = Depends(require(P.RASTREABILIDADE_ACESSAR))):
    """Diff linha a linha de uma troca de arquivo (ou upsert no DataStore), lido do CKAN na hora;
    os valores não são gravados na solução."""
    try:
        return service.diff_evento(db, user, evento_id)
    except service.EventoNaoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.DiffIndisponivel as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
