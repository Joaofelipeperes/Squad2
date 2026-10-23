"""Tela Organizações (US19) e formato fechado (PBI-53). Dados fictícios."""
from datetime import UTC, date, datetime

import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Coleta, Dataset, Recurso
from app.modules.metadados import regras
from app.modules.pda import service as pda_service
from tests.conftest import SEDUC, SES

API = "/api/v1/painel/organizacoes"
URL = "https://dadosabertos.go.gov.br/dataset/"
DS_A, DS_B, DS_C = 1, 2, 3


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(pda_service, "hoje_local", lambda: date(2026, 10, 18))


@pytest.fixture
def inventario():
    """org-ses: 2 datasets ativos (CSV, ZIP, PDF, sem formato, dicionário PDF, recurso apagado
    XLS) e 1 fora do portal (PDF); org-seduc: nenhum dataset."""
    lm = datetime(2026, 9, 1, tzinfo=UTC)
    with SessionLocal() as db:
        db.add_all([Coleta(id=1, status="ok"), Coleta(id=2, status="ok")])
        db.add_all([
            Dataset(id=DS_A, id_ckan="ds-a", name="indicadores-saude", titulo="Indicadores",
                    organizacao_id=SES, ultima_coleta_id=2),
            Dataset(id=DS_B, id_ckan="ds-b", name="leitos", titulo="Leitos", organizacao_id=SES,
                    ultima_coleta_id=2),
            Dataset(id=DS_C, id_ckan="ds-c", name="antigo", titulo="Antigo", organizacao_id=SES,
                    ativo_no_portal=False, ultima_coleta_id=1),
        ])
        db.add_all([
            Recurso(id=1, id_ckan="r1", dataset_id=DS_A, formato="CSV", ultima_coleta_id=2,
                    last_modified=lm),
            Recurso(id=2, id_ckan="r2", dataset_id=DS_A, formato="ZIP", ultima_coleta_id=2),
            Recurso(id=3, id_ckan="r3", dataset_id=DS_A, nome="Dicionário de dados", formato="PDF",
                    eh_dicionario_dados=True, ultima_coleta_id=2),
            Recurso(id=4, id_ckan="r4", dataset_id=DS_A, formato="XLS", ultima_coleta_id=1),
            Recurso(id=5, id_ckan="r5", dataset_id=DS_B, formato="PDF", ultima_coleta_id=2),
            Recurso(id=6, id_ckan="r6", dataset_id=DS_B, formato=None, ultima_coleta_id=2),
            Recurso(id=7, id_ckan="r7", dataset_id=DS_C, formato="PDF", ultima_coleta_id=1),
        ])
        db.commit()


@pytest.mark.parametrize("formato,esperado", [
    ("CSV", True), (" csv ", True), (".json", True), ("ZIP", False), ("PDF", False),
    ("", False), (None, False),
])
def test_eh_formato_aberto(formato, esperado):
    assert regras.eh_formato_aberto(formato, ["CSV", "JSON"]) is esperado


def _org(corpo, chave):
    return next(o for o in corpo["organizacoes"] if o["chave"] == chave)


def test_sem_pda(client, gerente, inventario):
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"] is None
    assert corpo["formatos_abertos"] == ["CSV", "JSON", "XML", "ODS", "GEOJSON", "TXT"]
    assert [o["nome"] for o in corpo["organizacoes"]] == [
        "Secretaria da Educação", "Secretaria da Saúde"]
    ses = _org(corpo, str(SES))
    # Só datasets ativos; recursos atuais sem dicionário; formatos fechados: ZIP, PDF e sem formato
    assert ses["datasets_no_portal"] == 2 and ses["recursos_validos"] == 4
    assert ses["recursos_formato_fechado"] == 3
    assert ses["formatos_fechados"] == {"ZIP": 1, "PDF": 1, "": 1}
    assert ses["bases_previstas"] == 0
    assert ses["atualizacao_pct"] is None and ses["indice_atencao"] is None
    assert ses["riscos_lgpd"] is None
    seduc = _org(corpo, str(SEDUC))
    assert seduc["datasets_no_portal"] == 0 and seduc["recursos_formato_fechado"] == 0


def test_bases_do_pda_vigente_por_orgao(client, gerente, inventario):
    texto = ("Orgão;Base de Dados;Meta/Prazo para abertura;Disponível no Portal\n"
             f"SES;Indicadores;Março/2025;{URL}indicadores-saude\n"
             "SES;Vacinas;Março/2025;Não\n"
             f"SES;Antiga;Março/2025;{URL}antigo\n"
             "SES;Leitos;Outubro/2026;Não\n"
             "SEDUC;Matrículas;Dezembro/2027;Não\n"
             "XYZ;Base sem órgão;Março/2025;Não\n")
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", texto.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"]["nome"] == "PDA teste"
    ses = _org(corpo, str(SES))
    assert ses["siglas"] == ["SES"] and ses["bases_previstas"] == 4
    assert ses["bases_vinculadas"] == 2 and ses["bases_publicadas"] == 1
    # Só a vinculada a dataset fora do portal conta; Vacinas (sem vínculo, prazo vencido) não
    assert ses["bases_em_atraso"] == 1
    assert ses["bases_proximas_do_prazo"] == 1  # Leitos vence em 31/10/2026 (janela de 30 dias)
    seduc = _org(corpo, str(SEDUC))
    assert seduc["bases_previstas"] == 1 and seduc["bases_em_atraso"] is None  # sem vínculo
    # Sigla do PDA sem organização no portal vira linha própria
    xyz = _org(corpo, "sigla:XYZ")
    assert xyz["organizacao_id"] is None and xyz["nome"] == "XYZ"
    assert xyz["bases_previstas"] == 1 and xyz["datasets_no_portal"] == 0


def test_parametro_formatos_abertos_editavel(client, admin, gerente, inventario):
    r = client.put("/api/v1/parametros/formatos_abertos", headers=admin,
                   json={"valor": ["CSV", "ZIP"]})
    assert r.status_code == 200, r.text
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    assert ses["formatos_fechados"] == {"PDF": 1, "": 1}


def test_permissao(client, orgao):
    assert client.get(API, headers=orgao).status_code == 403  # papel de órgão não tem painel


def test_excluidos_nao_contam_no_painel(client, gerente, inventario):
    """Exclusão lógica (ADR-0019): dataset e recurso excluídos saem das contagens."""
    with SessionLocal() as db:
        db.get(Dataset, DS_B).deleted = True  # leva PDF e sem formato
        db.get(Recurso, 2).deleted = True     # ZIP do DS_A
        db.commit()
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    assert ses["datasets_no_portal"] == 1 and ses["recursos_validos"] == 1
    assert ses["recursos_formato_fechado"] == 0 and ses["formatos_fechados"] == {}
