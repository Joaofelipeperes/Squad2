"""Google Gemini (API REST generateContent) — modelo comercial previsto pela SECTI."""
from app.integrations.ai.base import AIProvider, ChatRequest, ChatResponse
from app.integrations.ai.providers._http import get_json, post_json
from app.integrations.ai.registry import register_provider


@register_provider
class GeminiProvider(AIProvider):
    kind = "gemini"
    label = "Google Gemini"
    description = "Modelo comercial da Google. Chave cedida pela SECTI para esta aplicação."
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"
    requires_api_key = True
    local_by_default = False
    suggested_models = ["gemini-2.5-flash", "gemini-2.5-pro"]

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.config.api_key or ""}

    def chat(self, request: ChatRequest) -> ChatResponse:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in request.messages if m.role != "system"
        ]
        gen_cfg: dict = {
            "temperature": self._temperature(request),
            "maxOutputTokens": self._max_tokens(request),
        }
        if request.json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        body: dict = {"contents": contents, "generationConfig": gen_cfg}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"{self.base_url}/models/{self.config.model}:generateContent"
        data, latency = post_json(url, json=body, headers=self._headers(),
                                  timeout=self.config.timeout_s)
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        usage = data.get("usageMetadata", {})
        return ChatResponse(
            text="".join(p.get("text", "") for p in parts),
            model=self.config.model,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            latency_ms=latency,
        )

    def list_models(self) -> list[str]:
        data = get_json(f"{self.base_url}/models", headers=self._headers(),
                        timeout=self.config.timeout_s)
        return sorted(
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )
