"""Catálogo de adaptadores de IA. Para suportar um fornecedor novo:

    @register_provider
    class MeuProvider(AIProvider):
        kind = "meu_fornecedor"; label = "..."; description = "..."
        def chat(self, request): ...
        def list_models(self): ...

e importe o arquivo em app/integrations/ai/__init__.py. A página de configuração passa a
oferecê-lo automaticamente (GET /api/v1/ia/tipos-provedor).
"""
from app.integrations.ai.base import AIProvider, AIProviderError, ProviderConfig

_REGISTRY: dict[str, type[AIProvider]] = {}


def register_provider(cls: type[AIProvider]) -> type[AIProvider]:
    if cls.kind in _REGISTRY:
        raise ValueError(f"Provedor '{cls.kind}' já registrado.")
    _REGISTRY[cls.kind] = cls
    return cls


def provider_class(kind: str) -> type[AIProvider]:
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise AIProviderError(f"Tipo de provedor desconhecido: '{kind}'.") from None


def build_provider(config: ProviderConfig) -> AIProvider:
    return provider_class(config.kind)(config)


def available_kinds() -> list[type[AIProvider]]:
    return list(_REGISTRY.values())
