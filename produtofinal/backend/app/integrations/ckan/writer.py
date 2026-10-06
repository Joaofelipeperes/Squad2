"""Escrita no CKAN — EXCLUSIVA para publicar recurso anonimizado após aprovação do gestor (US26).

Salvaguardas (PGP v2):
- desligada por padrão (GDA_CKAN_WRITE_ENABLED=false) até autorização formal CGE-GO/SECTI (PBI-95);
- token de API pertence à GEDA, nunca a um residente;
- só aceita recursos com url_type == "upload" (links externos não são corrigíveis pelo CKAN);
- a cópia do original e a trilha de aprovação são responsabilidade do módulo lgpd, ANTES de chamar aqui.
"""
from pathlib import Path

import httpx

from app.core.config import get_settings


class CkanWriteDisabled(RuntimeError):
    pass


class CkanWriter:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        s = get_settings()
        if not s.ckan_write_enabled or not s.ckan_write_api_token:
            raise CkanWriteDisabled(
                "Escrita no CKAN desabilitada. Requer GDA_CKAN_WRITE_ENABLED=true e token da GEDA."
            )
        base = (s.ckan_write_base_url or s.ckan_base_url).rstrip("/")
        self._http = httpx.Client(
            base_url=f"{base}/api/3/action",
            headers={"Authorization": s.ckan_write_api_token.get_secret_value()},
            timeout=120,
            transport=transport,
        )

    def replace_resource_file(self, resource_id: str, file_path: Path, *, note: str) -> dict:
        """Substitui o arquivo de um recurso (resource_patch com upload multipart)."""
        with file_path.open("rb") as fh:
            resp = self._http.post(
                "/resource_patch",
                data={"id": resource_id, "gda_nota_correcao": note},
                files={"upload": (file_path.name, fh)},
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"resource_patch falhou: {data.get('error')}")
        return data["result"]
