"""API da página Administração › Modelos de IA. Todas as rotas exigem ia.configurar."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.integrations.ai.base import AIProviderError, ChatMessage, ChatRequest
from app.integrations.ai.policy import TAREFAS, PoliticaIAViolada, TarefaIA
from app.modules.ia import service
from app.modules.ia.gateway import AIGateway, IANaoConfigurada
from app.modules.ia.models import PerfilProvedorIA
from app.modules.ia.schemas import (
    PerfilIn,
    PerfilOut,
    PlaygroundIn,
    PlaygroundOut,
    TarefaOut,
    TesteConexaoIn,
    TesteConexaoOut,
    TipoProvedorOut,
    UsoOut,
    VinculoIn,
)

router = APIRouter(dependencies=[Depends(require(P.IA_CONFIGURAR))])
# Quem age (auditoria `created_id`/`changed_id`); a permissão já é exigida no router
Configurador = Annotated[UsuarioAtual, Depends(require(P.IA_CONFIGURAR))]


def _get(db, perfil_id: int) -> PerfilProvedorIA:
    p = service.perfil_por_id(db, perfil_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado.")
    return p


def _salvar(db, body: PerfilIn, user: UsuarioAtual, atual: PerfilProvedorIA | None = None):
    try:
        return service.to_out(service.salvar_perfil(db, body, atual, usuario_id=user.id))
    except (service.ErroConfiguracaoIA, AIProviderError) as exc:
        raise HTTPException(422, str(exc))


@router.get("/tipos-provedor", response_model=list[TipoProvedorOut])
def tipos():
    return service.listar_tipos()


@router.get("/perfis", response_model=list[PerfilOut])
def listar(db: DbSession):
    return service.listar_perfis(db)


@router.post("/perfis", response_model=PerfilOut, status_code=201)
def criar(body: PerfilIn, db: DbSession, user: Configurador):
    if service.perfil_por_nome(db, body.nome.strip()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um perfil com este nome.")
    return _salvar(db, body, user)


@router.put("/perfis/{perfil_id}", response_model=PerfilOut)
def atualizar(perfil_id: int, body: PerfilIn, db: DbSession, user: Configurador):
    return _salvar(db, body, user, _get(db, perfil_id))


@router.delete("/perfis/{perfil_id}", status_code=204)
def excluir(perfil_id: int, db: DbSession, user: Configurador):
    """Exclusão lógica (ADR-0019); perfil vinculado a uma tarefa → 409."""
    try:
        service.excluir_perfil(db, _get(db, perfil_id), usuario_id=user.id)
    except service.ErroConfiguracaoIA as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


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
def vincular(tarefa: TarefaIA, body: VinculoIn, db: DbSession, user: Configurador):
    try:
        service.vincular(db, tarefa, body, user.email, usuario_id=user.id)
    except service.ErroConfiguracaoIA as exc:
        raise HTTPException(422, str(exc))
    return service.listar_tarefas(db)


@router.get("/uso", response_model=list[UsoOut])
def uso(db: DbSession, limite: int = 50):
    return service.listar_usos(db, min(limite, 500))


@router.post("/playground", response_model=PlaygroundOut)
def playground(body: PlaygroundIn, db: DbSession):
    if TAREFAS[body.tarefa].tipo != "chat":
        raise HTTPException(status.HTTP_409_CONFLICT, "Tarefa de embeddings: use o botão Testar do "
                                                      "perfil vinculado a ela.")
    try:
        resp, perfil, fb = AIGateway(db).chat(body.tarefa, ChatRequest(
            messages=[ChatMessage(role="user", content=body.mensagem)]))
    except (IANaoConfigurada, PoliticaIAViolada) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return PlaygroundOut(texto=resp.text, perfil=perfil.nome, modelo=resp.model,
                         latencia_ms=resp.latency_ms, usou_fallback=fb)
