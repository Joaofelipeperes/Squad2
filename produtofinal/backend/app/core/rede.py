"""Regras para as chamadas HTTP que a solução faz para fora (ADR-0036).

Dois níveis, conforme quem escolhe o endereço:

- `exigir_url_configuravel`: endereço digitado por um administrador (provedor de IA, perfil do
  CKAN). Pode ser um serviço da rede interna (o Ollama e o CKAN local são), mas só `http`/`https`
  e nunca um endereço de metadados da nuvem (link-local).
- `exigir_url_externa`: endereço que vem de fora da solução (link de recurso publicado por um órgão
  no CKAN, baixado na varredura LGPD). Não pode apontar para a rede interna, salvo o próprio CKAN
  em uso (`hosts_confiaveis`).

A verificação resolve o nome antes da chamada; quem baixa confere também cada redirecionamento.
"""
import ipaddress
import socket
from collections.abc import Iterable
from urllib.parse import urlsplit

ESQUEMAS = ("http", "https")
_resolver = socket.getaddrinfo  # trocado nos testes (tests/conftest.py): sem consulta de DNS


class UrlNaoPermitida(ValueError):
    pass


def _enderecos(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """IPs do host (o próprio, se já for um IP). Nome que não resolve → lista vazia: a chamada
    falha sozinha logo depois."""
    try:
        return [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        pass
    try:
        infos = _resolver(host, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return []
    return [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]


def _host(url: str) -> str:
    partes = urlsplit(url.strip())
    if partes.scheme.lower() not in ESQUEMAS or not partes.hostname:
        raise UrlNaoPermitida("Endereço inválido: use http:// ou https:// com o nome do servidor.")
    return partes.hostname.lower()


def exigir_url_configuravel(url: str) -> None:
    """Endereço informado por administrador: `http`/`https` e fora da faixa link-local."""
    host = _host(url)
    if any(ip.is_link_local or ip.is_multicast or ip.is_unspecified for ip in _enderecos(host)):
        raise UrlNaoPermitida("Endereço não permitido (faixa reservada da rede).")


def exigir_url_externa(url: str, hosts_confiaveis: Iterable[str] = ()) -> None:
    """Endereço vindo de fora (link de recurso): não pode ser da rede interna."""
    host = _host(url)
    if host in {h.lower() for h in hosts_confiaveis if h}:
        return
    for ip in _enderecos(host):
        if not ip.is_global or ip.is_multicast:
            raise UrlNaoPermitida("O link aponta para um endereço da rede interna e não é baixado.")
