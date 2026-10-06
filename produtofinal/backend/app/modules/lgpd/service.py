"""Módulo LGPD — responsável: Luiza. Pipeline da varredura (US11):

    1. leitura do recurso tabular (PBI-32)
    2. detectores DETERMINÍSTICOS: CPF/CNPJ com dígito verificador, e-mail, telefone, CEP (PBI-33)
       → não dependem de IA; funcionam mesmo sem chave da SECTI
    3. colunas AMBÍGUAS (nome, endereço, texto livre) → classificar_colunas_ambiguas() abaixo,
       que usa a tarefa de IA CLASSIFICACAO_DADO_PESSOAL (política: só modelo LOCAL)
    4. score de confiança + prioridade (PBI-86, PBI-36) → Achado
"""
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.integrations.ai.base import ChatMessage, ChatRequest
from app.integrations.ai.policy import TarefaIA
from app.modules.ia.gateway import AIGateway


@dataclass
class AmostraColuna:
    nome: str
    valores: list[str]  # poucas linhas (ex.: 10); nunca persistidas


@dataclass
class ClassificacaoColuna:
    coluna: str
    tipo: str | None     # None = não é dado pessoal
    confianca: int


def detectar_por_regras(coluna: AmostraColuna) -> ClassificacaoColuna | None:
    """PBI-33 — implementar: regex + validação de dígito verificador."""
    raise NotImplementedError


_PROMPT = (
    "Você classifica colunas de planilhas publicadas em portal de dados abertos. Para cada coluna, "
    "diga se contém dado pessoal de pessoa física identificável. Tipos: nome, endereco, "
    "data_nascimento, outro_pessoal, ou null. Responda APENAS JSON no formato "
    '{"colunas":[{"coluna":"...","tipo":"nome|endereco|data_nascimento|outro_pessoal|null",'
    '"confianca":0-100}]}'
)


def classificar_colunas_ambiguas(db: Session, colunas: list[AmostraColuna]) -> list[ClassificacaoColuna]:
    """Etapa 3 — delega ao modelo vinculado à tarefa de classificação (local por política)."""
    if not colunas:
        return []
    corpo = [{"coluna": c.nome, "amostra": c.valores[:10]} for c in colunas]
    resp, _perfil, _fb = AIGateway(db).chat(TarefaIA.CLASSIFICACAO_DADO_PESSOAL, ChatRequest(
        messages=[ChatMessage(role="system", content=_PROMPT),
                  ChatMessage(role="user", content=json.dumps(corpo, ensure_ascii=False))],
        json_mode=True, temperature=0,
    ))
    try:
        itens = json.loads(resp.text).get("colunas", [])
    except (json.JSONDecodeError, AttributeError):
        return []  # resposta inválida → nenhuma classificação (a regra determinística prevalece)
    return [ClassificacaoColuna(coluna=i.get("coluna", ""),
                                tipo=None if i.get("tipo") in (None, "null") else i["tipo"],
                                confianca=int(i.get("confianca", 0))) for i in itens]
