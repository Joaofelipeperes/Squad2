"""Importação do PDA com mapeamento de colunas e importação em lote dos IDs do CKAN.
Dados fictícios (IDs gerados para o teste)."""
import json
from datetime import date

import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Coleta, Dataset, Organizacao
from app.modules.pda import regras, service

API = "/api/v1/pda"
ID_CONV = "7383caee-1523-4eb7-8cf4-63157a1e1735"
ID_TERC = "5e921182-f6bb-4e3d-b294-84ad243a2fc1"
ID_OUTRO = "f495c5eb-5aed-4ac0-a3e7-cd1eb2d6061c"
ID_FORA = "11111111-2222-4333-8444-555555555555"  # UUID válido que não está no inventário
ABC = 3  # `id` próprio da organização ABC (1 e 2 vêm do conftest)

# Formato da "TABELA_FATO_PDA" da GEDA: SIGLA e ORGAO (por extenso), nomes próprios das colunas
TABELA_FATO = (
    "SIGLA;ORGAO;NOME_PDA;NOME_DA_BASE_CKAN;ID_UNICO;PERIODICIDADE;PREVISAO_DE_ABERTURA\n"
    f"ABC;Agência Brasil Central;Convênios Recebido;Convênios Recebidos - ABC;{ID_CONV};Anual;"
    "01/12/2025\n"
    f"ABC;Agência Brasil Central;Terceirizados;Terceirizados - ABC;{ID_TERC};Anual;01/12/2025\n"
    "AGEHAB;Agência Goiana de Habitação;Aluguel Social;Não encontrado;;Mensal;01/10/2025\n"
)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(service, "hoje_local", lambda: date(2026, 10, 22))


@pytest.fixture
def inventario():
    with SessionLocal() as db:
        db.add_all([
            Organizacao(id=ABC, id_ckan="org-abc", name="abc", titulo="Agência Brasil Central"),
            Coleta(id=1, status="ok"),
        ])
        db.add_all([
            Dataset(id=1, id_ckan=ID_CONV, name="convenios-recebidos-abc",
                    titulo="Convênios - ABC", organizacao_id=ABC, ultima_coleta_id=1),
            Dataset(id=2, id_ckan=ID_TERC, name="terceirizados-abc", titulo="Terceirizados - ABC",
                    organizacao_id=ABC, ultima_coleta_id=1),
            Dataset(id=3, id_ckan=ID_OUTRO, name="acordos-abc", titulo="Acordos - ABC",
                    organizacao_id=ABC, ultima_coleta_id=1),
        ])
        db.commit()


def _arquivo(texto: str, nome="pda.csv", codificacao="utf-8"):
    return {"arquivo": (nome, texto.encode(codificacao), "text/csv")}


# ---------------------------------------------------------- regras: sugestão de colunas
@pytest.mark.parametrize("cabecalho,esperado", [
    # nome igual, ignorando maiúsculas, acentos, espaços e "_"
    (["SIGLA", "ORGAO", "NOME_PDA", "PERIODICIDADE", "PREVISAO_DE_ABERTURA"],
     {"orgao": 0, "base": 2, "periodicidade": 3, "prazo": 4}),
    # planilha clássica do PDA
    (["Orgão", "Base de Dados", "Atualização", "Meta/Prazo para abertura"],
     {"orgao": 0, "base": 1, "periodicidade": 2, "prazo": 3}),
    # muito parecido (plural / erro de digitação)
    (["Orgao", "Bases de Dados", "Periodicidad"], {"orgao": 0, "base": 1, "periodicidade": 2}),
])
def test_sugerir_colunas_pda(cabecalho, esperado):
    assert regras.sugerir_colunas(cabecalho, regras._SINONIMOS_PDA) == esperado


def test_sugestao_por_prefixo_e_coluna_unica():
    sinonimos = {"cpf": ("cpf",), "nome": ("nome",), "nome2": ("nome",)}
    # CPF_cliente → CPF; "Nome" vai para um campo só
    assert regras.sugerir_colunas(["CPF_cliente", "Nome"], sinonimos) == {"cpf": 0, "nome": 1}


@pytest.mark.parametrize("colunas,mensagem", [
    ({"orgao": 0}, "obrigatórios"),
    ({"orgao": 0, "base": 0}, "mais de um campo"),
    ({"orgao": 0, "base": 1, "xyz": 2}, "desconhecido"),
])
def test_validar_mapeamento(colunas, mensagem):
    with pytest.raises(regras.PlanilhaInvalida, match=mensagem):
        regras.validar_mapeamento(colunas, regras.CAMPOS_PDA)


