"""Assistente GEDA (US28): o backend monta os FATOS, o modelo só redige a resposta.

Sem banco vetorial: o contexto é um resumo determinístico do inventário da última coleta
(contagens e situação por órgão). Achados LGPD entram apenas como contagem — nunca conteúdo.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import UsuarioAtual, filtrar_por_orgao

from app.integrations.ai.base import ChatMessage, ChatRequest
from app.integrations.ai.policy import TarefaIA
from app.modules.ia.gateway import AIGateway
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.inventario.service import ultima_coleta

SYSTEM = (
    "Você é o Assistente GEDA da Controladoria-Geral do Estado de Goiás. Responda em português, "
    "de forma objetiva, usando SOMENTE os fatos fornecidos no contexto. Se a informação não "
    "estiver no contexto, diga que não há dado na última coleta e sugira a tela do sistema onde "
    "a gerente pode conferir. Nunca invente números, prazos ou nomes de bases."
)


def montar_contexto(db: Session, pergunta: str, user: UsuarioAtual) -> str:
    """Respeita o escopo de órgão: usuário restrito só recebe fatos do próprio órgão."""
    c = ultima_coleta(db)
    if c is None:
        return "Nenhuma coleta do portal foi realizada ainda."
    linhas = [f"Última coleta: {c.finalizada_em or c.iniciada_em:%d/%m/%Y %H:%M} "
              f"(status {c.status})."]
    if not user.restrito_a_orgao:
        linhas.append(f"Totais: {c.total_organizacoes} órgãos, {c.total_datasets} datasets, "
                      f"{c.total_recursos} recursos.")
    # Recorte simples por órgão citado na pergunta (a ser enriquecido pelos módulos pda/atualizacoes)
    p = pergunta.lower()
    orgaos = db.scalars(filtrar_por_orgao(select(Organizacao), Organizacao.ckan_id, user)).all()
    for org in orgaos:
        citado = org.name.lower() in p or org.titulo.lower() in p or (org.sigla or "#").lower() in p
        if citado or user.restrito_a_orgao:
            n_ds = db.scalar(select(func.count()).select_from(Dataset)
                             .where(Dataset.organizacao_id == org.ckan_id, Dataset.ativo_no_portal))
            n_rec = db.scalar(select(func.count()).select_from(Recurso).join(Dataset)
                              .where(Dataset.organizacao_id == org.ckan_id))
            linhas.append(f"Órgão {org.titulo}: {n_ds} datasets ativos, {n_rec} recursos.")
    return "\n".join(linhas)


def perguntar(db: Session, pergunta: str, user: UsuarioAtual):
    contexto = montar_contexto(db, pergunta, user)
    req = ChatRequest(messages=[
        ChatMessage(role="system", content=SYSTEM),
        ChatMessage(role="user", content=f"Contexto:\n{contexto}\n\nPergunta: {pergunta}"),
    ])
    return AIGateway(db).chat(TarefaIA.ASSISTENTE, req)
