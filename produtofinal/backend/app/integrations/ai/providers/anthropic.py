"""Anthropic Claude (API REST /v1/messages) — modelo comercial, sem SDK (ADR-0002).

Pensado para o Assistente GEDA com um modelo barato e rápido (família Haiku). Não serve para
tarefas sensíveis: é execução externa, e a política do gateway bloqueia esse uso.

Detalhes da API tratados aqui:
- `system` vai fora da lista de mensagens; a conversa tem de alternar user/assistant e terminar
  em `user` (mensagens seguidas do mesmo papel são juntadas).
- O raciocínio ("thinking") é desligado: o Assistente só redige fatos já calculados, e o
  raciocínio atrasa a primeira palavra da resposta.
- Modelos mais novos recusam `temperature` diferente do padrão (HTTP 400). Nesse caso a chamada é
  refeita sem o parâmetro e o modelo é lembrado até o processo reiniciar.
- A resposta pode trazer blocos que não são texto (ex.: thinking); só os blocos de texto contam.
- Chave de API sem workspace exige o cabeçalho `anthropic-workspace-id`: o ID vai no campo
  adicional "ID do workspace" do perfil (`extra["workspace_id"]`).
"""
from app.integrations.ai.base import (
    AIProvider,
    AIProviderError,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FieldSpec,
)
from app.integrations.ai.providers._http import get_json, post_json
from app.integrations.ai.registry import register_provider

VERSAO_API = "2023-06-01"
_SEM_TEMPERATURA: set[str] = set()  # modelos que recusaram `temperature` (memória do processo)


def _alternar(mensagens: list[ChatMessage]) -> list[dict]:
    """Converte para o formato da API: sem `system`, papéis alternados, começa e termina em user."""
    saida: list[dict] = []
    for m in mensagens:
        if m.role == "system" or not m.content.strip():
            continue
        if saida and saida[-1]["role"] == m.role:
            saida[-1]["content"] += "\n\n" + m.content
        else:
            saida.append({"role": m.role, "content": m.content})
    while saida and saida[0]["role"] != "user":
        saida.pop(0)
    while saida and saida[-1]["role"] != "user":
        saida.pop()
    if not saida:
        raise AIProviderError("A conversa enviada ao Claude não tem mensagem do usuário.")
    return saida


def _recusou_temperatura(erro: AIProviderError) -> bool:
    texto = str(erro).lower()
    return "http 400" in texto and ("temperature" in texto or "top_p" in texto)


@register_provider
class AnthropicProvider(AIProvider):
    kind = "anthropic"
    label = "Anthropic Claude"
    description = ("Modelo comercial da Anthropic. Para o Assistente, prefira um modelo da família "
                   "Haiku (mais barato e rápido).")
    default_base_url = "https://api.anthropic.com/v1"
    requires_api_key = True
    local_by_default = False
    suggested_models = ["claude-haiku-5-5", "claude-haiku-4-5"]

    @classmethod
    def fields(cls) -> list[FieldSpec]:
        return [*super().fields(), FieldSpec(
            name="workspace_id", label="ID do workspace",
            help="Só para chave de API que não pertence a um workspace (erro pedindo o "
                 "cabeçalho anthropic-workspace-id). O ID fica em Settings › Workspaces no "
                 "console da Anthropic.")]

    def _headers(self) -> dict:
        h = {"x-api-key": self.config.api_key or "", "anthropic-version": VERSAO_API}
        workspace = (self.config.extra.get("workspace_id") or "").strip()
        if workspace:
            h["anthropic-workspace-id"] = workspace
        return h

    def _corpo(self, request: ChatRequest, com_temperatura: bool) -> dict:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        if request.json_mode:
            system += "\n\nResponda somente com um objeto JSON válido, sem texto fora dele."
        corpo: dict = {
            "model": self.config.model,
            "max_tokens": self._max_tokens(request),
            "messages": _alternar(request.messages),
            "thinking": {"type": "disabled"},
        }
        if system.strip():
            corpo["system"] = system.strip()
        if com_temperatura:
            corpo["temperature"] = self._temperature(request)
        return corpo

    def chat(self, request: ChatRequest) -> ChatResponse:
        url = f"{self.base_url}/messages"
        com_temperatura = self.config.model not in _SEM_TEMPERATURA
        try:
            data, latency = post_json(url, json=self._corpo(request, com_temperatura),
                                      headers=self._headers(), timeout=self.config.timeout_s)
        except AIProviderError as exc:
            if not (com_temperatura and _recusou_temperatura(exc)):
                raise
            _SEM_TEMPERATURA.add(self.config.model)
            data, latency = post_json(url, json=self._corpo(request, False),
                                      headers=self._headers(), timeout=self.config.timeout_s)
        texto = "".join(b.get("text", "") for b in data.get("content") or []
                        if b.get("type") == "text")
        if not texto.strip() and data.get("stop_reason") == "max_tokens":
            raise AIProviderError("O Claude atingiu o limite de tokens antes de responder; "
                                  "aumente 'max_tokens' no perfil.")
        usage = data.get("usage") or {}
        return ChatResponse(
            text=texto,
            model=data.get("model", self.config.model),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=latency,
        )

    def list_models(self) -> list[str]:
        data = get_json(f"{self.base_url}/models?limit=100", headers=self._headers(),
                        timeout=self.config.timeout_s)
        return sorted(m["id"] for m in data.get("data", []))
