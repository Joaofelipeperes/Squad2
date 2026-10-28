"""Tela Datasets (PBI-83): lista do inventário, filtros, detalhe e bases do PDA vinculadas.
Dados fictícios."""
from datetime import UTC, date, datetime

import pytest

from app.core.db import SessionLocal
from app.modules.inventario import regras
from app.modules.inventario.models import Coleta, Dataset, Recurso
from app.modules.pda import service as pda_service
from tests.conftest import SEDUC, SES

API = "/api/v1/inventario"
SAUDE, VAZIO, ANTIGO = 1, 2, 3  # `id` próprio dos datasets da fixture


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(pda_service, "hoje_local", lambda: date(2026, 10, 18))


@pytest.fixture
def inventario():
    """org-ses: um dataset publicado (CSV + XLSX + dicionário + recurso apagado) e um só com
    dicionário; org-seduc: um dataset fora do portal."""
    def dt(*a):
        return datetime(*a, tzinfo=UTC)

    with SessionLocal() as db:
        db.add_all([Coleta(id=1, status="ok"), Coleta(id=2, status="ok")])
        db.add_all([
            Dataset(id=SAUDE, id_ckan="ds-saude", name="indicadores-saude",
                    titulo="Indicadores de Saúde",
                    descricao="Indicadores mensais.", organizacao_id=SES,
                    periodicidade_declarada="Mensal", licenca="cc-by",
                    metadata_created=dt(2023, 1, 10), metadata_modified=dt(2026, 10, 1),
                    ultima_coleta_id=2),
            Dataset(id=VAZIO, id_ckan="ds-vazio", name="leitos", titulo="Leitos Hospitalares",
                    organizacao_id=SES, ultima_coleta_id=2),
            Dataset(id=ANTIGO, id_ckan="ds-antigo", name="matriculas", titulo="Matrículas",
                    organizacao_id=SEDUC, ativo_no_portal=False, ultima_coleta_id=1),
        ])
        db.add_all([
            Recurso(id=1, id_ckan="r-csv", dataset_id=SAUDE, nome="dados.csv", formato="CSV",
                    ultima_coleta_id=2, last_modified=dt(2026, 9, 5)),
            Recurso(id=2, id_ckan="r-xlsx", dataset_id=SAUDE, nome="dados.xlsx", formato="XLSX",
                    ultima_coleta_id=2, created_ckan=dt(2026, 9, 1)),
            Recurso(id=3, id_ckan="r-dic", dataset_id=SAUDE, nome="Dicionário de dados",
                    formato="PDF", eh_dicionario_dados=True, ultima_coleta_id=2,
                    last_modified=dt(2026, 10, 2)),
            Recurso(id=4, id_ckan="r-velho", dataset_id=SAUDE, nome="antigo.ods", formato="ODS",
                    ultima_coleta_id=1, last_modified=dt(2026, 10, 3)),
            Recurso(id=5, id_ckan="r-dic2", dataset_id=VAZIO, nome="dicionario de dados",
                    formato="PDF", eh_dicionario_dados=True, ultima_coleta_id=2),
            Recurso(id=6, id_ckan="r-mat", dataset_id=ANTIGO, nome="matriculas.csv",
                    formato="CSV", ultima_coleta_id=1, last_modified=dt(2025, 3, 1)),
        ])
        db.commit()


def _lista(client, h, **params):
    r = client.get(f"{API}/datasets", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("ativo,validos,esperado", [
    (True, 2, "Publicado"), (True, 0, "Sem recurso"), (False, 3, "Fora do portal"),
])
def test_situacao_no_portal(ativo, validos, esperado):
    assert regras.situacao_no_portal(ativo, validos) == esperado


def test_lista_de_datasets(client, gerente, inventario):
    corpo = _lista(client, gerente)
    assert corpo["total"] == 3
    linhas = {d["id_ckan"]: d for d in corpo["datasets"]}
    assert [d["titulo"] for d in corpo["datasets"]] == [
        "Indicadores de Saúde", "Leitos Hospitalares", "Matrículas"]
    saude = linhas["ds-saude"]
    # Recurso apagado (coleta antiga) e dicionário não contam; datas do recurso, não do metadado
    assert saude["recursos_validos"] == 2 and saude["formatos"] == ["CSV", "XLSX"]
    assert saude["ultima_atualizacao"].startswith("2026-09-05")
    assert saude["ultima_atualizacao_estimada"] is False
    assert saude["metadata_modified"].startswith("2026-10-01")
    assert saude["situacao"] == "Publicado" and saude["orgao_nome"] == "Secretaria da Saúde"
    assert linhas["ds-vazio"]["situacao"] == "Sem recurso"
    assert linhas["ds-vazio"]["recursos_validos"] == 0
    assert linhas["ds-antigo"]["situacao"] == "Fora do portal"
    assert corpo["opcoes"]["formatos"] == ["CSV", "XLSX"]
    assert corpo["opcoes"]["situacoes"] == ["Publicado", "Sem recurso", "Fora do portal"]
    assert [o["valor"] for o in corpo["opcoes"]["orgaos"]] == [str(SEDUC), str(SES)]


@pytest.mark.parametrize("params,esperados", [
    ({"busca": "saude"}, ["ds-saude"]),          # sem acento
    ({"busca": "LEITOS"}, ["ds-vazio"]),
    ({"busca": "indicadores-saude"}, ["ds-saude"]),  # pelo name
    ({"orgao": SES}, ["ds-saude", "ds-vazio"]),
    ({"formato": "xlsx"}, ["ds-saude"]),
    ({"formato": "PDF"}, []),                    # PDF só em dicionário: não conta
    ({"situacao": "Sem recurso"}, ["ds-vazio"]),
    ({"busca": " ", "orgao": ""}, ["ds-saude", "ds-vazio", "ds-antigo"]),
])
def test_filtros(client, gerente, inventario, params, esperados):
    corpo = _lista(client, gerente, **params)
    assert [d["id_ckan"] for d in corpo["datasets"]] == esperados
    assert corpo["total"] == 3


def test_detalhe_do_dataset(client, gerente, inventario):
    r = client.get(f"{API}/datasets/{SAUDE}", headers=gerente)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["descricao"] == "Indicadores mensais." and d["periodicidade_declarada"] == "Mensal"
    assert d["metadata_created"].startswith("2023-01-10") and d["licenca"] == "cc-by"
    # Recursos atuais (dicionário por último, marcado); o apagado só entra na contagem à parte
    assert [x["id_ckan"] for x in d["recursos"]] == ["r-csv", "r-xlsx", "r-dic"]
    assert d["recursos"][2]["eh_dicionario_dados"] is True
    assert d["recursos_removidos"] == 1
    assert client.get(f"{API}/datasets/9999", headers=gerente).status_code == 404


def test_estimada_pela_criacao(client, gerente, inventario):
    with SessionLocal() as db:
        db.get(Recurso, 1).last_modified = None
        db.commit()
    saude = next(d for d in _lista(client, gerente)["datasets"] if d["id_ckan"] == "ds-saude")
    assert saude["ultima_atualizacao"].startswith("2026-09-01")
    assert saude["ultima_atualizacao_estimada"] is True


def test_permissoes_e_escopo_de_orgao(client, gerente, orgao, inventario):
    # Papel padrão de órgão não tem inventario.acessar
    assert client.get(f"{API}/datasets", headers=orgao).status_code == 403
    assert client.get(f"{API}/datasets/{SAUDE}", headers=orgao).status_code == 403


def test_bases_do_pda_vinculadas_ao_dataset(client, gerente, analista, inventario):
    url = "https://dadosabertos.go.gov.br/dataset/"
    texto = ("Orgão;Base de Dados;Atualização;Meta/Prazo para abertura;Disponível no Portal\n"
             f"SES;Indicadores;Mensal;Março/2025;{url}indicadores-saude\n"
             "SES;Leitos;Mensal;Dezembro/2026;Não\n")
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", texto.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    bases = client.get(f"/api/v1/pda/datasets/{SAUDE}/bases", headers=analista).json()
    assert len(bases) == 1
    b = bases[0]
    assert b["nome_previsto"] == "Indicadores" and b["prazo_abertura"] == "2025-03-31"
    assert b["periodicidade"] == "Mensal" and b["situacao"] == "Publicado"
    # Sem vínculo pelo ID → nenhuma base (nunca casa pelo nome "Leitos")
    assert client.get(f"/api/v1/pda/datasets/{VAZIO}/bases", headers=analista).json() == []


def test_dataset_e_recurso_excluidos_nao_aparecem(client, gerente, inventario):
    """Exclusão lógica (ADR-0019): dataset excluído some da lista e do detalhe; recurso excluído
    não conta nem aparece."""
    with SessionLocal() as db:
        db.get(Dataset, VAZIO).deleted = True
        db.get(Recurso, 2).deleted = True  # r-xlsx
        db.commit()
    corpo = _lista(client, gerente)
    assert corpo["total"] == 2 and [d["id_ckan"] for d in corpo["datasets"]] == [
        "ds-saude", "ds-antigo"]
    saude = corpo["datasets"][0]
    assert saude["recursos_validos"] == 1 and saude["formatos"] == ["CSV"]
    assert client.get(f"{API}/datasets/{VAZIO}", headers=gerente).status_code == 404
    d = client.get(f"{API}/datasets/{SAUDE}", headers=gerente).json()
    assert [x["id_ckan"] for x in d["recursos"]] == ["r-csv", "r-dic"]
