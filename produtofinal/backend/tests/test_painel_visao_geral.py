"""Tela Visão Geral (Dashboard, US19/PBI-56) e datasets sem recurso (PBI-51). Dados fictícios."""
import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Dataset, Recurso
from tests.conftest import SEDUC
from tests.test_painel_organizacoes import _hoje, inventario  # noqa: F401 (fixtures)

API = "/api/v1/painel/visao-geral"
URL = "https://dadosabertos.go.gov.br/dataset/"
DS_D = 4

# Hoje = 18/10/2026. "Indicadores" (ds-a) tem last_modified em 01/09/2026: 47 dias
PDA = ("Orgão;Base de Dados;Atualização;Meta/Prazo para abertura;Disponível no Portal\n"
       f"SES;Indicadores;Mensal;Março/2025;{URL}indicadores-saude\n"  # publicada; atualização atrasada
       "SES;Vacinas;Mensal;Março/2025;Não\n"                           # prazo vencido, sem vínculo
       f"SES;Antiga;Anual;Março/2025;{URL}antigo\n"                   # vinculada, fora do portal
       "SES;Leitos;Mensal;Outubro/2026;Não\n"                          # próximo do prazo
       "SEDUC;Matrículas;Anual;Dezembro/2027;Não\n"                    # em dia
       "XYZ;Base sem órgão;Eventual;Março/2025;Não\n")                 # prazo vencido, sem órgão


@pytest.fixture
def so_dicionario(inventario):  # noqa: F811
    """Dataset ativo da SEDUC só com o dicionário de dados: conta como sem recurso."""
    with SessionLocal() as db:
        db.add(Dataset(id=DS_D, id_ckan="ds-d", name="escolas", titulo="Escolas",
                       organizacao_id=SEDUC, ultima_coleta_id=2))
        db.add(Recurso(id=8, id_ckan="r8", dataset_id=DS_D, nome="Dicionário", formato="PDF",
                       eh_dicionario_dados=True, ultima_coleta_id=2))
        db.commit()


def _situacoes(corpo, chave="situacoes_pda"):
    return {c["rotulo"]: c["total"] for c in corpo[chave]}


def test_visao_geral_sem_pda(client, gerente, so_dicionario):
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"] is None and corpo["hoje"] == "2026-10-18"
    k = corpo["kpis"]
    assert k["orgaos_monitorados"] == 2 and k["bases_previstas"] == 0
    assert k["bases_em_atraso"] is None  # sem base vinculada não há atraso confirmado
    # Inventário: só datasets ativos; recursos atuais sem dicionário (r1, r2, r5, r6)
    assert (k["datasets_publicados"], k["datasets_fora_do_portal"]) == (3, 1)
    assert k["recursos_monitorados"] == 4 and k["datasets_sem_recurso"] == 1
    assert k["atualizacoes_em_atraso"] is None and k["possiveis_dados_pessoais"] is None
    assert set(_situacoes(corpo).values()) == {0}
    assert set(_situacoes(corpo, "situacoes_atualizacao").values()) == {0}
    assert [a["item"] for a in corpo["alertas"]] == ["Escolas"]
    assert corpo["alertas"][0]["tipo"] == "Inventário"
    assert corpo["alertas"][0]["destino"] == "/datasets"


def test_visao_geral_com_pda_vigente(client, gerente, so_dicionario):
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", PDA.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"]["nome"] == "PDA teste"
    k = corpo["kpis"]
    assert (k["bases_previstas"], k["bases_vinculadas"], k["bases_publicadas"]) == (6, 2, 1)
    assert k["bases_em_atraso"] == 1 and k["bases_prazo_vencido"] == 2
    assert k["orgaos_no_pda"] == 3  # SES, SEDUC e a sigla XYZ sem organização
    s = _situacoes(corpo)
    assert (s["Publicado"], s["Em atraso"], s["Prazo vencido"]) == (1, 1, 2)
    assert (s["Próximo do prazo"], s["Em dia"], s["Sem recurso"]) == (1, 1, 0)
    # Alertas: atraso confirmado, depois prazo próximo, depois inventário; prazo vencido sem
    # vínculo não vira alerta
    assert [(a["situacao"], a["item"]) for a in corpo["alertas"]] == [
        ("Em atraso", "Antiga"), ("Atualização atrasada", "Indicadores"),
        ("Próximo do prazo", "Leitos"), ("Dataset sem recurso", "Escolas")]
    atrasada = corpo["alertas"][1]
    assert atrasada["tipo"] == "Atualização" and atrasada["prazo"] == "2026-10-01"  # 01/09 + 30
    # Atualização pela periodicidade do PDA: só as vinculadas são avaliadas
    a = _situacoes(corpo, "situacoes_atualizacao")
    assert (a["Atrasado"], a["Sem informação"], a["Aguardando vínculo"]) == (1, 1, 4)
    assert a["Atualizado"] == 0 and k["atualizacoes_em_atraso"] == 1
    assert corpo["alertas"][0]["destino"].startswith("/pda?orgao=")
    assert corpo["total_alertas"] == 4
    assert corpo["alertas_por_tipo"] == {"PDA": 2, "Atualização": 1, "Inventário": 1}


def test_visao_geral_permissao(client, analista, orgao):
    assert client.get(API, headers=analista).status_code == 200
    assert client.get(API, headers=orgao).status_code == 403


def test_alertas_ate_10_por_tipo(monkeypatch, client, gerente, so_dicionario):
    """Um tipo numeroso não esconde os outros: até 10 de cada tipo, com o total por tipo."""
    from app.modules.painel import service
    monkeypatch.setattr(service, "ALERTAS_MAXIMO", 1)
    client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                files={"arquivo": ("pda.csv", PDA.encode(), "text/csv")})
    corpo = client.get(API, headers=gerente).json()
    assert [a["tipo"] for a in corpo["alertas"]] == ["PDA", "Atualização", "Inventário"]
    assert corpo["alertas_por_tipo"]["PDA"] == 2 and corpo["total_alertas"] == 4
