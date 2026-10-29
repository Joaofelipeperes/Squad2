from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.integrations.ai.base import AIProviderError
from app.modules.assistente import service
from app.modules.ia.gateway import IANaoConfigurada

router = APIRouter()


class MensagemIn(BaseModel):
    papel: Literal["user", "assistant"]
    texto: str = Field(max_length=4000)


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=2, max_length=1000)
    # Conversa anterior, mantida só no navegador (nada é gravado). Usada para continuações
    # como "e o prazo dele?"; o serviço aproveita só as últimas mensagens.
    historico: list[MensagemIn] = Field(default_factory=list, max_length=20)


class FonteOut(BaseModel):
    tipo: str  # dataset | orgao | pda
    id: str
    titulo: str


class RespostaOut(BaseModel):
    resposta: str
    modelo: str
    fontes: list[FonteOut] = []


@router.post("/perguntar", response_model=RespostaOut)
def perguntar(body: PerguntaIn, db: DbSession,
              user: UsuarioAtual = Depends(require(P.ASSISTENTE_USAR))):
    historico = [service.MensagemAnterior(m.papel, m.texto) for m in body.historico]
    try:
        resp, _perfil, _fb, fontes = service.perguntar(db, body.pergunta, user, historico)
    except IANaoConfigurada as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return RespostaOut(resposta=resp.text, modelo=resp.model,
                       fontes=[FonteOut(tipo=f.tipo, id=f.id, titulo=f.titulo) for f in fontes])
