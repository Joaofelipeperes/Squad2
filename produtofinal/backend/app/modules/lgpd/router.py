"""Rotas do módulo lgpd (tela Riscos de Dados Pessoais).

Permissões (app/core/permissoes.py): lgpd.acessar para ler, lgpd.triar para decidir achados,
lgpd.varrer para pedir varreduras, lgpd.aprovar_correcao para gerar a prévia, publicar no CKAN,
descartar e reverter a anonimização (US26).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi import status as http
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.deps import DbSession, UsuarioAtual, require
from app.core.permissoes import P
from app.modules.lgpd import correcoes, service
from app.modules.lgpd.schemas import (
    AchadoDetalheOut,
    AchadosOut,
    AprovarCorrecaoIn,
    CorrecaoIn,
    CorrecaoOut,
    CorrecoesOut,
    DecisaoIn,
    PedidoVarreduraIn,
    PedidoVarreduraOut,
    ReverterCorrecaoIn,
    VarredurasOut,
)

router = APIRouter()


def _erro(exc: service.ErroLgpd) -> HTTPException:
    codigo = (404 if isinstance(exc, service.NaoEncontrado)
              else 409 if isinstance(exc, correcoes.Conflito) else 422)
    return HTTPException(codigo, str(exc))


def _vazio(v: str | None) -> str | None:
    return (v.strip() or None) if v is not None else None


@router.get("/achados", response_model=AchadosOut)
def listar(db: DbSession, user: UsuarioAtual = Depends(require(P.LGPD_ACESSAR)),
           prioridade: str | None = None, tipo: str | None = None, orgao: str | None = None,
           status: str | None = None):
    return service.listar_achados(db, user, prioridade=_vazio(prioridade), tipo=_vazio(tipo),
                                  orgao=_vazio(orgao), status=_vazio(status))


@router.get("/achados/{achado_id}", response_model=AchadoDetalheOut)
def detalhe(achado_id: int, db: DbSession, user: UsuarioAtual = Depends(require(P.LGPD_ACESSAR))):
    try:
        return service.obter_achado(db, achado_id, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)


@router.post("/achados/{achado_id}/decisao", response_model=AchadoDetalheOut)
def decidir(achado_id: int, body: DecisaoIn, db: DbSession,
            user: UsuarioAtual = Depends(require(P.LGPD_TRIAR))):
    """PBI-40 — confirmado, falso positivo, tratado ou de volta para revisão."""
    try:
        return service.decidir(db, achado_id, body, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)


@router.get("/varreduras", response_model=VarredurasOut)
def varreduras(db: DbSession, user: UsuarioAtual = Depends(require(P.LGPD_ACESSAR)),
               limite: int = 30):
    return service.listar_varreduras(db, user, limite)


@router.post("/varreduras/cancelar")
def cancelar_fila(db: DbSession, user: UsuarioAtual = Depends(require(P.LGPD_VARRER))):
    """Cancela as varreduras na fila que ainda não começaram."""
    return {"canceladas": service.cancelar_fila(db, user)}


@router.post("/varreduras", response_model=PedidoVarreduraOut, status_code=http.HTTP_202_ACCEPTED)
def pedir_varredura(body: PedidoVarreduraIn, bg: BackgroundTasks, db: DbSession,
                    user: UsuarioAtual = Depends(require(P.LGPD_VARRER))):
    """Coloca os recursos do escopo na fila e varre em segundo plano (pode levar minutos)."""
    try:
        # "pendentes" pode pegar o portal inteiro: no máximo N por pedido (como o job)
        limite = get_settings().lgpd_varredura_max_recursos if body.escopo == "pendentes" else None
        criadas, ja = service.solicitar(db, body.escopo, body.id, user, limite=limite)
    except service.ErroLgpd as exc:
        raise _erro(exc)
    if criadas:
        bg.add_task(service.executar_fila, [v.id for v in criadas])
    return service.pedido_out(db, criadas, ja)


# ------------------------------------------------------------------ anonimização (US26)
@router.get("/correcoes", response_model=CorrecoesOut)
def listar_correcoes(db: DbSession, user: UsuarioAtual = Depends(require(P.LGPD_ACESSAR)),
                     limite: int = 30):
    return correcoes.listar(db, user, limite)


@router.get("/correcoes/{correcao_id}", response_model=CorrecaoOut)
def obter_correcao(correcao_id: int, db: DbSession,
                   user: UsuarioAtual = Depends(require(P.LGPD_ACESSAR))):
    """Inclui exemplos JÁ anonimizados, lidos do arquivo da prévia (PBI-91)."""
    try:
        return correcoes.obter(db, correcao_id, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)


@router.post("/correcoes", response_model=CorrecaoOut, status_code=http.HTTP_202_ACCEPTED)
def gerar_previa(body: CorrecaoIn, bg: BackgroundTasks, db: DbSession,
                 user: UsuarioAtual = Depends(require(P.LGPD_APROVAR_CORRECAO))):
    """Gera a prévia em segundo plano (baixa o original e guarda a cópia fora do banco)."""
    try:
        c = correcoes.solicitar_previa(db, body, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)
    bg.add_task(correcoes.executar_previa, c.id)
    return correcoes.obter(db, c.id, user)


@router.get("/correcoes/{correcao_id}/arquivo-previa")
def baixar_previa(correcao_id: int, db: DbSession,
                  user: UsuarioAtual = Depends(require(P.LGPD_APROVAR_CORRECAO))):
    """Arquivo JÁ anonimizado da prévia (o original nunca é servido pela API)."""
    try:
        caminho, nome = correcoes.arquivo_previa(db, correcao_id, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)
    return FileResponse(caminho, filename=f"previa_anonimizada_{nome}",
                        media_type="application/octet-stream")


@router.post("/correcoes/{correcao_id}/aprovar", response_model=CorrecaoOut)
def aprovar_correcao(correcao_id: int, body: AprovarCorrecaoIn, db: DbSession,
                     user: UsuarioAtual = Depends(require(P.LGPD_APROVAR_CORRECAO))):
    """PBI-92/93 — publica no CKAN o arquivo da prévia (exige GDA_CKAN_WRITE_ENABLED)."""
    try:
        return correcoes.aprovar(db, correcao_id, body.justificativa, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)


@router.post("/correcoes/{correcao_id}/descartar", response_model=CorrecaoOut)
def descartar_correcao(correcao_id: int, db: DbSession,
                       user: UsuarioAtual = Depends(require(P.LGPD_APROVAR_CORRECAO))):
    try:
        return correcoes.descartar(db, correcao_id, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)


@router.post("/correcoes/{correcao_id}/reverter", response_model=CorrecaoOut)
def reverter_correcao(correcao_id: int, body: ReverterCorrecaoIn, db: DbSession,
                      user: UsuarioAtual = Depends(require(P.LGPD_APROVAR_CORRECAO))):
    """PBI-94 — restaura o original no CKAN."""
    try:
        return correcoes.reverter(db, correcao_id, body.motivo, user)
    except service.ErroLgpd as exc:
        raise _erro(exc)
