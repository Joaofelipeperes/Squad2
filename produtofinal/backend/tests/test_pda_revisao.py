"""Regressões da revisão de 08/10/2026 do módulo pda (e das regras do inventário que ele usa).
Dados fictícios, exceto nomes de organizações e de recursos copiados do portal público."""
import io
import zipfile
from datetime import UTC, date, datetime

import pytest
from openpyxl import Workbook

from app.core.db import SessionLocal
from app.modules.inventario.models import Coleta, Dataset, Organizacao, Recurso
from app.modules.inventario.regras import eh_dicionario_de_dados
from app.modules.pda import regras, service
from app.modules.pda.regras import casar_orgao, normalizar_periodicidade
from tests.conftest import SENHA, login

API = "/api/v1/pda"
URL = "https://dadosabertos.go.gov.br/dataset/"
CAB = "Orgão;Base de Dados;Atualização;Disponível no Portal"

# Organizações reais do portal (coleta de 07/10/2026)
ORGAOS_REAIS = [
    ("o-casacivil", "secretaria-de-estado-da-casa-civil", "Secretaria de Estado da Casa Civil",
     None),
    ("o-casamilitar", "secretaria-de-estado-da-casa-militar",
     "Secretaria de Estado da Casa Militar", None),
    ("o-parcerias", "companhia-de-investimentos-e-parcerias-do-estado-de-goias-goias-parcerias",
     "Companhia de Investimentos e Parcerias do Estado de Goiás  – Goiás Parcerias", None),
    ("o-habitacao", "agencia-goiana-de-habitacao", "Agência Goiana de Habitação", None),
    ("o-cultura", "secretaria-de-estado-da-cultura", "Secretaria de Estado da Cultura", None),
    ("o-saneago", "saneamento-de-goias-s-a", "Saneamento de Goiás S.A.", None),
    ("o-agr", "agencia-goiana-de-regulacao-controle-e-fiscalizacao-de-servicos-publicos",
     "Agência Goiana de Regulação, Controle e Fiscalização de Serviços Públicos ", None),
    ("o-turismo", "goias-turismo", "Goiás Turismo", None),
]


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(service, "hoje_local", lambda: date(2026, 10, 8))


def _importar(client, h, nome, texto, arquivo="pda.csv", **campos):
    conteudo = texto if isinstance(texto, bytes) else ("﻿" + texto).encode("utf-8")
    return client.post(f"{API}/planos", headers=h, data={"nome": nome, **campos},
                       files={"arquivo": (arquivo, conteudo, "application/octet-stream")})


# ---------------------------------------------------------- casamento de órgão
@pytest.mark.parametrize("sigla,esperado", [
    ("CASA CIVIL", "o-casacivil"),        # sigla de várias palavras: sequência contígua no name
    ("GOIÁS PARCERIAS", "o-parcerias"),   # sequência contígua no título
    # de-para explícito (SIGLAS_CONHECIDAS), inclusive o erro de digitação da planilha
    ("CASA MLITAR", "o-casamilitar"), ("SECULT", "o-cultura"), ("Saneago", "o-saneago"),
    ("AGEHAB", "o-habitacao"), ("AGR", "o-agr"),
    ("SECRETARIA DE ESTADO", None),       # várias organizações contêm a sequência: não chuta
])
def test_casar_orgao_siglas_de_varias_palavras(sigla, esperado):
    assert casar_orgao(sigla, ORGAOS_REAIS) == esperado


def test_de_para_sem_a_organizacao_no_portal_nao_chuta():
    """Organização do de-para que mudou de name (ou não existe) → segue a heurística, sem chutar."""
    sem_saneago = [o for o in ORGAOS_REAIS if o[0] != "o-saneago"]
    assert casar_orgao("SANEAGO", sem_saneago) is None


def test_orgao_por_evidencia_so_com_organizacao_unica():
    pares = [("SEAD", "o-adm"), ("sead ", "o-adm"), ("SES", "o-saude"), ("SES", "o-outra")]
    assert regras.orgao_por_evidencia(pares) == {"SEAD": "o-adm"}  # SES aponta para duas


# ---------------------------------------------------------- periodicidade
@pytest.mark.parametrize("texto,esperado", [
    (".Semestral", "Semestral"), ("-Mensal", "Mensal"), ("Mensal-", "Mensal"),
    ("Mensal/Quando necessário", "Sem informação"),  # parte desconhecida: não chuta
    ("Mensal/N/A", "Mensal"), ("Mensal/Trimestral", "Múltipla"),
])
def test_periodicidade_bordas_e_barra(texto, esperado):
    assert normalizar_periodicidade(texto) == esperado


