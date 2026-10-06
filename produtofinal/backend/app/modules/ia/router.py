"""API da página Administração › Modelos de IA. Todas as rotas exigem ia.configurar."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.integrations.ai.base import AIProviderError, ChatMessage, ChatRequest
from app.integrations.ai.policy import PoliticaIAViolada, TarefaIA
from app.modules.ia import service
from app.modules.ia.gateway import AIGateway, IANaoConfigurada
from app.modules.ia.models import PerfilProvedorIA, UsoIA, VinculoTarefaIA
from app.modules.ia.schemas import (
    PerfilIn, PerfilOut, PlaygroundIn, PlaygroundOut, TarefaOut, TesteConexaoIn,
    TesteConexaoOut, TipoProvedorOut, UsoOut, VinculoIn,
)

router = APIRouter(dependencies=[Depends(require(P.IA_CONFIGURAR))])


def _get(db, perfil_id: int) -> PerfilProvedorIA:
    p = db.get(PerfilProvedorIA, perfil_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado.")
    return p


def _salvar(db, body: PerfilIn, atual: PerfilProvedorIA | None = None):
    try:
        return service.to_out(service.salvar_perfil(db, body, atual))
    except (service.ErroConfiguracaoIA, AIProviderError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc))


@router.get("/tipos-provedor", response_model=list[TipoProvedorOut])
def tipos():
    return service.listar_tipos()


@router.get("/perfis", response_model=list[PerfilOut])
def listar(db: DbSession):
    return [service.to_out(p) for p in
            db.scalars(select(PerfilProvedorIA).order_by(PerfilProvedorIA.nome)).all()]


@router.post("/perfis", response_model=PerfilOut, status_code=201)
def criar(body: PerfilIn, db: DbSession):
    if db.scalar(select(PerfilProvedorIA).where(PerfilProvedorIA.nome == body.nome.strip())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um perfil com este nome.")
    return _salvar(db, body)


@router.put("/perfis/{perfil_id}", response_model=PerfilOut)
def atualizar(perfil_id: int, body: PerfilIn, db: DbSession):
    return _salvar(db, body, _get(db, perfil_id))


@router.delete("/perfis/{perfil_id}", status_code=204)
def excluir(perfil_id: int, db: DbSession):
    p = _get(db, perfil_id)
    em_uso = db.scalar(select(VinculoTarefaIA).where(
        (VinculoTarefaIA.perfil_id == p.id) | (VinculoTarefaIA.perfil_fallback_id == p.id)))
    if em_uso:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Perfil vinculado a uma tarefa. Troque o vínculo antes de excluir.")
    db.delete(p)
    db.commit()


@router.post("/testar-conexao", response_model=TesteConexaoOut)
def testar_conexao(body: TesteConexaoIn, db: DbSession):
    return service.testar(db, body)


@router.post("/perfis/{perfil_id}/testar", response_model=TesteConexaoOut)
def testar_perfil(perfil_id: int, db: DbSession):
    return service.testar_resposta(db, _get(db, perfil_id))


@router.get("/tarefas", response_model=list[TarefaOut])
def tarefas(db: DbSession):
    return service.listar_tarefas(db)


@router.put("/tarefas/{tarefa}", response_model=list[TarefaOut])
def vincular(tarefa: TarefaIA, body: VinculoIn, db: DbSession,
             user: UsuarioAtual = Depends(require(P.IA_CONFIGURAR))):
    try:
        service.vincular(db, tarefa, body, user.email)
    except service.ErroConfiguracaoIA as exc:
        raise HTTPException(422, str(exc))
    return service.listar_tarefas(db)


@router.get("/uso", response_model=list[UsoOut])
def uso(db: DbSession, limite: int = 50):
    return db.scalars(select(UsoIA).order_by(UsoIA.momento.desc()).limit(min(limite, 500))).all()


@router.post("/playground", response_model=PlaygroundOut)
def playground(body: PlaygroundIn, db: DbSession):
    try:
        resp, perfil, fb = AIGateway(db).chat(body.tarefa, ChatRequest(
            messages=[ChatMessage(role="user", content=body.mensagem)]))
    except (IANaoConfigurada, PoliticaIAViolada) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return PlaygroundOut(texto=resp.text, perfil=perfil.nome, modelo=resp.model,
                         latencia_ms=resp.latency_ms, usou_fallback=fb)
