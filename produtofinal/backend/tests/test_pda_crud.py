"""CRUD manual do PDA: criar PDA sem planilha, editar, excluir e incluir/editar/remover bases.
Dados fictícios."""
from datetime import UTC, date, datetime

import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Coleta, Dataset, Organizacao, Recurso
from app.modules.pda import service
from tests.test_pda_revisao import _importar

API = "/api/v1/pda"
URL = "https://dadosabertos.go.gov.br/dataset/"


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(service, "hoje_local", lambda: date(2026, 10, 13))


@pytest.fixture
def inventario():
    """Organização "administracao" com um dataset publicado (um recurso válido)."""
    with SessionLocal() as db:
        db.add(Organizacao(ckan_id="org-adm", name="administracao",
                           titulo="Secretaria da Administração"))
        db.add(Coleta(id=1, status="ok"))
        db.add(Dataset(ckan_id="ds-folha", name="folha-de-pagamento", titulo="Folha",
                       organizacao_id="org-adm", ultima_coleta_id=1))
        db.add(Recurso(ckan_id="r-1", dataset_id="ds-folha", nome="folha.csv", formato="CSV",
                       ultima_coleta_id=1, last_modified=datetime(2026, 9, 26, tzinfo=UTC)))
        db.commit()


def _criar_plano(client, h, nome="PDA manual", **campos):
    return client.post(f"{API}/planos/manual", headers=h, json={"nome": nome, **campos})


def _base(**campos):
    return {"orgao_sigla": "SEAD", "nome_previsto": "Folha de Pagamento", **campos}


def _plano(client, h, plano_id):
    return client.get(f"{API}/planos/{plano_id}", headers=h).json()


# ---------------------------------------------------------- PDA
def test_criar_pda_manual_vazio(client, gerente, analista):
    r = _criar_plano(client, gerente, vigencia_inicio="2025-01-01", vigencia_fim="2027-12-31")
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["vigente"] is True  # primeiro PDA cadastrado
    assert p["total_bases"] == 0 and p["arquivo_nome"] is None and p["importado_por"] == "Paloma"
    assert _criar_plano(client, gerente, nome="pda MANUAL").status_code == 409
    assert _criar_plano(client, gerente, nome="   ").status_code == 422
    assert _criar_plano(client, analista, nome="Outro").status_code == 403
    # Segundo PDA só vira vigente se pedido
    assert _criar_plano(client, gerente, nome="PDA 2").json()["vigente"] is False
    assert _criar_plano(client, gerente, nome="PDA 3", definir_vigente=True).json()["vigente"]
    assert _plano(client, gerente, p["id"])["vigente"] is False


def test_editar_pda(client, gerente, analista):
    p1 = _criar_plano(client, gerente).json()
    p2 = _criar_plano(client, gerente, nome="PDA 2").json()
    r = client.put(f"{API}/planos/{p1['id']}", headers=gerente,
                   json={"nome": "  PDA   2025-2027 ", "vigencia_inicio": "2025-01-01"})
    assert r.status_code == 200, r.text
    assert r.json()["nome"] == "PDA 2025-2027" and r.json()["vigencia_inicio"] == "2025-01-01"
    assert r.json()["vigente"] is True  # editar não troca o vigente
    # O próprio nome (com outra caixa) pode; o nome de outro PDA não
    assert client.put(f"{API}/planos/{p1['id']}", headers=gerente,
                      json={"nome": "pda 2025-2027"}).status_code == 200
    assert client.put(f"{API}/planos/{p1['id']}", headers=gerente,
                      json={"nome": "pda 2"}).status_code == 409
    assert client.put(f"{API}/planos/{p2['id']}", headers=gerente,
                      json={"nome": "PDA 2", "vigencia_inicio": "2026-01-01",
                            "vigencia_fim": "2025-01-01"}).status_code == 422
    assert client.put(f"{API}/planos/9999", headers=gerente, json={"nome": "X"}).status_code == 404
    assert client.put(f"{API}/planos/{p2['id']}", headers=analista,
                      json={"nome": "X"}).status_code == 403


def test_excluir_vigente_so_quando_unico(client, gerente):
    p1 = _criar_plano(client, gerente).json()
    p2 = _criar_plano(client, gerente, nome="PDA 2").json()
    assert client.delete(f"{API}/planos/{p1['id']}", headers=gerente).status_code == 409
    assert client.delete(f"{API}/planos/{p2['id']}", headers=gerente).status_code == 204
    assert client.delete(f"{API}/planos/{p1['id']}", headers=gerente).status_code == 204
    assert client.get(f"{API}/planos", headers=gerente).json() == []


