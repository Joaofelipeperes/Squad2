"""Situação de atualização pela periodicidade do campo "Atualização" do CKAN (PBI-27/28, ADR-0037)."""
from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.atualizacoes import regras, service

HOJE = date(2026, 10, 28)


def _ha(dias: int) -> datetime:
    """Última atualização há `dias` dias."""
    return datetime.combine(HOJE - timedelta(days=dias), datetime.min.time(), tzinfo=UTC)


@pytest.mark.parametrize("dias,esperado", [
    (0, "Atualizado"), (23, "Atualizado"),
    (24, "Próximo do vencimento"), (30, "Próximo do vencimento"),  # Mensal = 30 dias, sem tolerância
    (31, "Atrasado"), (400, "Atrasado"),
])
def test_mensal(dias, esperado):
    assert regras.situacao_periodicidade("Mensal", _ha(dias), HOJE) == esperado


@pytest.mark.parametrize("periodicidade,dias,esperado", [
    ("Anual", 291, "Atualizado"), ("Anual", 292, "Próximo do vencimento"),  # 80% de 365
    ("Anual", 365, "Próximo do vencimento"), ("Anual", 366, "Atrasado"),
    ("Semestral", 181, "Atrasado"), ("Diária", 1, "Próximo do vencimento"),
    ("Diária", 2, "Atrasado"), ("Quinquenal", 1000, "Atualizado"),
    ("Quadrienal", 1461, "Atrasado"), ("Bienal", 500, "Atualizado"),
])
def test_demais_periodicidades(periodicidade, dias, esperado):
    assert regras.situacao_periodicidade(periodicidade, _ha(dias), HOJE) == esperado


@pytest.mark.parametrize("texto,esperado", [
    # valores reais do portal, com espaços e tabulação sobrando
    ("Mensal", "Mensal"), ("Mensal ", "Mensal"), (" Anual ", "Anual"), ("semestral", "Semestral"),
    ("Quadrienal ", "Quadrienal"), ("DIÁRIA", "Diária"),
    ("Não possui atualização periódica", "Sem atualização periódica"),
    (" \tNão possui atualização periódica ", "Sem atualização periódica"),
    ("nao possui atualizacao periodica", "Sem atualização periódica"),
    # vazio, ausente ou inválido: "Periodicidade não informada" — nunca chuta
    (None, "Periodicidade não informada"), ("", "Periodicidade não informada"),
    ("   ", "Periodicidade não informada"), ("Mensal/Anual", "Periodicidade não informada"),
    ("Eventual", "Periodicidade não informada"), ("Quando houver", "Periodicidade não informada"),
    ("Sem informação", "Periodicidade não informada"), (12, "Periodicidade não informada"),
])
def test_periodicidade_ckan(texto, esperado):
    assert regras.periodicidade_ckan(texto) == esperado


def test_sem_atualizacao_periodica_e_valida_e_sem_prazo():
    # declaração do órgão: vale com ou sem data e nunca vira atraso
    for ultima in (_ha(5000), _ha(1), None):
        assert regras.situacao_periodicidade("Não possui atualização periódica", ultima, HOJE) == (
            "Sem atualização periódica")
    assert regras.prazo_em_dias("Sem atualização periódica") is None
    assert regras.vencimento_atualizacao("Não possui atualização periódica", _ha(5)) is None


def test_periodicidade_nao_informada_nao_se_confunde_com_sem_atualizacao_periodica():
    for texto in (None, "", "qualquer coisa"):
        assert regras.situacao_periodicidade(texto, _ha(5), HOJE) == "Periodicidade não informada"
        assert regras.situacao_periodicidade(texto, None, HOJE) == "Periodicidade não informada"
    assert regras.PERIODICIDADE_NAO_INFORMADA != regras.SEM_ATUALIZACAO_PERIODICA
    # nenhuma das duas entra no cálculo do prazo
    assert not {regras.PERIODICIDADE_NAO_INFORMADA, regras.SEM_ATUALIZACAO_PERIODICA} & set(
        regras.COM_PRAZO)


def test_sem_data_de_atualizacao():
    assert regras.situacao_periodicidade("Mensal", None, HOJE) == "Sem data de atualização"


def test_idempotente_sobre_valor_normalizado():
    for valor in regras.PERIODICIDADES:
        assert regras.periodicidade_ckan(valor) == valor


def test_vencimento():
    assert regras.vencimento_atualizacao("Mensal", _ha(40)) == HOJE - timedelta(days=10)
    assert regras.vencimento_atualizacao(" Mensal ", _ha(40)) == HOJE - timedelta(days=10)
    assert regras.vencimento_atualizacao("Mensal", None) is None
    assert regras.vencimento_atualizacao(None, _ha(40)) is None


def test_contrato_do_service():
    assert service.situacao_periodicidade("Mensal", _ha(31), HOJE) == "Atrasado"