# ---------------------------------------------------------- leitura da planilha
def test_rodape_so_na_coluna_orgao_e_cabecalho_repetido():
    texto = ("Base de Dados;Órgão\nTotal de servidores;SEAD\nFolha;SEAD\n"
             "Base de Dados;Órgão\nTotal;\n")
    lida = regras.ler_planilha(texto.encode(), "pda.csv")
    assert [ln.nome_previsto for ln in lida.linhas] == ["Total de servidores", "Folha"]
    assert (4, "Cabeçalho repetido.") in lida.ignoradas


def test_prazo_brasileiro_com_hora():
    assert regras.interpretar_data("31/12/2026 00:00:00") == date(2026, 12, 31)
    assert regras.interpretar_data("31/12/2026 08:30") == date(2026, 12, 31)


def test_colunas_opcionais_ausentes():
    lida = regras.ler_planilha("Órgão;Base de Dados\nABC;B1\n".encode(), "pda.csv")
    assert not lida.tem_coluna_prazo
    assert "Meta/Prazo para abertura" in lida.colunas_opcionais_ausentes


def test_xlsx_descompactado_grande_demais(monkeypatch):
    monkeypatch.setattr(regras, "TAMANHO_DESCOMPACTADO_MAXIMO", 1000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet1.xml", "a" * 5000)  # comprime para poucos bytes
    with pytest.raises(regras.PlanilhaInvalida, match="descompactada"):
        regras.ler_planilha(buf.getvalue(), "pda.xlsx")


def test_xlsx_com_linhas_demais(monkeypatch):
    monkeypatch.setattr(regras, "LINHAS_MAXIMO", 50)
    wb = Workbook()
    ws = wb.active
    ws.append(["Órgão", "Base de Dados"])
    for i in range(80):
        ws.append(["ABC", f"Base {i}"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(regras.PlanilhaInvalida, match="mais de 50 linhas"):
        regras.ler_planilha(buf.getvalue(), "pda.xlsx")


# ---------------------------------------------------------- dicionário de dados (PBI-11)
@pytest.mark.parametrize("nome,esperado", [
    ("DICIONÁRIO_DE_DADOS_PAR_E_PAF.pdf", True),
    ("DICIONARIO_DE_DADOS_DIARIAS", True),
    ("dicionario-de-dados-chamados-ti-jan-2026.pdf", True),
    ("DICIONARIO CONVENIOS CONCEDIDOS DGPP", True),
    ("Dicionário Licitações GOIÁSTELECOM", True),
    ("povos_tradicionais_goias_2023_2024.csv", False),
    ("Relação de dicionários escolares distribuídos", False),
])
def test_dicionario_de_dados_nomes_reais(nome, esperado):
    assert eh_dicionario_de_dados(nome) is esperado


# ---------------------------------------------------------- API
@pytest.fixture
def adm_com_dataset():
    """Organização sem sigla reconhecível pela heurística ("administracao") com um dataset
    publicado: a sigla SEAD só casa pela evidência do vínculo por ID."""
    with SessionLocal() as db:
        db.add(Organizacao(ckan_id="org-adm", name="administracao",
                           titulo="Secretaria da Administração"))
        db.add_all([Coleta(id=1, status="ok"), Coleta(id=2, status="ok")])
        db.add(Dataset(ckan_id="ds-folha", name="folha-de-pagamento", titulo="Folha",
                       organizacao_id="org-adm", ultima_coleta_id=2,
                       metadata_created=datetime(2022, 9, 19, 12, 0, tzinfo=UTC)))
        db.add_all([
            Recurso(ckan_id="r-atual", dataset_id="ds-folha", nome="folha.csv", formato="CSV",
                    ultima_coleta_id=2, last_modified=datetime(2026, 9, 26, tzinfo=UTC)),
            Recurso(ckan_id="r-xlsx", dataset_id="ds-folha", nome="folha.xlsx", formato="XLSX",
                    ultima_coleta_id=2, last_modified=datetime(2026, 9, 20, tzinfo=UTC)),
            Recurso(ckan_id="r-dic", dataset_id="ds-folha", nome="Dicionário de dados",
                    formato="PDF", eh_dicionario_dados=True, ultima_coleta_id=2),
            # apagado do CKAN: não veio na última coleta do dataset → não conta
            Recurso(ckan_id="r-apagado", dataset_id="ds-folha", nome="antigo.csv",
                    formato="ODS", ultima_coleta_id=1,
                    last_modified=datetime(2026, 10, 5, tzinfo=UTC)),
        ])
        db.commit()


def test_sigla_herda_organizacao_do_vinculo_por_id(client, gerente, adm_com_dataset):
    texto = (f"{CAB}\nSEAD;Folha de Pagamento;Mensal;{URL}folha-de-pagamento\n"
             "SEAD;Movimentações;Mensal;Não\n")
    r = _importar(client, gerente, "PDA SEAD", texto)
    assert r.status_code == 201, r.text
    assert "SEAD" not in r.json()["orgaos_sem_correspondencia"]
    corpo = client.get(f"{API}/bases", headers=gerente).json()
    assert {b["orgao_chave"] for b in corpo["bases"]} == {"org-adm"}
    assert len(corpo["opcoes"]["orgaos"]) == 1  # uma opção só para a sigla


def test_recurso_apagado_formatos_e_data_de_publicacao(client, gerente, adm_com_dataset):
    texto = f"{CAB}\nSEAD;Folha de Pagamento;Mensal;{URL}folha-de-pagamento\n"
    _importar(client, gerente, "PDA SEAD", texto)
    base = client.get(f"{API}/bases", headers=gerente).json()["bases"][0]
    assert base["situacao"] == "Publicado"
    assert base["recursos_validos"] == 2          # sem o dicionário e sem o recurso apagado
    assert base["formatos"] == ["CSV", "XLSX"]
    assert base["ultima_atualizacao"].startswith("2026-09-26")  # não a do recurso apagado
    assert base["data_publicacao"].startswith("2022-09-19")


def test_resumo_avisa_coluna_de_prazo_ausente(client, gerente):
    r = _importar(client, gerente, "PDA sem prazo", f"{CAB}\nABC;B1;Anual;Não\n")
    corpo = r.json()
    assert corpo["tem_coluna_prazo"] is False
    assert "Meta/Prazo para abertura" in corpo["colunas_opcionais_ausentes"]


def test_nome_repetido_sem_diferenciar_maiusculas(client, gerente):
    assert _importar(client, gerente, "PDA 2026", f"{CAB}\nABC;B1;Anual;Não\n").status_code == 201
    r = _importar(client, gerente, "pda 2026", f"{CAB}\nABC;B1;Anual;Não\n")
    assert r.status_code == 409


def test_indice_impede_nome_repetido_sem_diferenciar_maiusculas():
    """Mesmo sem a checagem prévia do serviço (corrida), o banco recusa → 409."""
    from sqlalchemy.exc import IntegrityError

    from app.modules.pda.models import PlanoPda

    with SessionLocal() as db:
        db.add(PlanoPda(nome="PDA X", importado_em=datetime.now(UTC)))
        db.commit()
        db.add(PlanoPda(nome="pda x", importado_em=datetime.now(UTC)))
        with pytest.raises(IntegrityError):
            db.commit()


def test_contagens_do_plano_respeitam_escopo_de_orgao(client, admin, gerente):
    texto = f"{CAB}\nSEDUC;Escolas;Mensal;Não\nSEDUC;Matrículas;Mensal;Não\nSES;Leitos;Mensal;Não\n"
    _importar(client, gerente, "PDA escopo", texto)
    papel = client.post("/api/v1/acesso/papeis", headers=admin, json={
        "codigo": "pda_orgao", "nome": "PDA do órgão", "permissoes": ["pda.acessar"]}).json()
    client.post("/api/v1/acesso/usuarios", headers=admin, json={
        "email": "pda@seduc.go.gov.br", "nome": "PDA SEDUC", "senha": SENHA,
        "papel_ids": [papel["id"]], "orgao_id": "org-seduc"})
    h = login(client, "pda@seduc.go.gov.br")
    corpo = client.get(f"{API}/bases", headers=h).json()
    assert corpo["total_previstas"] == 2
    assert corpo["plano"]["total_bases"] == 2  # não o total do PDA inteiro (3)
    assert [p["total_bases"] for p in client.get(f"{API}/planos", headers=h).json()] == [2]
    assert [p["total_bases"] for p in client.get(f"{API}/planos", headers=gerente).json()] == [3]