@pytest.mark.parametrize("valor,esperado", [
    (f" {ID_CONV.upper()} ", ID_CONV), ("7383caee-1523", None), ("Não encontrado", None),
    (None, None),
])
def test_normalizar_uuid(valor, esperado):
    assert regras.normalizar_uuid(valor) == esperado


# ---------------------------------------------------------- funcionalidade 1: mapeamento
def test_colunas_da_planilha_com_sugestao_e_previa(client, gerente, analista):
    titulo = "Relatório PDA 2025;;;;;;\n"  # título acima do cabeçalho
    r = client.post(f"{API}/planilha/colunas", headers=gerente, files=_arquivo(titulo + TABELA_FATO))
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["linha"] == 1 and c["colunas"][:3] == ["SIGLA", "ORGAO", "NOME_PDA"]
    sugestao = {f["campo"]: f["sugestao"] for f in c["campos"]}
    assert sugestao["orgao"] == 0 and sugestao["base"] == 2  # SIGLA, não ORGAO por extenso
    assert sugestao["prazo"] == 6 and sugestao["portal"] is None
    assert {f["campo"] for f in c["campos"] if f["obrigatorio"]} == {"orgao", "base"}
    assert len(c["previa"]) == 3 and c["previa"][0][2] == "Convênios Recebido"
    assert c["previa"][2][4] is None  # célula vazia (sem ID)
    assert client.post(f"{API}/planilha/colunas", headers=analista,
                       files=_arquivo(TABELA_FATO)).status_code == 403
    r = client.post(f"{API}/planilha/colunas", headers=gerente, files=_arquivo("x", "a.pdf"))
    assert r.status_code == 422


def test_importar_com_mapeamento(client, gerente, inventario):
    c = client.post(f"{API}/planilha/colunas", headers=gerente, files=_arquivo(TABELA_FATO)).json()
    mapa = {"aba": c["aba"], "linha": c["linha"],
            "colunas": {"orgao": 0, "base": 2, "periodicidade": 5, "prazo": 6}}
    r = client.post(f"{API}/planos", headers=gerente, files=_arquivo(TABELA_FATO),
                    data={"nome": "PDA mapeado", "mapeamento": json.dumps(mapa)})
    assert r.status_code == 201, r.text
    resumo = r.json()
    assert resumo["bases_importadas"] == 3 and resumo["tem_coluna_prazo"] is True
    bases = client.get(f"{API}/bases", headers=gerente,
                       params={"plano_id": resumo["plano"]["id"]}).json()["bases"]
    conv = next(b for b in bases if b["nome_previsto"] == "Convênios Recebido")
    assert conv["orgao_sigla"] == "ABC" and conv["periodicidade"] == "Anual"
    assert conv["prazo_abertura"] == "2025-12-01" and conv["orgao_chave"] == str(ABC)


@pytest.mark.parametrize("mapa,mensagem", [
    ({"aba": 0, "linha": 0, "colunas": {"orgao": 0}}, "obrigatórios"),
    ({"aba": 0, "linha": 0, "colunas": {"orgao": 0, "base": 0}}, "mais de um campo"),
    ({"aba": 0, "linha": 0, "colunas": {"orgao": 0, "base": 40}}, "não existem"),
    ({"aba": 3, "linha": 0, "colunas": {"orgao": 0, "base": 2}}, "Aba"),
])
def test_importar_com_mapeamento_invalido(client, gerente, mapa, mensagem):
    r = client.post(f"{API}/planos", headers=gerente, files=_arquivo(TABELA_FATO),
                    data={"nome": "PDA", "mapeamento": json.dumps(mapa)})
    assert r.status_code == 422 and mensagem in r.json()["detail"]
    assert client.get(f"{API}/planos", headers=gerente).json() == []
    r = client.post(f"{API}/planos", headers=gerente, files=_arquivo(TABELA_FATO),
                    data={"nome": "PDA", "mapeamento": "{não é json"})
    assert r.status_code == 422


# ---------------------------------------------------------- funcionalidade 2: IDs do CKAN
@pytest.fixture
def plano(client, gerente, inventario):
    """PDA com as bases da ABC (uma já vinculada a OUTRO dataset) e da AGEHAB."""
    r = client.post(f"{API}/planos/manual", headers=gerente, json={"nome": "PDA ids"})
    p = r.json()
    url = f"{API}/planos/{p['id']}/bases"
    for nome, sigla, extra in [("Convênios Recebido", "ABC", {}),
                               ("Terceirizados", "ABC", {"dataset_id_ckan": ID_OUTRO}),
                               ("Aluguel Social", "AGEHAB", {})]:
        assert client.post(url, headers=gerente, json={
            "orgao_sigla": sigla, "nome_previsto": nome, **extra}).status_code == 201
    return p


