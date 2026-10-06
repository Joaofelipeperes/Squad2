import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["GDA_DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["GDA_ENVIRONMENT"] = "dev"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.modules import import_all_models  # noqa: E402
from app.modules.acesso.service import criar_usuario  # noqa: E402
from app.modules.inventario.models import Organizacao  # noqa: E402

import_all_models()
SENHA = "senha12345"


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add_all([Organizacao(ckan_id="org-seduc", name="seduc", titulo="Secretaria da Educação"),
                    Organizacao(ckan_id="org-ses", name="ses", titulo="Secretaria da Saúde")])
        db.commit()
        criar_usuario(db, "admin@cge.go.gov.br", "Admin", SENHA, ["administrador"])
        criar_usuario(db, "paloma@cge.go.gov.br", "Paloma", SENHA, ["gerente_geda"])
        criar_usuario(db, "estagiario@cge.go.gov.br", "Estagiário", SENHA, ["analista_geda"])
        criar_usuario(db, "servidor@seduc.go.gov.br", "Servidor SEDUC", SENHA,
                      ["orgao_publicador"], orgao_id="org-seduc")
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email):
    r = client.post("/api/v1/acesso/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return login(client, "admin@cge.go.gov.br")


@pytest.fixture
def gerente(client):
    return login(client, "paloma@cge.go.gov.br")


@pytest.fixture
def analista(client):
    return login(client, "estagiario@cge.go.gov.br")


@pytest.fixture
def orgao(client):
    return login(client, "servidor@seduc.go.gov.br")
