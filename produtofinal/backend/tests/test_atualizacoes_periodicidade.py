"""Situação de atualização pela periodicidade do PDA vigente (PBI-27/28, ADR-0023)."""
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
])
def test_demais_periodicidades(periodicidade, dias, esperado):
    assert regras.situacao_periodicidade(periodicidade, _ha(dias), HOJE) == esperado


@pytest.mark.parametrize("periodicidade", ["Eventual", "Estática"])
def test_sem_prazo_fixo(periodicidade):
    assert regras.situacao_periodicidade(periodicidade, _ha(900), HOJE) == (
        "Sem periodicidade definida")
    assert regras.situacao_periodicidade(periodicidade, None, HOJE) == "Sem periodicidade definida"


def test_sem_informacao():
    assert regras.situacao_periodicidade("Sem informação", _ha(5), HOJE) == "Sem informação"
    assert regras.situacao_periodicidade("Mensal", None, HOJE) == "Sem informação"
    assert regras.situacao_periodicidade(None, _ha(5), HOJE) == "Sem informação"


@pytest.mark.parametrize("original,dias", [
    ("Mensal/Trimestral/Semestral", 30), ("Anual e Semestral", 180), ("Trimestral, anual", 90),
    ("Diário ou mensal", 1), ("qualquer coisa", None), (None, None),
])
def test_multipla_usa_a_menor(original, dias):
    assert regras.prazo_em_dias("Múltipla", original) == dias


def test_multipla_na_situacao_e_vencimento():
    assert regras.situacao_periodicidade("Múltipla", _ha(40), HOJE,
                                         "Mensal/Trimestral") == "Atrasado"
    assert regras.situacao_periodicidade("Múltipla", _ha(40), HOJE, "?") == "Sem informação"
    assert regras.vencimento_atualizacao("Mensal", _ha(40)) == HOJE - timedelta(days=10)
    assert regras.vencimento_atualizacao("Eventual", _ha(40)) is None


def test_contrato_do_service():
    assert service.situacao_periodicidade("Mensal", _ha(31), HOJE) == "Atrasado"
