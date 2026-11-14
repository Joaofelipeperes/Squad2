"""Utilitário HTTP comum aos adaptadores (tempo de resposta e erros legíveis).

O endereço do provedor é digitado na tela Modelos de IA: antes de chamar, `exigir_url_configuravel`
recusa esquema que não seja http/https e a faixa link-local; redirecionamento não é seguido; e a
mensagem de erro leva só o texto de erro do provedor, nunca o corpo bruto da resposta (ADR-0036).
"""
import time

import httpx

from app.core.rede import UrlNaoPermitida, exigir_url_configuravel
from app.integrations.ai.base import AIProviderError


def _verificar(url: str) -> None:
    try:
        exigir_url_configuravel(url)
    except UrlNaoPermitida as exc:
        raise AIProviderError(str(exc)) from exc


def _erro_do_provedor(resp: httpx.Response) -> str:
    """Mensagem de erro que o provedor devolveu em JSON (`error` ou `error.message`), se houver."""
    try:
        erro = resp.json().get("error")
    except (ValueError, AttributeError):
        return ""
    if isinstance(erro, dict):
        erro = erro.get("message")
    return f": {str(erro)[:300]}" if erro else ""


def _json(resp: httpx.Response, url: str) -> dict:
    if resp.status_code >= 400:
        raise AIProviderError(f"HTTP {resp.status_code} em {url}{_erro_do_provedor(resp)}")
    try:
        dados = resp.json()
    except ValueError as exc:
        raise AIProviderError(f"Resposta inesperada de {url} (não é JSON).") from exc
    if not isinstance(dados, dict):
        raise AIProviderError(f"Resposta inesperada de {url}.")
    return dados


def post_json(url: str, *, json: dict, headers: dict | None, timeout: float) -> tuple[dict, int]:
    _verificar(url)
    t0 = time.perf_counter()
    try:
        resp = httpx.post(url, json=json, headers=headers, timeout=timeout)
    except httpx.TransportError as exc:
        raise AIProviderError(f"Não foi possível conectar a {url}: {exc}") from exc
    latency = int((time.perf_counter() - t0) * 1000)
    return _json(resp, url), latency


def get_json(url: str, *, headers: dict | None, timeout: float) -> dict:
    _verificar(url)
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.TransportError as exc:
        raise AIProviderError(f"Não foi possível conectar a {url}: {exc}") from exc
    return _json(resp, url)
