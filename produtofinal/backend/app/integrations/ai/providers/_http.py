"""Utilitário HTTP comum aos adaptadores (tempo de resposta e erros legíveis)."""
import time

import httpx

from app.integrations.ai.base import AIProviderError


def post_json(url: str, *, json: dict, headers: dict | None, timeout: float) -> tuple[dict, int]:
    t0 = time.perf_counter()
    try:
        resp = httpx.post(url, json=json, headers=headers, timeout=timeout)
    except httpx.TransportError as exc:
        raise AIProviderError(f"Não foi possível conectar a {url}: {exc}") from exc
    latency = int((time.perf_counter() - t0) * 1000)
    if resp.status_code >= 400:
        raise AIProviderError(f"HTTP {resp.status_code} em {url}: {resp.text[:300]}")
    return resp.json(), latency


def get_json(url: str, *, headers: dict | None, timeout: float) -> dict:
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.TransportError as exc:
        raise AIProviderError(f"Não foi possível conectar a {url}: {exc}") from exc
    if resp.status_code >= 400:
        raise AIProviderError(f"HTTP {resp.status_code} em {url}: {resp.text[:300]}")
    return resp.json()
