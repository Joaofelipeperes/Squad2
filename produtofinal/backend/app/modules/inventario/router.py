from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.inventario import service
from app.modules.inventario.models import Coleta
from app.modules.inventario.schemas import ColetaOut

router = APIRouter()


@router.get("/coletas/ultima", response_model=ColetaOut | None)
def ultima(db: DbSession, _: CurrentUser):
    """Data/hora da última coleta, exibida na topbar de todas as telas (PBI-58) — por isso
    basta estar autenticado."""
    return service.ultima_coleta(db)


@router.get("/coletas", response_model=list[ColetaOut],
            dependencies=[Depends(require(P.INVENTARIO_ACESSAR))])
def historico(db: DbSession, limite: int = 30):
    return db.scalars(select(Coleta).order_by(Coleta.id.desc()).limit(limite)).all()


@router.post("/coletas", response_model=ColetaOut, status_code=202)
def forcar_coleta(bg: BackgroundTasks, db: DbSession,
                  user: UsuarioAtual = Depends(require(P.INVENTARIO_COLETAR))):
    """Botão 'Atualizar dados' (PBI-74)."""
    try:
        c = service.iniciar(db, origem="manual", solicitante=user.email)
    except service.ColetaEmAndamento as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    bg.add_task(service.executar, c.id)
    return c
