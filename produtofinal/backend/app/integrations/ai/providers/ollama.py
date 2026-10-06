"""Ollama — execução LOCAL de modelos abertos (Llama, Qwen, Gemma, Mistral...)."""
from app.integrations.ai.base import AIProvider, ChatRequest, ChatResponse
from app.integrations.ai.providers._http import get_json, post_json
from app.integrations.ai.registry import register_provider


@register_provider
class OllamaProvider(AIProvider):
    kind = "ollama"
    label = "Ollama (local)"
    description = "Modelos abertos rodando na própria infraestrutura. Nenhum dado sai do servidor."
    default_base_url = "http://localhost:11434"
    requires_api_key = False
    local_by_default = True
    suggested_models = ["qwen2.5:7b", "llama3.1:8b", "gemma2:9b"]

    def chat(self, request: ChatRequest) -> ChatResponse:
        body: dict = {
            "model": self.config.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": False,
            "options": {
                "temperature": self._temperature(request),
                "num_predict": self._max_tokens(request),
            },
        }
        if request.json_mode:
            body["format"] = "json"
        data, latency = post_json(f"{self.base_url}/api/chat", json=body, headers=None,
                                  timeout=self.config.timeout_s)
        return ChatResponse(
            text=data.get("message", {}).get("content", ""),
            model=data.get("model", self.config.model),
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            latency_ms=latency,
        )

    def list_models(self) -> list[str]:
        data = get_json(f"{self.base_url}/api/tags", headers=None, timeout=self.config.timeout_s)
        return sorted(m["name"] for m in data.get("models", []))
