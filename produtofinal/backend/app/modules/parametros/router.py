from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.parametros.catalogo import CATALOGO
from app.modules.parametros.models import Parametro

router = APIRouter()


class ParametroOut(BaseModel):
    chave: str
    rotulo: str
    descricao: str
    valor: Any
    padrao: Any
    pbi: str


class ParametroIn(BaseModel):
    valor: Any


def obter(db, chave: str):
    """Uso pelos outros módulos: obter(db, 'janela_alerta_prazo_dias')."""
    p = db.get(Parametro, chave)
    return p.valor if p else CATALOGO[chave].padrao


@router.get("", response_model=list[ParametroOut],
            dependencies=[Depends(require(P.PARAMETROS_ACESSAR))])
def listar(db: DbSession):
    return [ParametroOut(chave=d.chave, rotulo=d.rotulo, descricao=d.descricao,
                         valor=obter(db, d.chave), padrao=d.padrao, pbi=d.pbi)
            for d in CATALOGO.values()]


@router.put("/{chave}", response_model=ParametroOut)
def alterar(chave: str, body: ParametroIn, db: DbSession,
            user: UsuarioAtual = Depends(require(P.PARAMETROS_EDITAR))):
    d = CATALOGO.get(chave)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parâmetro inexistente.")
    if type(body.valor) is not type(d.padrao):
        raise HTTPException(422,
                            f"Tipo esperado: {type(d.padrao).__name__}.")
    p = db.get(Parametro, chave) or Parametro(chave=chave)
    p.valor, p.alterado_por = body.valor, user.email
    db.add(p)
    db.commit()
    return ParametroOut(chave=d.chave, rotulo=d.rotulo, descricao=d.descricao, valor=p.valor,
                        padrao=d.padrao, pbi=d.pbi)
