"""Regras puras (sem banco, sem FastAPI) — reutilizáveis caso a entrega vire extensão CKAN."""
import hashlib
import json
import re
from datetime import datetime, timezone

# Heurística provisória até a GEDA confirmar o critério (PBI-11)
_DICIONARIO = re.compile(r"dicion[aá]rio(\s+de)?\s+dados", re.IGNORECASE)


def parse_ckan_datetime(value: str | None) -> datetime | None:
    """CKAN 2.9 devolve ISO sem fuso (UTC implícito): '2026-09-17T14:03:11.123456'."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def eh_dicionario_de_dados(nome: str | None, descricao: str | None = None) -> bool:
    return bool(_DICIONARIO.search(f"{nome or ''} {descricao or ''}"))


def extras_como_dict(extras: list[dict] | None) -> dict:
    return {e.get("key"): e.get("value") for e in (extras or []) if e.get("key")}


def snapshot_payload(pkg: dict) -> dict:
    """Recorte estável do dataset usado para detectar mudanças entre coletas."""
    return {
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "private": pkg.get("private", False),
        "state": pkg.get("state"),
        "organization": (pkg.get("organization") or {}).get("id"),
        "resources": sorted(
            ({"id": r.get("id"), "format": r.get("format"), "last_modified": r.get("last_modified"),
              "url": r.get("url")} for r in pkg.get("resources", [])),
            key=lambda r: r["id"] or "",
        ),
    }


def hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
