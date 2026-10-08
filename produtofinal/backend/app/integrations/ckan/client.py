"""Cliente de leitura da API Action do CKAN (https://docs.ckan.org/en/2.9/api/).

Regras de projeto já decididas e que este cliente respeita:
- a chave de vínculo é SEMPRE o `id` do dataset (o `name` é editável pelos órgãos);
- `last_modified` do RECURSO é o indicador de atualização; `metadata_modified` do dataset não.
"""
import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class CkanError(RuntimeError):
    pass


class CkanClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        transport: httpx.BaseTransport | None = None,  # injetável nos testes
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ckan_base_url).rstrip("/")
        self.max_retries = max_retries if max_retries is not None else s.ckan_max_retries
        self._http = httpx.Client(
            base_url=f"{self.base_url}/api/3/action",
            timeout=timeout or s.ckan_timeout_s,
            headers={"User-Agent": "monitor-dados-abertos-go/0.1 (CGE-GO/GEDA)"},
            transport=transport,
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
                data = resp.json()
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
