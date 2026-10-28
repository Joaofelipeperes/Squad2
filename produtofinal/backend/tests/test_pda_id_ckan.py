"""Importação do PDA com o ID do dataset no CKAN na planilha (coluna "ID_UNICO") e configuração
da leitura (colunas, linha do cabeçalho e delimitador) escolhida no modal. Formato da tabela fato
do PDA: SIGLA;ORGAO;NOME_PDA;NOME_DA_BASE_CKAN;ID_UNICO;PERIODICIDADE;PREVISAO_DE_ABERTURA.
Órgãos e nomes de bases públicos; IDs fictícios."""
import json
from datetime import UTC, date, datetime

import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Coleta, Dataset, Organizacao
from app.modules.pda import regras, service
from tests.conftest import SEDUC
from tests.test_pda_revisao import _importar

API = "/api/v1/pda"
HAB = 3  # `id` próprio da organização criada em `habitacao`
ID_CONV = "91fdefd9-0000-4000-8000-000000000001"   # no inventário
ID_TERC = "48022f62-0000-4000-8000-000000000002"   # no inventário
ID_NOVO = "2335814a-0000-4000-8000-000000000003"   # ainda não coletado
CAB = "SIGLA;ORGAO;NOME_PDA;NOME_DA_BASE_CKAN;ID_UNICO;PERIODICIDADE;PREVISAO_DE_ABERTURA"
LINHAS = [
    f"AGEHAB;Agência Goiana de Habitação;Convênios Recebidos;Convênios Recebidos - AGEHAB;"
    f"{ID_CONV.upper()};Mensal;01/11/2025",
    f"AGEHAB;Agência Goiana de Habitação;Relação de Terceirizados;Terceirizados - AGEHAB;"
    f"{ID_TERC};Mensal;01/09/2025",
    f"AGEHAB;Agência Goiana de Habitação;Concursos Públicos;Concursos - AGEHAB;{ID_NOVO};"
    "Mensal;01/09/2025",
    "AGEHAB;Agência Goiana de Habitação;Aluguel Social;Não encontrado;;Mensal;01/10/2025",
    "SEDUC;Secretaria da Educação;Obras;Não encontrado;Não encontrado;Anual;01/12/2025",
    "SEDUC;Secretaria da Educação;Merenda;Merenda - SEDUC;merenda-escolar;Anual;01/12/2025",
]
CSV = "\n".join([CAB, *LINHAS]) + "\n"


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(service, "hoje_local", lambda: date(2026, 10, 8))


@pytest.fixture
def habitacao():
    with SessionLocal() as db:
        db.add(Organizacao(id=HAB, id_ckan="org-agehab", name="agencia-goiana-de-habitacao",
                           titulo="Agência Goiana de Habitação"))
        db.add(Coleta(id=1, status="ok"))
        db.add_all([
            Dataset(id=1, id_ckan=ID_CONV, name="convenios-recebidos-agehab",
                    titulo="Convênios Recebidos - AGEHAB", organizacao_id=HAB,
                    ultima_coleta_id=1,
                    metadata_created=datetime(2025, 10, 1, tzinfo=UTC)),
            Dataset(id=2, id_ckan=ID_TERC, name="relacao-de-terceirizados-agehab",
                    titulo="Relação de Terceirizados - AGEHAB", organizacao_id=HAB,
                    ultima_coleta_id=1),
        ])
        db.commit()


# ---------------------------------------------------------- regras
@pytest.mark.parametrize("valor,esperado", [
    (ID_CONV, (ID_CONV, True)), (f" {ID_CONV.upper()} ", (ID_CONV, True)),
    (None, (None, True)), ("", (None, True)), ("Não encontrado", (None, True)), ("-", (None, True)),
    ("merenda-escolar", (None, False)), ("12345", (None, False)),
])
def test_id_ckan_da_celula(valor, esperado):
    assert regras.id_ckan_da_celula(valor) == esperado


