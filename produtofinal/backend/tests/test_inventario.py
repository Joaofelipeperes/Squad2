import httpx

from app.core.db import SessionLocal
from app.integrations.ckan.client import CkanClient
from app.modules.inventario import service
from app.modules.inventario.models import Dataset, DatasetSnapshot, Recurso

ORGS = [{"id": "o1", "name": "ses", "title": "Secretaria da Saúde"},
        {"id": "o2", "name": "seduc", "title": "Secretaria da Educação"}]


def _pkg(i, org):
    return {
        "id": f"d{i}", "name": f"dataset-{i}", "title": f"Dataset {i}",
        "organization": {"id": org}, "metadata_modified": "2026-09-20T10:00:00",
        "extras": [{"key": "periodicidade", "value": "Mensal"}],
        "resources": [
            {"id": f"r{i}a", "name": "dados.csv", "format": "csv", "url_type": "upload",
             "last_modified": "2026-09-01T08:00:00"},
            {"id": f"r{i}b", "name": "Dicionário de dados", "format": "PDF", "url_type": None},
        ],
    }


PKGS = [_pkg(1, "o1"), _pkg(2, "o1"), _pkg(3, "o2")]


def _handler(request: httpx.Request):
    action = request.url.path.rsplit("/", 1)[-1]
    if action == "organization_list":
        return httpx.Response(200, json={"success": True, "result": ORGS})
    if action == "package_search":
        start, rows = int(request.url.params["start"]), int(request.url.params["rows"])
        return httpx.Response(200, json={"success": True, "result": {
            "count": len(PKGS), "results": PKGS[start:start + rows]}})
    return httpx.Response(404, json={"success": False})


def test_coleta_completa_com_paginacao():
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler))
    with SessionLocal() as db:
        c = service.iniciar(db, origem="manual")
    import app.core.config as cfg
    cfg.get_settings().ckan_page_size = 2  # força duas páginas
    service.executar(c.id, client=client)
    with SessionLocal() as db:
        coleta = service.ultima_coleta(db)
        assert coleta.status == "ok", coleta.erro
        assert (coleta.total_organizacoes, coleta.total_datasets, coleta.total_recursos) == (2, 3, 6)
        ds = db.get(Dataset, "d1")
        assert ds.periodicidade_declarada == "Mensal"
        assert db.get(Recurso, "r1b").eh_dicionario_dados is True
        assert db.get(Recurso, "r1a").formato == "CSV"
        assert db.query(DatasetSnapshot).count() == 3


def test_coleta_concorrente_bloqueada(client, gerente):
    h = gerente
    with SessionLocal() as db:
        service.iniciar(db, origem="agendada")
    assert client.post("/api/v1/inventario/coletas", headers=h).status_code == 409
