"""Contrato comum a todos os provedores de IA (locais ou comerciais)."""
from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    json_mode: bool = False  # pede ao modelo uma resposta JSON válida


class ChatResponse(BaseModel):
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


class ProviderConfig(BaseModel):
    """Configuração já decifrada, montada a partir de um perfil salvo no banco."""

    kind: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    timeout_s: float = 60.0
    temperature: float = 0.2
    max_tokens: int = 1024
    extra: dict = Field(default_factory=dict)


class FieldSpec(BaseModel):
    """Descreve um campo do formulário de configuração — o frontend monta o form a partir disso."""

    name: str
    label: str
    required: bool = False
    secret: bool = False
    placeholder: str | None = None
    help: str | None = None


class AIProviderError(RuntimeError):
    pass


class AIProvider(ABC):
    kind: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    default_base_url: ClassVar[str | None] = None
    requires_api_key: ClassVar[bool] = False
    local_by_default: ClassVar[bool] = False  # sugestão para o campo "execução local" do perfil
    suggested_models: ClassVar[list[str]] = []

    def __init__(self, config: ProviderConfig) -> None:
        if self.requires_api_key and not config.api_key:
            raise AIProviderError(f"O provedor {self.label} exige chave de API.")
        self.config = config
        self.base_url = (config.base_url or self.default_base_url or "").rstrip("/")

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @classmethod
    def fields(cls) -> list[FieldSpec]:
        specs = [
            FieldSpec(name="base_url", label="URL base", placeholder=cls.default_base_url,
                      help="Deixe em branco para usar o endereço padrão."),
            FieldSpec(name="model", label="Modelo", required=True,
                      placeholder=cls.suggested_models[0] if cls.suggested_models else None),
        ]
        if cls.requires_api_key:
            specs.append(FieldSpec(name="api_key", label="Chave de API", required=True, secret=True))
        return specs

    def _temperature(self, req: ChatRequest) -> float:
        return self.config.temperature if req.temperature is None else req.temperature

    def _max_tokens(self, req: ChatRequest) -> int:
        return req.max_tokens or self.config.max_tokens