def test_le_o_formato_da_tabela_fato_sem_configuracao():
    """SIGLA vira o órgão e ORGAO o nome do órgão; ID_UNICO, NOME_PDA e PREVISAO_DE_ABERTURA são
    reconhecidos pelos nomes usuais."""
    lida = regras.ler_planilha(CSV.encode("cp1252"), "TABELA_FATO_PDA.CSV")
    assert len(lida.linhas) == 6 and lida.ignoradas == []
    assert lida.tem_coluna_id_ckan and not lida.tem_coluna_portal
    primeira = lida.linhas[0]
    assert (primeira.orgao_sigla, primeira.orgao_nome, primeira.nome_previsto) == (
        "AGEHAB", "Agência Goiana de Habitação", "Convênios Recebidos")
    assert primeira.dataset_id_ckan == ID_CONV and primeira.prazo == date(2025, 11, 1)
    assert [ln.dataset_id_ckan for ln in lida.linhas[3:]] == [None, None, None]
    assert lida.avisos == [(7, "ID do CKAN não reconhecido ('merenda-escolar'): base importada "
                               "sem o ID.")]


def test_colunas_configuradas_tem_prioridade():
    texto = "Linha de título\nUF;Org;Plano;Codigo\nAGEHAB;x;Obras;" + ID_NOVO + "\n"
    cfg = regras.config_leitura({"orgao": "UF", "base": "Plano", "id_ckan": "codigo"}, 2, ";")
    lida = regras.ler_planilha(texto.encode(), "pda.csv", cfg)
    assert [(ln.linha, ln.orgao_sigla, ln.nome_previsto, ln.dataset_id_ckan)
            for ln in lida.linhas] == [(3, "AGEHAB", "Obras", ID_NOVO)]


def test_config_padrao_do_modal_le_a_planilha_da_geda():
    """Configuração SIGLA/ORGAO num arquivo sem "Sigla": "Orgão" continua sendo a sigla."""
    texto = "Orgão;Base de Dados;Atualização\nSEAD;Folha;Mensal\n"
    cfg = regras.config_leitura({"orgao": "SIGLA", "orgao_nome": "ORGAO", "base": "NOME_PDA",
                                 "id_ckan": "ID_UNICO"}, 1, None)
    lida = regras.ler_planilha(texto.encode(), "pda.csv", cfg)
    assert [(ln.orgao_sigla, ln.orgao_nome, ln.nome_previsto) for ln in lida.linhas] == [
        ("SEAD", None, "Folha")]
    assert not lida.tem_coluna_id_ckan


def test_linha_do_cabecalho_configurada_e_obrigatoria():
    cfg = regras.config_leitura({"orgao": "SIGLA", "base": "NOME_PDA"}, 2, None)
    with pytest.raises(regras.PlanilhaInvalida, match='na linha 2.*"SIGLA", "NOME_PDA"'):
        regras.ler_planilha(CSV.encode(), "pda.csv", cfg)


def test_delimitador_configurado():
    texto = CSV.replace(";", "|")
    with pytest.raises(regras.PlanilhaInvalida):
        regras.ler_planilha(texto.encode(), "pda.csv")
    lida = regras.ler_planilha(texto.encode(), "pda.csv", regras.config_leitura(delimitador="|"))
    assert len(lida.linhas) == 6


@pytest.mark.parametrize("colunas,linha,delimitador,mensagem", [
    ({"cpf": "x"}, None, None, "desconhecido"),
    ({}, 0, None, "Início da leitura"),
    ({}, None, "#", "Delimitador"),
])
def test_config_invalida(colunas, linha, delimitador, mensagem):
    with pytest.raises(regras.PlanilhaInvalida, match=mensagem):
        regras.config_leitura(colunas, linha, delimitador)


# ---------------------------------------------------------- importação
def _bases(client, h, plano_id):
    r = client.get(f"{API}/bases", headers=h, params={"plano_id": plano_id})
    assert r.status_code == 200, r.text
    return {b["nome_previsto"]: b for b in r.json()["bases"]}


