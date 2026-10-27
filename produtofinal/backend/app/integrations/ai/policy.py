"""Tarefas de IA da solução e a política de uso de dados sensíveis.

Cada tarefa é vinculada, na página de configuração, a um perfil de provedor (+ fallback opcional).
Tarefas que processam dado pessoal (`sensivel=True`) só aceitam perfis marcados como execução
LOCAL — o conteúdo não sai da infraestrutura. A exceção exige a variável
GDA_IA_PERMITIR_EXTERNO_PARA_SENSIVEL=true, decisão que cabe à CGE-GO, não ao time.
"""
from dataclasses import dataclass
from enum import StrEnum


class TarefaIA(StrEnum):
    ASSISTENTE = "assistente"                        # US28 — Assistente GEDA
    CLASSIFICACAO_DADO_PESSOAL = "classificacao_dp"  # US11 — apoio à varredura (casos ambíguos)
    EMBEDDINGS_DADO_PESSOAL = "embeddings_dp"        # US11 — filtro semântico da varredura


@dataclass(frozen=True)
class MetaTarefa:
    rotulo: str
    descricao: str
    sensivel: bool
    user_story: str
    tipo: str = "chat"  # chat | embeddings (o perfil precisa ser de um modelo de embeddings)


TAREFAS: dict[TarefaIA, MetaTarefa] = {
    TarefaIA.ASSISTENTE: MetaTarefa(
        rotulo="Assistente GEDA",
        descricao="Responde perguntas em linguagem natural sobre órgãos, bases, prazos e alertas. "
                  "Recebe apenas indicadores agregados — nunca o conteúdo de achados LGPD.",
        sensivel=False,
        user_story="US28",
    ),
    TarefaIA.CLASSIFICACAO_DADO_PESSOAL: MetaTarefa(
        rotulo="Classificação de dados pessoais",
        descricao="Segunda etapa da varredura: confirma se um texto contém endereço e extrai o "
                  "trecho (o que as regras determinísticas não resolvem). Recebe textos reais. "
                  "Ex.: qwen2.5:7b-instruct, qwen3:8b ou qwen3.5:9b no Ollama.",
        sensivel=True,
        user_story="US11",
    ),
    TarefaIA.EMBEDDINGS_DADO_PESSOAL: MetaTarefa(
        rotulo="Filtro semântico da varredura LGPD",
        descricao="Modelo de embeddings (ex.: bge-m3 no Ollama) que escolhe quais células de texto "
                  "vão ao modelo de classificação de endereço. Recebe textos reais dos recursos.",
        sensivel=True,
        user_story="US11",
        tipo="embeddings",
    ),
}


class PoliticaIAViolada(PermissionError):
    pass


def verificar(tarefa: TarefaIA, perfil_local: bool, permitir_externo: bool) -> None:
    if TAREFAS[tarefa].sensivel and not perfil_local and not permitir_externo:
        raise PoliticaIAViolada(
            f"A tarefa '{TAREFAS[tarefa].rotulo}' processa dados pessoais e só pode usar um "
            "provedor de execução local."
        )
