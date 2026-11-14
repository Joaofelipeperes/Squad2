"""Tela Monitoramento de Atualizações (US9/US10, ADR-0037): GET /atualizacoes/datasets.

Todos os datasets publicados no portal entram, previstos no PDA ou espontâneos; a periodicidade
vem só do campo "Atualização" do CKAN. Dados fictícios."""
from datetime import UTC, datetime

import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Dataset, Recurso
from tests.conftest import SEDUC
from tests.test_painel_organizacoes import DS_A, DS_B, _hoje, inventario  # noqa: F401 (fixtures)
from tests.test_painel_visao_geral import PDA

API = "/api/v1/atualizacoes/datasets"
DS_D, DS_E = 10, 11


@pytest.fixture
def com_periodicidade(inventario):  # noqa: F811
    """SES: indicadores-saude "Mensal " (último recurso em 01/09, atrasado), leitos "Não possui
    atualização periódica" (sem data). SEDUC: matriculas sem o campo e escolas com valor inválido
    (os dois "Periodicidade não informada"), e um dataset fora do portal que não entra."""
    lm = datetime(2026, 10, 10, tzinfo=UTC)
    with SessionLocal() as db:
        db.get(Dataset, DS_A).extras = {"Atualização": "Mensal ", "Fonte": "SES"}
        db.get(Dataset, DS_B).extras = {"Atualização ": "Não possui atualização periódica"}
        db.add_all([
            Dataset(id=DS_D, id_ckan="ds-d", name="matriculas", titulo="Matrículas",
                    organizacao_id=SEDUC, ultima_coleta_id=2, extras={"Fonte": "SEDUC"}),
            Dataset(id=DS_E, id_ckan="ds-e", name="escolas", titulo="Escolas",
                    organizacao_id=SEDUC, ultima_coleta_id=2,
                    extras={"Atualização": "Quando houver"}),
        ])
        db.add_all([
            Recurso(id=20, id_ckan="r20", dataset_id=DS_D, formato="CSV", ultima_coleta_id=2,
                    last_modified=lm),
            Recurso(id=21, id_ckan="r21", dataset_id=DS_E, formato="CSV", ultima_coleta_id=2,
                    last_modified=lm),
        ])
        db.commit()


def _importar_pda(client, gerente):
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", PDA.encode(), "text/csv")})
    assert r.status_code == 201, r.text


def _por_nome(corpo):
    return {d["dataset_name"]: d for d in corpo["datasets"]}


def test_sem_pda_vigente_todos_os_publicados_entram_como_espontaneos(client, gerente,
                                                                       com_periodicidade):
    corpo = client.get(API, headers=gerente).json()
    # 4 ativos no portal; "antigo" (fora do portal) não entra
    assert corpo["plano_nome"] is None and corpo["total"] == 4
    assert set(_por_nome(corpo)) == {"indicadores-saude", "leitos", "matriculas", "escolas"}
    assert {d["tipo_base"] for d in corpo["datasets"]} == {"Espontânea"}


def test_situacao_pela_periodicidade_do_ckan(client, gerente, com_periodicidade):
    _importar_pda(client, gerente)
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano_nome"] == "PDA teste" and corpo["total"] == 4
    d = _por_nome(corpo)
    ind = d["indicadores-saude"]
    # Hoje = 18/10/2026; last_modified do recurso em 01/09/2026: 47 dias, prazo 01/10 (Mensal)
    assert ind["tipo_base"] == "Prevista no PDA" and ind["periodicidade_declarada"] == "Mensal"
    assert ind["situacao"] == "Atrasado" and ind["dias_desde_atualizacao"] == 47
    assert ind["prazo_esperado"] == "2026-10-01" and ind["periodicidade"] == "Mensal"
    # Declaração válida do órgão: sem prazo, não é atraso nem não conformidade
    assert d["leitos"]["periodicidade"] == "Sem atualização periódica"
    assert d["leitos"]["situacao"] == "Sem atualização periódica"
    assert d["leitos"]["tipo_base"] == "Espontânea" and d["leitos"]["prazo_esperado"] is None
    # Campo ausente ou inválido: "Periodicidade não informada", mesmo com data de atualização
    for nome, declarada in (("matriculas", None), ("escolas", "Quando houver")):
        assert d[nome]["situacao"] == "Periodicidade não informada"
        assert d[nome]["periodicidade_declarada"] == declarada
        assert d[nome]["dias_desde_atualizacao"] == 8
    assert corpo["resumo"] == {
        "atualizados": 0, "atrasados": 1, "proximos_do_vencimento": 0,
        "sem_atualizacao_periodica": 1, "periodicidade_nao_informada": 2, "sem_data": 0,
        "previstas_no_pda": 1, "espontaneas": 3}
    assert corpo["opcoes"]["periodicidades"] == [
        "Mensal", "Sem atualização periódica", "Periodicidade não informada"]
    assert corpo["opcoes"]["tipos_base"] == ["Prevista no PDA", "Espontânea"]
    assert {o["valor"] for o in corpo["opcoes"]["orgaos"]} == {x["orgao_chave"]
                                                              for x in corpo["datasets"]}


def test_periodicidade_do_pda_nao_e_usada(client, gerente, inventario):  # noqa: F811
    """Sem o campo no CKAN, a periodicidade "Mensal" da planilha do PDA não vale (ADR-0037)."""
    _importar_pda(client, gerente)
    ind = _por_nome(client.get(API, headers=gerente).json())["indicadores-saude"]
    assert ind["tipo_base"] == "Prevista no PDA"
    assert ind["situacao"] == "Periodicidade não informada" and ind["prazo_esperado"] is None


def test_filtros(client, gerente, com_periodicidade):
    _importar_pda(client, gerente)
    todos = client.get(API, headers=gerente).json()

    def nomes(**filtros):
        corpo = client.get(API, headers=gerente, params=filtros).json()
        assert corpo["total"] == 4 and corpo["resumo"] == todos["resumo"]  # cartões ignoram filtros
        return sorted(d["dataset_name"] for d in corpo["datasets"])

    assert nomes(situacao="Atrasado") == ["indicadores-saude"]
    assert nomes(situacao="Periodicidade não informada") == ["escolas", "matriculas"]
    assert nomes(periodicidade="Sem atualização periódica") == ["leitos"]
    assert nomes(tipo_base="Prevista no PDA") == ["indicadores-saude"]
    assert nomes(tipo_base="Espontânea") == ["escolas", "leitos", "matriculas"]
    assert nomes(dataset="INDICADORES") == ["indicadores-saude"]  # sem caixa
    assert nomes(dataset="inexistente") == []
    assert nomes(orgao=str(SEDUC)) == ["escolas", "matriculas"]
    assert nomes(orgao=str(SEDUC), situacao="Atualizado") == []


def test_exige_permissao(client, inventario):  # noqa: F811
    assert client.get(API).status_code == 401