def test_importacao_vincula_pelo_id_do_ckan(client, gerente, habitacao):
    r = _importar(client, gerente, "PDA tabela fato", CSV)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert (corpo["vinculos_resolvidos"], corpo["vinculos_pendentes"], corpo["sem_vinculo"]) == (
        2, 1, 3)
    assert corpo["tem_coluna_id_ckan"] is True and corpo["tem_coluna_portal"] is False
    assert [a["linha"] for a in corpo["avisos"]] == [7]
    assert corpo["orgaos_sem_correspondencia"] == []
    bases = _bases(client, gerente, corpo["plano"]["id"])
    conv = bases["Convênios Recebidos"]
    assert conv["vinculo"] == "resolvido" and conv["dataset_id"] == 1
    assert conv["dataset_id_ckan"] == ID_CONV and conv["dataset_id_ckan_planilha"] == ID_CONV
    assert conv["orgao_chave"] == str(HAB) and conv["situacao"] == "Sem recurso"
    novo = bases["Concursos Públicos"]
    assert novo["vinculo"] == "pendente" and novo["dataset_id"] is None
    assert novo["dataset_id_ckan_planilha"] == ID_NOVO
    # sem ID: órgão pela evidência das bases da mesma sigla vinculadas por ID
    assert bases["Aluguel Social"]["vinculo"] == "sem_vinculo"
    assert bases["Aluguel Social"]["orgao_chave"] == str(HAB)
    assert bases["Obras"]["orgao_chave"] == str(SEDUC)


def test_atualizar_vinculos_resolve_pelo_id(client, gerente, habitacao):
    plano_id = _importar(client, gerente, "PDA", CSV).json()["plano"]["id"]
    with SessionLocal() as db:
        db.add(Dataset(id=3, id_ckan=ID_NOVO, name="concursos-publicos-e-selecoes-agehab",
                       titulo="Concursos", organizacao_id=HAB, ultima_coleta_id=1))
        db.commit()
    r = client.post(f"{API}/planos/{plano_id}/vincular", headers=gerente)
    assert r.json() == {"vinculos_resolvidos": 1, "vinculos_pendentes": 0}
    assert _bases(client, gerente, plano_id)["Concursos Públicos"]["dataset_id"] == 3


def test_importacao_com_config_do_modal(client, gerente, habitacao):
    texto = "Exportado em 23/10/2026\n" + CSV.replace(";", "|")
    config = {"colunas": {"orgao": "SIGLA", "orgao_nome": "ORGAO", "base": "NOME_PDA",
                          "id_ckan": "ID_UNICO", "periodicidade": "PERIODICIDADE",
                          "prazo": "PREVISAO_DE_ABERTURA", "descricao": ""},
              "linha_cabecalho": 2, "delimitador": "|"}
    r = _importar(client, gerente, "PDA config", texto, config=json.dumps(config))
    assert r.status_code == 201, r.text
    assert r.json()["bases_importadas"] == 6 and r.json()["vinculos_resolvidos"] == 2


def test_importacao_com_config_invalida(client, gerente):
    r = _importar(client, gerente, "PDA", CSV, config=json.dumps({"delimitador": "#"}))
    assert r.status_code == 422 and "Delimitador" in r.json()["detail"]
    r = _importar(client, gerente, "PDA", CSV, config="{nao e json")
    assert r.status_code == 422


def test_edicao_mantem_id_pendente(client, gerente, habitacao):
    plano_id = _importar(client, gerente, "PDA", CSV).json()["plano"]["id"]
    base = _bases(client, gerente, plano_id)["Concursos Públicos"]
    dados = {"orgao_sigla": "AGEHAB", "nome_previsto": "Concursos Públicos e Seleções",
             "dataset_id_ckan": ID_NOVO}
    r = client.put(f"{API}/bases/{base['id']}", headers=gerente, json=dados)
    assert r.status_code == 200, r.text
    assert r.json()["vinculo"] == "pendente" and r.json()["dataset_id_ckan_planilha"] == ID_NOVO
    # outro ID inexistente continua recusado
    r = client.put(f"{API}/bases/{base['id']}", headers=gerente,
                   json={**dados, "dataset_id_ckan": "00000000-0000-4000-8000-000000000000"})
    assert r.status_code == 422
