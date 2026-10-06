"""Contrato de módulo do backend.

Cada pasta em app/modules/ expõe um objeto `module: BackendModule` no seu __init__.py.
O main.py e o worker.py descobrem os módulos pela lista INSTALLED_MODULES — adicionar uma
funcionalidade nova = criar a pasta + registrar o nome na lista. Nada mais precisa mudar.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import APIRouter


@dataclass(frozen=True)
class JobSpec:
    """Tarefa agendada executada pelo worker (processo separado da API)."""

    id: str
    func: Callable[[], None]
    cron: str  # expressão crontab: "min hora dia mês dia_semana"


@dataclass(frozen=True)
class BackendModule:
    name: str
    prefix: str                       # ex.: "/inventario" → /api/v1/inventario
    tags: list[str]
    router: APIRouter | None = None
    jobs: list[JobSpec] = field(default_factory=list)
    user_stories: list[str] = field(default_factory=list)  # rastreabilidade com o backlog