# ---------------------------------------------------------- bases
def test_incluir_bases_com_e_sem_vinculo(client, gerente, inventario):
    p = _criar_plano(client, gerente).json()
    url = f"{API}/planos/{p['id']}/bases"
    r = client.post(url, headers=gerente, json=_base(
        dataset_link=f"{URL}folha-de-pagamento/", periodicidade="Mensal",
        prazo_abertura="2025-12-31", possui_conteudo_sigiloso=False))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["vinculo"] == "resolvido" and b["dataset_id"] == "ds-folha"
    assert b["orgao_chave"] == "org-adm"  # órgão do dataset vinculado
    assert b["situacao"] == "Publicado" and b["recursos_validos"] == 1

    # Sem link: SEAD herda a organização pela evidência do vínculo por ID neste PDA
    b2 = client.post(url, headers=gerente, json=_base(
        nome_previsto="Movimentações", periodicidade="Múltipla",
        prazo_abertura="2025-03-31")).json()
    assert b2["vinculo"] == "sem_vinculo" and b2["orgao_chave"] == "org-adm"
    assert b2["periodicidade"] == "Múltipla" and b2["situacao"] == "Prazo vencido"

    # Name sem dataset no inventário → vínculo pendente; órgão escolhido no formulário
    b3 = client.post(url, headers=gerente, json=_base(
        orgao_sigla="SEDUC", organizacao_id="org-seduc", nome_previsto="Escolas",
        dataset_link="escolas-estaduais")).json()
    assert b3["vinculo"] == "pendente" and b3["dataset_name_planilha"] == "escolas-estaduais"
    assert b3["orgao_chave"] == "org-seduc"

    assert _plano(client, gerente, p["id"])["total_bases"] == 3
    assert client.get(f"{API}/bases", headers=gerente).json()["total_previstas"] == 3


@pytest.mark.parametrize("campos,mensagem", [
    ({"orgao_sigla": " "}, "órgão"),
    ({"nome_previsto": ""}, "nome da base"),
    ({"dataset_link": "https://outro.site/x?y=1"}, "Endereço do dataset"),
    ({"organizacao_id": "org-inexistente"}, "Organização não encontrada"),
    # dataset da administração com órgão SEDUC escolhido: incoerente
    ({"organizacao_id": "org-seduc", "dataset_link": "folha-de-pagamento"}, "outra organização"),
])
def test_incluir_base_invalida(client, gerente, inventario, campos, mensagem):
    p = _criar_plano(client, gerente).json()
    r = client.post(f"{API}/planos/{p['id']}/bases", headers=gerente, json=_base(**campos))
    assert r.status_code == 422 and mensagem in r.json()["detail"]
    assert _plano(client, gerente, p["id"])["total_bases"] == 0


def test_incluir_base_permissoes_e_plano_inexistente(client, gerente, analista, orgao):
    assert client.post(f"{API}/planos/9999/bases", headers=gerente,
                       json=_base()).status_code == 404
    p = _criar_plano(client, gerente).json()
    for h in (analista, orgao):
        assert client.post(f"{API}/planos/{p['id']}/bases", headers=h,
                           json=_base()).status_code == 403


def test_editar_base(client, gerente, inventario):
    r = _importar(client, gerente, "PDA importado",
                  "Orgão;Base de Dados;Atualização;Disponível no Portal\n"
                  f"SEAD;Folha;Mnsal;{URL}folha-de-pagamento\n")
    base = client.get(f"{API}/bases", headers=gerente).json()["bases"][0]
    assert base["periodicidade_original"] == "Mnsal"
    url = f"{API}/bases/{base['id']}"

    # Mesmo endereço e mesma periodicidade: vínculo e texto original da planilha mantidos
    r = client.put(url, headers=gerente, json=_base(
        nome_previsto="Folha de Pagamento", periodicidade="Mensal",
        dataset_link="folha-de-pagamento", descricao="Servidores ativos"))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["nome_previsto"] == "Folha de Pagamento" and b["descricao"] == "Servidores ativos"
    assert b["vinculo"] == "resolvido" and b["dataset_id"] == "ds-folha"
    assert b["periodicidade"] == "Mensal" and b["periodicidade_original"] == "Mnsal"

    # Endereço apagado → sem vínculo; periodicidade nova substitui o texto original
    b = client.put(url, headers=gerente, json=_base(periodicidade="Anual",
                                                     prazo_abertura="2027-06-30")).json()
    assert b["vinculo"] == "sem_vinculo" and b["dataset_id"] is None
    assert b["periodicidade"] == "Anual" and b["periodicidade_original"] == "Anual"
    assert b["situacao"] == "Em dia"  # não publicada, prazo além da janela de alerta

    assert client.put(f"{API}/bases/9999", headers=gerente, json=_base()).status_code == 404


def test_excluir_base(client, gerente, analista):
    p = _criar_plano(client, gerente).json()
    url = f"{API}/planos/{p['id']}/bases"
    b1 = client.post(url, headers=gerente, json=_base()).json()
    client.post(url, headers=gerente, json=_base(nome_previsto="Outra"))
    assert client.delete(f"{API}/bases/{b1['id']}", headers=analista).status_code == 403
    assert client.delete(f"{API}/bases/{b1['id']}", headers=gerente).status_code == 204
    assert client.delete(f"{API}/bases/{b1['id']}", headers=gerente).status_code == 404
    assert client.get(f"{API}/bases/{b1['id']}", headers=gerente).status_code == 404
    assert _plano(client, gerente, p["id"])["total_bases"] == 1


def test_opcoes_do_formulario(client, gerente, analista):
    r = client.get(f"{API}/formulario", headers=gerente)
    assert r.status_code == 200
    corpo = r.json()
    assert [o["valor"] for o in corpo["organizacoes"]] == ["org-seduc", "org-ses"]
    assert "Múltipla" in corpo["periodicidades"] and "Mensal" in corpo["periodicidades"]
    assert client.get(f"{API}/formulario", headers=analista).status_code == 403
