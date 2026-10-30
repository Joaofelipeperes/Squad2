from datetime import datetime

from pydantic import BaseModel, Field


class PerfilCkanIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    auditoria_base_url: str | None = Field(default=None, max_length=500)
    # None = manter o token atual; "" = remover; texto = substituir.
    auditoria_api_token: str | None = None


class PerfilCkanOut(BaseModel):
    id: int
    nome: str
    base_url: str
    auditoria_base_url: str | None
    tem_token: bool                       # há token de auditoria salvo
    auditoria_api_token_dica: str | None  # ex.: ••••1a2b (nunca o token em claro)
    selecionado: bool                     # é o CKAN em uso agora
    atualizado_em: datetime
