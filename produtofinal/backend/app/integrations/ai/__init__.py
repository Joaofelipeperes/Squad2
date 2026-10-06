"""Camada de IA plugável.

    base.py        contrato AIProvider + tipos de requisição/resposta (independe de fornecedor)
    registry.py    catálogo de adaptadores; @register_provider adiciona um novo tipo
    providers/     um arquivo por fornecedor (gemini, ollama, openai_compat, mock)
    policy.py      tarefas de IA e a regra de proteção de dados sensíveis (LGPD)

Os módulos de negócio NUNCA importam um adaptador diretamente: eles chamam
app.modules.ia.gateway.AIGateway.chat(tarefa, requisição), que resolve qual perfil de
provedor está vinculado àquela tarefa na página de configuração.
"""
from app.integrations.ai.providers import gemini, mock, ollama, openai_compat  # noqa: F401  (registro)
