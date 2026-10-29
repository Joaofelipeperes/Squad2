import httpx
from sqlalchemy import select

from app.core.db import SessionLocal
from app.integrations.ckan.client import CkanClient
from app.modules.inventario import regras, service
from app.modules.inventario.models import Dataset, DatasetSnapshot, Organizacao, Recurso

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


def _por_id_ckan(db, modelo, id_ckan):
    return db.scalar(select(modelo).where(modelo.id_ckan == id_ckan))


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
        ds = _por_id_ckan(db, Dataset, "d1")
        assert ds.periodicidade_declarada == "Mensal"
        assert ds.organizacao_id == _por_id_ckan(db, Organizacao, "o1").id
        assert _por_id_ckan(db, Recurso, "r1b").eh_dicionario_dados is True
        assert _por_id_ckan(db, Recurso, "r1a").formato == "CSV"
        assert _por_id_ckan(db, Recurso, "r1a").dataset_id == ds.id
        assert db.query(DatasetSnapshot).count() == 3
        assert db.query(DatasetSnapshot).filter_by(dataset_id=ds.id).count() == 1


def test_segunda_coleta_atualiza_pelo_id_ckan():
    """A coleta casa os registros pelo `id_ckan`: a segunda não duplica nem troca o `id`."""
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler))
    ids = []
    for _ in range(2):
        with SessionLocal() as db:
            c = service.iniciar(db, origem="manual")
        service.executar(c.id, client=client)
        with SessionLocal() as db:
            ids.append({d.id_ckan: d.id for d in db.query(Dataset)})
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert service.ultima_coleta(db).status == "ok"
        assert db.query(Dataset).count() == 3 and db.query(Recurso).count() == 6
        assert db.query(Organizacao).filter(Organizacao.id_ckan.in_(["o1", "o2"])).count() == 2
        assert db.query(DatasetSnapshot).count() == 6


def test_organizacoes_paginadas_alem_do_limite_do_ckan():
    """CKAN 2.9 devolve no máximo 25 organizações por chamada com all_fields=True."""
    todas = [{"id": f"o{i}", "name": f"org-{i}", "title": f"Org {i}"} for i in range(51)]

    def handler(request: httpx.Request):
        limit, offset = int(request.url.params["limit"]), int(request.url.params["offset"])
        return httpx.Response(200, json={"success": True,
                                         "result": todas[offset:offset + min(limit, 25)]})

    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(handler))
    assert [o["id"] for o in client.organizations()] == [o["id"] for o in todas]


def test_coleta_concorrente_bloqueada(client, gerente):
    h = gerente
    with SessionLocal() as db:
        service.iniciar(db, origem="agendada")
    assert client.post("/api/v1/inventario/coletas", headers=h).status_code == 409


def test_periodicidade_usa_extra_atualizacao_do_portal():
    # chave real do portal de Goiás, com acento, maiúscula e espaços sobrando
    assert regras.periodicidade_declarada({"Atualização": " Mensal "}) == "Mensal"
    assert regras.periodicidade_declarada({"atualizacao": "Anual"}) == "Anual"
    # "periodicidade" tem preferência quando existe
    assert regras.periodicidade_declarada({"Atualização": "Anual", "periodicidade": "Mensal"}) == "Mensal"
    # sem extra: usa o campo do pacote; sem nada: None
    assert regras.periodicidade_declarada({}, {"periodicidade": "Semestral"}) == "Semestral"
    assert regras.periodicidade_declarada({"Fonte": "DGPC"}) is None


def test_coleta_preenche_auditoria_e_nao_duplica():
    """Coleta é ação do sistema: created/changed preenchidos, sem usuário; a segunda coleta só
    atualiza `changed` (o `created` e o `id` ficam)."""
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler))
    with SessionLocal() as db:
        c = service.iniciar(db, origem="manual", solicitante="paloma@cge.go.gov.br", usuario_id=7)
    assert c.created_id == 7 and c.changed_id == 7  # coleta manual: quem pediu
    service.executar(c.id, client=client)
    with SessionLocal() as db:
        ds = _por_id_ckan(db, Dataset, "d1")
        rec = _por_id_ckan(db, Recurso, "r1a")
        criado, alterado = ds.created, ds.changed
        assert criado is not None and alterado is not None and ds.created_id is None
        assert rec.created is not None and rec.changed_id is None and rec.deleted is False
    with SessionLocal() as db:
        c2 = service.iniciar(db, origem="agendada")
    service.executar(c2.id, client=client)
    with SessionLocal() as db:
        ds2 = _por_id_ckan(db, Dataset, "d1")
        assert ds2.id == ds.id and ds2.created == criado and ds2.changed >= alterado
        assert db.query(Dataset).count() == 3 and db.query(Recurso).count() == 6


def test_coleta_ignora_registro_excluido_logicamente():
    """Dataset excluído no nosso sistema não é reaproveitado: a coleta cria um registro ativo
    novo para o mesmo id_ckan (único só entre os ativos)."""
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler))
    with SessionLocal() as db:
        c = service.iniciar(db, origem="manual")
    service.executar(c.id, client=client)
    with SessionLocal() as db:
        antigo = _por_id_ckan(db, Dataset, "d1")
        antigo.deleted = True
        db.commit()
        antigo_id = antigo.id
    with SessionLocal() as db:
        c2 = service.iniciar(db, origem="manual")
    service.executar(c2.id, client=client)
    with SessionLocal() as db:
        assert service.ultima_coleta(db).status == "ok"
        d1 = db.query(Dataset).filter_by(id_ckan="d1").order_by(Dataset.id).all()
        assert [(d.id == antigo_id, d.deleted) for d in d1] == [(True, True), (False, False)]
