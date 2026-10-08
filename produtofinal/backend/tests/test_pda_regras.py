"""Regras puras do módulo pda (sem banco). Dados fictícios."""
from datetime import date, timedelta

import pytest

from app.modules.pda import regras
from app.modules.pda.regras import (
    casar_orgao,
    extrair_name_da_url,
    flag_prazo,
    normalizar_periodicidade,
    situacao_base,
)


# ---------------------------------------------------------- periodicidade
@pytest.mark.parametrize("texto,esperado", [
    ("Mensal", "Mensal"), ("Anual", "Anual"), ("Mnsal", "Mensal"), ("Semstral", "Semestral"),
    ("Semestral", "Semestral"), ("Sob Demanda", "Eventual"), ("Quando houver", "Eventual"),
    ("Eventual", "Eventual"), ("Não há mais atualização", "Estática"), ("Estática", "Estática"),
    ("Mensal/Trimestral/Semestral", "Múltipla"), ("N/A", "Sem informação"),
    ("", "Sem informação"), (None, "Sem informação"), ("   ", "Sem informação"),
    ("Bianual", "Bienal"), ("Quadrienal", "Quadrienal"), ("Quinquenal", "Quinquenal"),
    ("Quinzenal", "Quinzenal"), ("Bimestral", "Bimestral"), ("Quadrimestral", "Quadrimestral"),
    ("Trimestral", "Trimestral"), ("Diário", "Diária"), ("diaria", "Diária"),
    ("Semanal", "Semanal"), ("  MENSAL  ", "Mensal"), ("Mensal.", "Mensal"),
    ("Conforme a lua", "Sem informação"),  # desconhecido: não chuta
])
def test_normalizar_periodicidade(texto, esperado):
    assert normalizar_periodicidade(texto) == esperado


def test_dominio_da_periodicidade():
    valores = ["Mensal", "Mnsal", "Bianual", "N/A", "Mensal/Anual", "xyz", "Estática"]
    assert {normalizar_periodicidade(v) for v in valores} <= set(regras.DOMINIO_PERIODICIDADE)


# ---------------------------------------------------------- name a partir da URL
@pytest.mark.parametrize("valor,esperado", [
    ("https://dadosabertos.go.gov.br/dataset/escolas-estaduais", "escolas-estaduais"),
    ("https://dadosabertos.go.gov.br/dataset/escolas-estaduais/", "escolas-estaduais"),
    ("https://dadosabertos.go.gov.br/dataset/escolas-estaduais?aba=1#r", "escolas-estaduais"),
    ("  https://DADOSABERTOS.GO.GOV.BR/dataset/escolas_2025  ", "escolas_2025"),
    ("https://dadosabertos.go.gov.br/dataset/escolas/resource/abc-123", "escolas"),
    ("dadosabertos.go.gov.br/dataset/sem-esquema", "sem-esquema"),
    ("Não", None), ("Nao", None), ("", None), (None, None), (123, None),
    ("https://dadosabertos.go.gov.br/organization/seduc", None),
    ("https://dadosabertos.go.gov.br/dataset/", None),
])
def test_extrair_name_da_url(valor, esperado):
    assert extrair_name_da_url(valor) == esperado


# ---------------------------------------------------------- casamento do órgão
ORGAOS = [
    ("o-abc", "agencia-brasil-central", "Agência Brasil Central - ABC", None),
    ("o-agehab", "agencia-goiana-de-habitacao", "Agência Goiana de Habitação", None),
    ("o-dgpp", "diretoria-geral-de-policia-penal-dgpp", "Diretoria-Geral de Polícia Penal (DGPP)",
     None),
    ("o-cge", "controladoria-geral-do-estado", "Controladoria-Geral do Estado", None),
    ("o-detran", "departamento-estadual-de-transito-de-goias",
     "Departamento Estadual de Trânsito de Goiás", None),
    ("o-fomento", "goiasfomento", "GoiásFomento", None),
    ("o-fapeg", "fapeg", "Fundação de Amparo à Pesquisa", None),
    ("o-juceg", "juceg-junta-comercial", "Junta Comercial", None),
    ("o-telecom", "goias-telecom", "Goiás Telecom", None),
    ("o-sead", "secretaria-administracao", "Secretaria da Administração", "SEAD"),
]


@pytest.mark.parametrize("sigla,esperado", [
    ("ABC", "o-abc"),
    ("AGEHAB", None),             # nenhum critério casa: não chuta
    ("DGPP", "o-dgpp"),
    ("CGE", "o-cge"),             # iniciais de Controladoria-Geral do Estado
    ("GOIÁSFOMENTO", "o-fomento"),
    ("GOIÁS TELECOM", "o-telecom"),
    ("FAPEG", "o-fapeg"),
    ("JUCEG", "o-juceg"),
    ("sead", "o-sead"),           # sigla cadastrada na organização
    ("DETRAN", None),
    ("", None), (None, None),
])
def test_casar_orgao(sigla, esperado):
    assert casar_orgao(sigla, ORGAOS) == esperado


