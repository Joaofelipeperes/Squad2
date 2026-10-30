"""Tela Monitoramento de Atualizações (US9/US10): GET /atualizacoes/datasets. Dados fictícios."""
from tests.test_painel_organizacoes import _hoje, inventario  # noqa: F401 (fixtures)
from tests.test_painel_visao_geral import PDA

API = "/api/v1/atualizacoes/datasets"


def _importar_pda(client, gerente):
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", PDA.encode(), "text/csv")})
    assert r.status_code == 201, r.text


def test_sem_pda_vigente(client, gerente, inventario):  # noqa: F811
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano_nome"] is None and corpo["total"] == 0 and corpo["datasets"] == []


def test_lista_datasets_vinculados_ao_pda(client, gerente, inventario):  # noqa: F811
    _importar_pda(client, gerente)
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano_nome"] == "PDA teste" and corpo["total"] == 2  # só as bases vinculadas
    por_nome = {d["dataset_name"]: d for d in corpo["datasets"]}
    ind = por_nome["indicadores-saude"]
    # Hoje = 18/10/2026; last_modified do recurso em 01/09/2026: 47 dias, prazo 01/10 (Mensal)
    assert ind["situacao"] == "Atrasado" and ind["dias_desde_atualizacao"] == 47
    assert ind["prazo_esperado"] == "2026-10-01" and ind["periodicidade"] == "Mensal"
    assert por_nome["antigo"]["situacao"] == "Sem informação"  # dataset fora do portal
    assert corpo["resumo"] == {"atualizados": 0, "atrasados": 1, "proximos_do_vencimento": 0,
                               "sem_informacao": 1}
    assert corpo["opcoes"]["periodicidades"] == ["Mensal", "Anual"]
    assert {o["valor"] for o in corpo["opcoes"]["orgaos"]} == {d["orgao_chave"]
                                                              for d in corpo["datasets"]}


def test_filtros(client, gerente, inventario):  # noqa: F811
    _importar_pda(client, gerente)
    todos = client.get(API, headers=gerente).json()

    def nomes(**filtros):
        corpo = client.get(API, headers=gerente, params=filtros).json()
        assert corpo["total"] == 2 and corpo["resumo"] == todos["resumo"]  # cartões ignoram filtros
        return [d["dataset_name"] for d in corpo["datasets"]]

    assert nomes(situacao="Atrasado") == ["indicadores-saude"]
    assert nomes(periodicidade="Anual") == ["antigo"]
    assert nomes(dataset="INDICADORES") == ["indicadores-saude"]  # sem caixa
    assert nomes(dataset="inexistente") == []
    chave = todos["datasets"][0]["orgao_chave"]
    esperado = [d["dataset_name"] for d in todos["datasets"] if d["orgao_chave"] == chave]
    assert nomes(orgao=chave) == esperado
    assert nomes(orgao=chave, situacao="Atualizado") == []


def test_exige_permissao(client, inventario):  # noqa: F811
    assert client.get(API).status_code == 401
