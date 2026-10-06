"""Área do órgão publicador. NÃO COMPROMETIDO no Backlog v2 — ver docs/modulos/envio.md.

Toda rota deste módulo deve aplicar o escopo de órgão:
    user = Depends(require(P.ENVIO_ACESSAR))
    stmt = filtrar_por_orgao(select(Dataset), Dataset.organizacao_id, user)
"""
from fastapi import APIRouter

router = APIRouter()
