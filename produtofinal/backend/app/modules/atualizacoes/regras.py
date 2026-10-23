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


def _criado_em(recurso: object) -> object:
    """Data de criação do recurso NO CKAN. Objetos do banco guardam essa data em `created_ckan`
    (o `created` deles é a auditoria da tabela — ADR-0019): quem tem `created_ckan` usa só ele,
    mesmo vazio; payloads do CKAN e dicts usam `created`."""
    if isinstance(recurso, Mapping):
        return recurso["created_ckan"] if "created_ckan" in recurso else recurso.get("created")
    if hasattr(recurso, "created_ckan"):
        return recurso.created_ckan
    return getattr(recurso, "created", None)


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

    Se nenhum recurso válido tem `last_modified`, usa a maior data de criação no CKAN e marca
    `estimada=True`. Sem recurso válido → (None, False). Recursos podem ser objetos do banco
    (`created_ckan`) ou payloads/dicts do CKAN (`created`), com `last_modified` e
    `eh_dicionario_dados`.
    """
    validos = [r for r in (recursos or []) if not _campo(r, "eh_dicionario_dados")]
    modificados = [d for r in validos if (d := _como_datetime(_campo(r, "last_modified")))]
    if modificados:
        return UltimaAtualizacao(max(modificados), False)
    criados = [d for r in validos if (d := _como_datetime(_criado_em(r)))]
    if criados:
        return UltimaAtualizacao(max(criados), True)
    return UltimaAtualizacao(None, False)
