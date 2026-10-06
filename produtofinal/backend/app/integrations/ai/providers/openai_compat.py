"""Qualquer servidor com API compatível com OpenAI (/v1/chat/completions).

Cobre, com um único adaptador: vLLM, LM Studio, llama.cpp server, LocalAI (locais) e
serviços comerciais que expõem essa mesma interface. Marque "execução local" no perfil
quando o servidor estiver na infraestrutura do Estado.
"""
from app.integrations.ai.base import AIProvider, ChatRequest, ChatResponse, FieldSpec
from app.integrations.ai.providers._http import get_json, post_json
from app.integrations.ai.registry import register_provider


@register_provider
class OpenAICompatibleProvider(AIProvider):
    kind = "openai_compat"
    label = "Compatível com OpenAI"
    description = "vLLM, LM Studio, llama.cpp, LocalAI ou serviço comercial com a mesma API."
    default_base_url = "http://localhost:8000/v1"
    requires_api_key = False  # servidores locais geralmente dispensam; comerciais exigem
    local_by_default = False
    suggested_models = []

    @classmethod
    def fields(cls) -> list[FieldSpec]:
        return [
            FieldSpec(name="base_url", label="URL base", required=True,
                      placeholder=cls.default_base_url, help="Deve terminar em /v1."),
            FieldSpec(name="model", label="Modelo", required=True),
            FieldSpec(name="api_key", label="Chave de API", secret=True,
                      help="Opcional para servidores locais."),
        ]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}

    def chat(self, request: ChatRequest) -> ChatResponse:
        body: dict = {
            "model": self.config.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": self._temperature(request),
            "max_tokens": self._max_tokens(request),
        }
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}
        data, latency = post_json(f"{self.base_url}/chat/completions", json=body,
                                  headers=self._headers(), timeout=self.config.timeout_s)
        usage = data.get("usage") or {}
        return ChatResponse(
            text=(data.get("choices") or [{}])[0].get("message", {}).get("content", "") or "",
            model=data.get("model", self.config.model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=latency,
        )

    def list_models(self) -> list[str]:
        data = get_json(f"{self.base_url}/models", headers=self._headers(),
                        timeout=self.config.timeout_s)
        return sorted(m["id"] for m in data.get("data", []))
