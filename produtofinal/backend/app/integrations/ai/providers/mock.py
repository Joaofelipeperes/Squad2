"""Provedor simulado — para desenvolvimento e testes enquanto a chave da SECTI não chega."""
import json

from app.integrations.ai.base import AIProvider, ChatRequest, ChatResponse, FieldSpec
from app.integrations.ai.registry import register_provider


@register_provider
class MockProvider(AIProvider):
    kind = "mock"
    label = "Simulado (desenvolvimento)"
    description = "Respostas fixas, sem rede. Útil para desenvolver telas e testes automatizados."
    local_by_default = True
    suggested_models = ["eco"]

    @classmethod
    def fields(cls) -> list[FieldSpec]:
        return [FieldSpec(name="model", label="Modelo", required=True, placeholder="eco")]

    def chat(self, request: ChatRequest) -> ChatResponse:
        last = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        text = (json.dumps({"resposta": last[:200], "simulado": True}, ensure_ascii=False)
                if request.json_mode else f"[simulado] Pergunta recebida: {last[:200]}")
        return ChatResponse(text=text, model=self.config.model, input_tokens=len(last) // 4,
                            output_tokens=len(text) // 4, latency_ms=1)

    def list_models(self) -> list[str]:
        return ["eco"]
