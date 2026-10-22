from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.inventario import service
from app.modules.inventario.models import Coleta
from app.modules.inventario.schemas import ColetaOut, DatasetDetalheOut, DatasetsOut

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


# ------------------------------------------------------------------ tela Datasets (PBI-83)
def _vazio(valor: str | None) -> str | None:
    return (valor.strip() or None) if valor is not None else None


@router.get("/datasets", response_model=DatasetsOut)
def listar_datasets(db: DbSession, user: UsuarioAtual = Depends(require(P.INVENTARIO_ACESSAR)),
                    busca: str | None = None, orgao: str | None = None,
                    formato: str | None = None, situacao: str | None = None):
    """Inventário de datasets do portal (tela Datasets) com filtros. `orgao` = id da organização
    (vazio = sem filtro)."""
    orgao_txt = _vazio(orgao)
    if orgao_txt is not None and not orgao_txt.isdigit():
        raise HTTPException(422, "orgao: informe o id (número inteiro) da organização.")
    return service.listar_datasets(db, user, busca=_vazio(busca),
                                   orgao=int(orgao_txt) if orgao_txt else None,
                                   formato=_vazio(formato), situacao=_vazio(situacao))


@router.get("/datasets/{dataset_id}", response_model=DatasetDetalheOut)
def obter_dataset(dataset_id: int, db: DbSession,
                  user: UsuarioAtual = Depends(require(P.INVENTARIO_ACESSAR))):
    """Detalhe do dataset com a lista de recursos atuais."""
    try:
        return service.obter_dataset(db, dataset_id, user)
    except service.DatasetNaoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