def test_casar_orgao_empate_nao_chuta():
    orgaos = [("o1", "abc-norte", "ABC Norte", None), ("o2", "abc-sul", "ABC Sul", None)]
    assert casar_orgao("ABC", orgaos) is None


def test_casar_orgao_criterio_mais_forte_decide():
    # sigla cadastrada (critério 1) vence o token no nome de outra organização (critério 3)
    orgaos = [("o1", "secretaria-x", "Secretaria X", "SX"), ("o2", "sx-outra", "SX Outra", None)]
    assert casar_orgao("SX", orgaos) == "o1"


# ---------------------------------------------------------- situação e flag de prazo
HOJE = date(2026, 10, 7)
JANELA = 30


def _sit(vinculada=False, ativo=None, recursos=0, prazo=None):
    return situacao_base(vinculada=vinculada, dataset_ativo=ativo, recursos_validos=recursos,
                         prazo=prazo, hoje=HOJE, janela_dias=JANELA)


def test_situacoes():
    assert _sit(True, True, 2, HOJE - timedelta(days=100)) == "Publicado"
    assert _sit(True, True, 0, HOJE - timedelta(days=100)) == "Sem recurso"
    assert _sit(prazo=HOJE - timedelta(days=1)) == "Em atraso"
    assert _sit(prazo=HOJE + timedelta(days=10)) == "Próximo do prazo"
    assert _sit(prazo=HOJE + timedelta(days=90)) == "Em dia"
    assert _sit(prazo=None) == "Não publicado"


def test_dataset_inativo_conta_como_nao_publicado():
    assert _sit(True, False, 3, HOJE - timedelta(days=1)) == "Em atraso"
    assert _sit(True, False, 3, None) == "Não publicado"


def test_so_dicionario_de_dados_e_sem_recurso():
    # recursos_validos já exclui o dicionário: dataset só com dicionário → 0 válidos
    assert _sit(True, True, 0, None) == "Sem recurso"


def test_limites_da_janela():
    assert _sit(prazo=HOJE) == "Próximo do prazo"
    assert _sit(prazo=HOJE + timedelta(days=JANELA)) == "Próximo do prazo"
    assert _sit(prazo=HOJE + timedelta(days=JANELA + 1)) == "Em dia"


def test_flag_prazo():
    assert flag_prazo(None, HOJE, JANELA) == ""
    assert flag_prazo(HOJE - timedelta(days=1), HOJE, JANELA) == "vencido"
    assert flag_prazo(HOJE, HOJE, JANELA) == "proximo"
    assert flag_prazo(HOJE + timedelta(days=JANELA), HOJE, JANELA) == "proximo"
    assert flag_prazo(HOJE + timedelta(days=JANELA + 1), HOJE, JANELA) == ""


# ---------------------------------------------------------- leitura da planilha
def test_interpretar_data():
    assert regras.interpretar_data("31/12/2026") == date(2026, 12, 31)
    assert regras.interpretar_data("2026-12-31") == date(2026, 12, 31)
    assert regras.interpretar_data(date(2026, 1, 2)) == date(2026, 1, 2)
    assert regras.interpretar_data("") is None and regras.interpretar_data(None) is None
    with pytest.raises(ValueError):
        regras.interpretar_data("dez/2026")
    with pytest.raises(ValueError):
        regras.interpretar_data(2026)  # ano solto não é data


def test_cabecalho_normalizado_e_linha_da_planilha():
    csv = ("Relatório PDA\n"
           "ORGÃO ;Base  de Dados;Possui Conteúdo Sigiloso?\n"
           "SEAD;Servidores;Sim\n"
           ";Sem órgão;Não\n"
           "Total;;\n").encode()
    lida = regras.ler_planilha(csv, "pda.csv")
    assert [(ln.linha, ln.orgao_sigla, ln.possui_conteudo_sigiloso) for ln in lida.linhas] == [
        (3, "SEAD", True)]
    assert lida.ignoradas == [(4, "Sem Órgão.")]
    assert lida.tem_coluna_prazo is False


def test_cabecalho_obrigatorio_ausente():
    with pytest.raises(regras.PlanilhaInvalida, match="Base de Dados"):
        regras.ler_planilha("Orgão;Descrição\nSEAD;x\n".encode(), "pda.csv")


def test_csv_latin1_e_virgula():
    conteudo = "Orgão,Base de Dados,Atualização\nSEAD,Folha,Mnsal\n".encode("latin-1")
    lida = regras.ler_planilha(conteudo, "pda.csv")
    assert lida.linhas[0].orgao_sigla == "SEAD"
    assert lida.linhas[0].periodicidade_original == "Mnsal"
