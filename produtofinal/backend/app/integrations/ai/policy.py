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


@dataclass(frozen=True)
class MetaTarefa:
    rotulo: str
    descricao: str
    sensivel: bool
    user_story: str


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
        descricao="Segunda etapa da varredura: avalia colunas ambíguas (nomes, endereços, texto "
                  "livre) que as regras determinísticas não resolvem. Recebe amostras reais.",
        sensivel=True,
        user_story="US11",
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
