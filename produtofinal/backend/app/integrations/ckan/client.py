"""Cliente de leitura da API Action do CKAN (https://docs.ckan.org/en/2.9/api/).

Regras de projeto já decididas e que este cliente respeita:
- a chave de vínculo é SEMPRE o `id` do dataset (o `name` é editável pelos órgãos);
- `last_modified` do RECURSO é o indicador de atualização; `metadata_modified` do dataset não.
"""
import logging
import threading
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class CkanError(RuntimeError):
    def __init__(self, mensagem: str, status_http: int | None = None) -> None:
        super().__init__(mensagem)
        self.status_http = status_http


class CkanAcessoNegado(CkanError):
    """HTTP 403: o token usado não tem permissão para a action naquele objeto."""


class CkanNaoEncontrado(CkanError):
    """HTTP 404: objeto inexistente (ou removido definitivamente) no CKAN."""


class CkanLimiteDeRequisicoes(CkanError):
    """HTTP 429 ao baixar arquivo: o servidor pediu para esperar (`espera_s`, do Retry-After)."""

    def __init__(self, mensagem: str, espera_s: float | None = None) -> None:
        super().__init__(mensagem, 429)
        self.espera_s = espera_s


def _segundos(retry_after: str | None) -> float | None:
    try:
        return max(float(retry_after), 0.0) if retry_after else None
    except ValueError:  # Retry-After em formato de data: usa a espera padrão
        return None


# Download de arquivos: intervalo mínimo por host, comum a todos os clientes do processo (o
# worker executa a fila de varredura e a API gera prévias; cada processo respeita o seu).
_proximo_download: dict[str, float] = {}
_trava_downloads = threading.Lock()


def _aguardar_vez(host: str, intervalo_s: float) -> None:
    if intervalo_s <= 0:
        return
    with _trava_downloads:
        agora = time.monotonic()
        inicio = max(agora, _proximo_download.get(host, 0.0))
        _proximo_download[host] = inicio + intervalo_s
    if inicio > agora:
        time.sleep(inicio - agora)


class CkanClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        transport: httpx.BaseTransport | None = None,  # injetável nos testes
        api_token: str | None = None,  # só para actions que exigem login (auditoria)
        intervalo_download_s: float | None = None,
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ckan_base_url).rstrip("/")
        self.max_retries = max_retries if max_retries is not None else s.ckan_max_retries
        self.intervalo_download_s = (intervalo_download_s if intervalo_download_s is not None
                                     else s.ckan_download_intervalo_s)
        self.esperas_429 = s.ckan_download_esperas_429
        headers = {"User-Agent": "monitor-dados-abertos-go/0.1 (CGE-GO/GEDA)"}
        if api_token:
            headers["Authorization"] = api_token
        self._transport = transport
        self._http = httpx.Client(
            base_url=f"{self.base_url}/api/3/action",
            timeout=timeout or s.ckan_timeout_s,
            headers=headers,
            transport=transport,
            follow_redirects=True,  # alguns portais redirecionam a API; sem isso o corpo vem vazio
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------ baixo nível
    def action(self, name: str, **params: Any) -> Any:
        """Chama /api/3/action/<name> com retentativa exponencial em falhas transitórias."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._http.get(f"/{name}", params=params)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise httpx.HTTPStatusError("transitório", request=resp.request, response=resp)
                if resp.status_code == 403:
                    raise CkanAcessoNegado(f"{name}: acesso negado pelo CKAN (HTTP 403)", 403)
                if resp.status_code == 404:
                    raise CkanNaoEncontrado(f"{name}: não encontrado no CKAN (HTTP 404)", 404)
                try:
                    data = resp.json()
                except ValueError as exc:
                    # Corpo não-JSON (ex.: página HTML de "Acesso Negado" com HTTP 200, típica de
                    # portal sem a extensão/endpoint): vira erro tratado em vez de JSONDecodeError.
                    tipo = resp.headers.get("content-type", "?")
                    raise CkanError(f"{name}: resposta não-JSON do CKAN "
                                    f"(HTTP {resp.status_code}, {tipo})", resp.status_code) from exc
                if not data.get("success"):
                    raise CkanError(f"{name} falhou: {data.get('error')}")
                return data["result"]
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                wait = 2**attempt
                log.warning("CKAN %s tentativa %s falhou (%s); nova tentativa em %ss",
                            name, attempt + 1, exc, wait)
                time.sleep(wait)
        raise CkanError(f"{name} indisponível após {self.max_retries + 1} tentativas") from last_exc

    # ------------------------------------------------------------------ alto nível
    def status(self) -> dict:
        return self.action("status_show")

    def organizations(self, page_size: int = 25) -> list[dict]:
        """Todas as organizações, paginando: o CKAN 2.9 limita `organization_list` com
        `all_fields=True` a 25 itens por chamada (ckan.group_and_organization_list_all_fields_max),
        e o portal tem mais que isso. Sem paginar, datasets de órgãos fora da 1ª página quebram a
        coleta (FK de organização)."""
        orgs: list[dict] = []
        vistos: set[str] = set()
        offset = 0
        while True:
            batch = self.action("organization_list", all_fields=True, include_extras=True,
                                limit=page_size, offset=offset)
            novos = [o for o in batch if o.get("id") not in vistos]
            orgs.extend(novos)
            vistos.update(o.get("id") for o in novos)
            # página incompleta = fim; página só com repetidos = servidor ignorou o offset
            if len(batch) < page_size or not novos:
                return orgs
            offset += len(batch)

    def iter_datasets(self, page_size: int | None = None) -> Iterator[dict]:
        """Percorre TODOS os datasets públicos com paginação (package_search), recursos inclusos."""
        rows = page_size or get_settings().ckan_page_size
        start = 0
        while True:
            result = self.action(
                "package_search", q="*:*", rows=rows, start=start, sort="id asc",
                include_private=False,
            )
            batch = result.get("results", [])
            yield from batch
            start += len(batch)
            if not batch or start >= result.get("count", 0):
                break

    def dataset(self, dataset_id: str) -> dict:
        return self.action("package_show", id=dataset_id)

    def resource(self, resource_id: str) -> dict:
        return self.action("resource_show", id=resource_id)

    # ------------------------------------------------------------------ auditoria (ADR-0009)
    def auditoria_dataset(self, dataset_id: str, *, limit: int = 100, offset: int = 0,
                          resource_id: str | None = None,
                          activity_type: str | None = None) -> dict:
        """Atividades gravadas pela extensão ckanext-dsaudit para um dataset (inclusive
        excluído), da mais recente para a mais antiga: {"count": N, "results": [...]}.
        Filtros opcionais por recurso e tipo de atividade. Exige token de usuário com permissão
        de edição no dataset (CkanAcessoNegado se não)."""
        params: dict = {"id": dataset_id, "limit": limit, "offset": offset}
        if resource_id:
            params["resource_id"] = resource_id
        if activity_type:
            params["activity_type"] = activity_type
        return self.action("dsaudit_activity_list", **params)

    def atividades_orgao(self, org_id: str, *, limit: int = 100, offset: int = 0) -> list[dict]:
        """Atividades nativas do CKAN ligadas ao órgão (`organization_activity_list`), da mais
        recente para a mais antiga: alterações no próprio órgão ("changed organization") e nos
        datasets dele. Traz usuário e data; o conteúdo (`data`) vem resumido."""
        return self.action("organization_activity_list", id=org_id, limit=limit, offset=offset)

    def atividades_dataset(self, dataset_id: str, *, limit: int = 100,
                           offset: int = 0) -> list[dict]:
        """Atividades nativas do CKAN do dataset (`package_activity_list`), da mais recente para a
        mais antiga: "new/changed/deleted package", com usuário e data (conteúdo resumido)."""
        return self.action("package_activity_list", id=dataset_id, limit=limit, offset=offset)

    def dados_atividade(self, activity_id: str) -> dict:
        """Versão completa do objeto guardada pelo CKAN na atividade nativa (`activity_data_show`;
        para dataset, o package_show daquele momento). Exige permissão de edição no dataset."""
        return self.action("activity_data_show", id=activity_id, object_type="package")

    def usuario(self, user_id: str) -> dict:
        return self.action("user_show", id=user_id)

    # ------------------------------------------------------------------ arquivos dos recursos
    def url_download(self, recurso_id: str, dataset_id: str, url: str | None,
                     url_type: str | None) -> str | None:
        """Endereço para baixar o arquivo do recurso. Arquivo enviado ao CKAN (`upload`) é baixado
        pelo endereço deste cliente, não pela URL gravada: dentro do Docker, a URL gravada aponta
        para o endereço público do portal (ex.: localhost:5000), que o container não alcança.
        Link externo é baixado da própria URL."""
        if not url:
            return None
        if url_type == "upload":
            nome = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
            return f"{self.base_url}/dataset/{dataset_id}/resource/{recurso_id}/download/{nome}"
        return url

    def baixar(self, url: str, limite_bytes: int) -> bytes:
        """Baixa um arquivo (para a varredura LGPD), parando se passar de `limite_bytes`.
        Respeita o intervalo mínimo entre downloads do mesmo host e, se o servidor responder
        HTTP 429, espera (Retry-After ou 60 s, 2 min, 4 min…) e tenta de novo (ADR-0025)."""
        host = httpx.URL(url).host
        for tentativa in range(self.esperas_429 + 1):
            _aguardar_vez(host, self.intervalo_download_s)
            try:
                return self._baixar_uma_vez(url, limite_bytes)
            except CkanLimiteDeRequisicoes as exc:
                if tentativa == self.esperas_429:
                    raise
                pausa = exc.espera_s or min(60 * 2 ** tentativa, 900)
                log.warning("HTTP 429 de %s; nova tentativa em %.0f s (%s de %s)", host, pausa,
                            tentativa + 1, self.esperas_429)
                time.sleep(pausa)
        raise AssertionError("inalcançável")

    def _baixar_uma_vez(self, url: str, limite_bytes: int) -> bytes:
        partes, total = [], 0
        # Sem o token da auditoria: a URL pode ser um link externo ao portal.
        headers = {k: v for k, v in self._http.headers.items() if k.lower() != "authorization"}
        try:
            with httpx.Client(transport=self._transport, timeout=self._http.timeout,
                              follow_redirects=True, headers=headers) as http, \
                    http.stream("GET", url) as resp:
                if resp.status_code == 429:
                    raise CkanLimiteDeRequisicoes(
                        f"HTTP 429 ao baixar {url}", _segundos(resp.headers.get("Retry-After")))
                if resp.status_code >= 400:
                    raise CkanError(f"HTTP {resp.status_code} ao baixar {url}", resp.status_code)
                for pedaco in resp.iter_bytes():
                    total += len(pedaco)
                    if total > limite_bytes:
                        raise CkanError(f"Arquivo maior que {limite_bytes // (1024 * 1024)} MB.")
                    partes.append(pedaco)
        except httpx.HTTPError as exc:
            raise CkanError(f"Falha ao baixar {url}: {exc}") from exc
        return b"".join(partes)
