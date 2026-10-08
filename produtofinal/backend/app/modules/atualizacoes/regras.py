"""Regras puras do módulo atualizacoes (sem banco, sem FastAPI) — reutilizáveis numa extensão CKAN.

Atualização real = `last_modified` do RECURSO. `metadata_modified` do dataset nunca é indicador.
"""
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import NamedTuple


class UltimaAtualizacao(NamedTuple):
    data: datetime | None
    estimada: bool  # True = sem last_modified em nenhum recurso válido; data veio de `created`


def _campo(recurso: object, nome: str) -> object:
    if isinstance(recurso, Mapping):
        return recurso.get(nome)
    return getattr(recurso, nome, None)


def _como_datetime(valor: object) -> datetime | None:
    """Aceita datetime ou ISO 8601 (formato do CKAN). Sem fuso → UTC (CKAN 2.9 grava em UTC)."""
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.strip())
        except ValueError:
            return None
    if not isinstance(valor, datetime):
        return None
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


def ultima_atualizacao_real(recursos: Iterable[object] | None) -> UltimaAtualizacao:
    """PBI-23/24/25 — maior `last_modified` entre os recursos, EXCLUINDO dicionário de dados.

    Se nenhum recurso válido tem `last_modified`, usa o maior `created` e marca `estimada=True`.
    Sem recurso válido → (None, False). Recursos podem ser objetos (ORM) ou dicts com os campos
    `last_modified`, `created` e `eh_dicionario_dados`.
    """
    validos = [r for r in (recursos or []) if not _campo(r, "eh_dicionario_dados")]
    modificados = [d for r in validos if (d := _como_datetime(_campo(r, "last_modified")))]
    if modificados:
        return UltimaAtualizacao(max(modificados), False)
    criados = [d for r in validos if (d := _como_datetime(_campo(r, "created")))]
    if criados:
        return UltimaAtualizacao(max(criados), True)
    return UltimaAtualizacao(None, False)
