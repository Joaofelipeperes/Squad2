"""Ollama — execução LOCAL de modelos abertos (Llama, Qwen, Gemma, Mistral...).

Raciocínio ("thinking"): modelos como Qwen3 e Qwen3.5 pensam antes de responder, o que em CPU deixa
cada chamada muito lenta e pode quebrar a resposta JSON. O adaptador pede `think: false`; se o
modelo não aceitar o parâmetro (ex.: Qwen2.5), refaz a chamada sem ele e lembra o modelo até o
processo reiniciar. Um bloco <think>...</think> que venha no texto é descartado.

Embeddings: `/api/embed` (ex.: bge-m3), usados pelo filtro semântico da varredura LGPD.
"""
import re

from app.integrations.ai.base import (
    AIProvider,
    AIProviderError,
    ChatRequest,
    ChatResponse,
    EmbedResponse,
)
from app.integrations.ai.providers._http import get_json, post_json
from app.integrations.ai.registry import register_provider

_SEM_THINK: set[str] = set()  # modelos que recusaram o parâmetro `think` (memória do processo)
_BLOCO_THINK = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)


def _recusou_think(erro: AIProviderError) -> bool:
    texto = str(erro).lower()
    return "http 4" in texto and "think" in texto


@register_provider
class OllamaProvider(AIProvider):
    kind = "ollama"
    label = "Ollama (local)"
    description = "Modelos abertos rodando na própria infraestrutura. Nenhum dado sai do servidor."
    default_base_url = "http://localhost:11434"
    requires_api_key = False
    local_by_default = True
    suggested_models = ["qwen2.5:7b-instruct", "qwen3:8b", "qwen3.5:9b", "bge-m3"]

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
        url = f"{self.base_url}/api/chat"
        com_think = self.config.model not in _SEM_THINK
        if com_think:
            body["think"] = False
        try:
            data, latency = post_json(url, json=body, headers=None, timeout=self.config.timeout_s)
        except AIProviderError as exc:
            if not (com_think and _recusou_think(exc)):
                raise
            _SEM_THINK.add(self.config.model)
            body.pop("think")
            data, latency = post_json(url, json=body, headers=None, timeout=self.config.timeout_s)
        texto = data.get("message", {}).get("content", "") or ""
        return ChatResponse(
            text=_BLOCO_THINK.sub("", texto),
            model=data.get("model", self.config.model),
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            latency_ms=latency,
        )

    def embed(self, textos: list[str]) -> EmbedResponse:
        data, latency = post_json(f"{self.base_url}/api/embed",
                                  json={"model": self.config.model, "input": textos},
                                  headers=None, timeout=self.config.timeout_s)
        vetores = data.get("embeddings") or []
        if len(vetores) != len(textos):
            raise AIProviderError(f"O modelo {self.config.model} não devolveu embeddings "
                                  "(é um modelo de embeddings, como o bge-m3?).")
        return EmbedResponse(vectors=vetores, model=data.get("model", self.config.model),
                             input_tokens=data.get("prompt_eval_count"), latency_ms=latency)

    def list_models(self) -> list[str]:
        data = get_json(f"{self.base_url}/api/tags", headers=None, timeout=self.config.timeout_s)
        return sorted(m["name"] for m in data.get("models", []))
