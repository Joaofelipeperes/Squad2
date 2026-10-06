from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.integrations.ai.base import AIProviderError
from app.modules.assistente import service
from app.modules.ia.gateway import IANaoConfigurada

router = APIRouter()


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=2, max_length=1000)


class RespostaOut(BaseModel):
    resposta: str
    modelo: str


@router.post("/perguntar", response_model=RespostaOut)
def perguntar(body: PerguntaIn, db: DbSession,
              user: UsuarioAtual = Depends(require(P.ASSISTENTE_USAR))):
    try:
        resp, _perfil, _fb = service.perguntar(db, body.pergunta, user)
    except IANaoConfigurada as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return RespostaOut(resposta=resp.text, modelo=resp.model)