def _ids(client, h, plano_id, texto, codificacao="utf-8", **form):
    return client.post(f"{API}/planos/{plano_id}/ids-ckan", headers=h,
                       files=_arquivo(texto, "ids.csv", codificacao),
                       data={k: str(v).lower() for k, v in form.items()})


def _por_nome(client, h, plano_id):
    bases = client.get(f"{API}/bases", headers=h, params={"plano_id": plano_id}).json()["bases"]
    return {b["nome_previsto"]: b for b in bases}


def test_analisar_ids_nao_grava(client, gerente, plano):
    r = _ids(client, gerente, plano["id"], TABELA_FATO)
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["aplicado"] is False and a["atualizadas"] == 0 and a["total_linhas"] == 3
    assert [(x["nome_pda"], x["dataset_id"]) for x in a["atualizar"]] == [
        ("Convênios Recebido", ID_CONV)]
    assert [(x["nome_pda"], x["id_atual"], x["dataset_id"]) for x in a["substituir"]] == [
        ("Terceirizados", ID_OUTRO, ID_TERC)]
    assert a["sem_id"] == 1 and a["sem_base"] == [] and a["invalidas"] == []
    assert _por_nome(client, gerente, plano["id"])["Convênios Recebido"]["dataset_id_ckan"] is None


def test_aplicar_ids_sem_e_com_sobrescrever(client, gerente, plano):
    # Latin-1 (CSV salvo pelo Excel) e separador ","
    texto = TABELA_FATO.replace(";", ",")
    a = _ids(client, gerente, plano["id"], texto, "latin-1", aplicar=True).json()
    assert a["aplicado"] is True and a["atualizadas"] == 1
    bases = _por_nome(client, gerente, plano["id"])
    assert bases["Convênios Recebido"]["dataset_id_ckan"] == ID_CONV
    assert bases["Convênios Recebido"]["vinculo"] == "resolvido"
    assert bases["Convênios Recebido"]["orgao_chave"] == str(ABC)
    assert bases["Terceirizados"]["dataset_id_ckan"] == ID_OUTRO  # sem confirmação, não sobrescreve

    a = _ids(client, gerente, plano["id"], texto, "latin-1", aplicar=True,
             sobrescrever=True).json()
    assert a["atualizadas"] == 1 and a["iguais"] == 1
    assert _por_nome(client, gerente, plano["id"])["Terceirizados"]["dataset_id_ckan"] == ID_TERC


def test_ids_comparacao_tolerante_e_problemas(client, gerente, plano):
    texto = (
        "SIGLA;NOME_ORGAO;NOME_PDA;NOME_DATASET;ID_DATASET\n"
        f" abc ;Agência;  CONVENIOS   recebido ;Convênios;{ID_CONV.upper()}\n"  # casa
        "ABC;Agência;Base inexistente;X;" + ID_CONV + "\n"
        "AGEHAB;Agência;Aluguel Social;X;não-é-uuid\n"
        f"AGEHAB;Agência;Aluguel Social;X;{ID_FORA}\n"
    )
    a = _ids(client, gerente, plano["id"], texto).json()
    assert [x["dataset_id"] for x in a["atualizar"]] == [ID_CONV]
    assert [x["linha"] for x in a["sem_base"]] == [3]
    motivos = {x["linha"]: x["motivo"] for x in a["invalidas"]}
    assert "UUID" in motivos[4] and "inventário" in motivos[5]


def test_ids_mesma_base_com_ids_diferentes(client, gerente, plano):
    texto = ("SIGLA;NOME_PDA;ID_DATASET\n"
             f"ABC;Convênios Recebido;{ID_CONV}\nABC;Convênios Recebido;{ID_OUTRO}\n")
    a = _ids(client, gerente, plano["id"], texto, aplicar=True).json()
    assert a["atualizadas"] == 0 and len(a["invalidas"]) == 2
    assert "outra linha" in a["invalidas"][0]["motivo"]


def test_ids_cabecalho_ausente_e_permissoes(client, gerente, analista, plano):
    r = _ids(client, gerente, plano["id"], "A;B\n1;2\n")
    assert r.status_code == 422 and "SIGLA" in r.json()["detail"]
    assert _ids(client, analista, plano["id"], TABELA_FATO).status_code == 403
    assert _ids(client, gerente, 9999, TABELA_FATO).status_code == 404
