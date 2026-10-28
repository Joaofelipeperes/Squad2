"""Regras puras do módulo atualizacoes (sem banco, sem FastAPI) — reutilizáveis numa extensão CKAN.

Atualização real = `last_modified` do RECURSO. `metadata_modified` do dataset nunca é indicador.
"""
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple


class UltimaAtualizacao(NamedTuple):
    data: datetime | None
    estimada: bool  # True = sem last_modified em nenhum recurso válido; data veio de `created`


def _campo(recurso: object, nome: str) -> object:
    if isinstance(recurso, Mapping):
        return recurso.get(nome)
    return getattr(recurso, nome, None)


def _criado_em(recurso: object) -> object:
    """Data de criação do recurso NO CKAN. Objetos do banco guardam essa data em `created_ckan`
    (o `created` deles é a auditoria da tabela — ADR-0019): quem tem `created_ckan` usa só ele,
    mesmo vazio; payloads do CKAN e dicts usam `created`."""
    if isinstance(recurso, Mapping):
        return recurso["created_ckan"] if "created_ckan" in recurso else recurso.get("created")
    if hasattr(recurso, "created_ckan"):
        return recurso.created_ckan
    return getattr(recurso, "created", None)


def _como_datetime(valor: object) -> datetime | None:
    """Aceita datetime ou ISO 8601 (formato do CKAN). Sem fuso → UTC (CKAN 2.9 grava em UTC)."""
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.strip())
        except ValueError:
            return None
    if not isinstance(valor, datetime):
        return None
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


def ultima_atualizacao_real(recursos: Iterable[object] | None) -> UltimaAtualizacao:
    """PBI-23/24/25 — maior `last_modified` entre os recursos, EXCLUINDO dicionário de dados.

    Se nenhum recurso válido tem `last_modified`, usa a maior data de criação no CKAN e marca
    `estimada=True`. Sem recurso válido → (None, False). Recursos podem ser objetos do banco
    (`created_ckan`) ou payloads/dicts do CKAN (`created`), com `last_modified` e
    `eh_dicionario_dados`.
    """
    validos = [r for r in (recursos or []) if not _campo(r, "eh_dicionario_dados")]
    modificados = [d for r in validos if (d := _como_datetime(_campo(r, "last_modified")))]
    if modificados:
        return UltimaAtualizacao(max(modificados), False)
    criados = [d for r in validos if (d := _como_datetime(_criado_em(r)))]
    if criados:
        return UltimaAtualizacao(max(criados), True)
    return UltimaAtualizacao(None, False)


# ------------------------------------------------------------------ situação por periodicidade
# PBI-27/28 — regra decidida em 28/10/2026 (ADR-0020). A periodicidade que vale é a da base no PDA
# VIGENTE; "Mensal" = 30 dias, sem tolerância.
ATUALIZADO = "Atualizado"
PROXIMO_DO_VENCIMENTO = "Próximo do vencimento"
ATRASADO = "Atrasado"
SEM_INFORMACAO = "Sem informação"
SEM_PERIODICIDADE = "Sem periodicidade definida"
SITUACOES_ATUALIZACAO: tuple[str, ...] = (ATUALIZADO, PROXIMO_DO_VENCIMENTO, ATRASADO,
                                          SEM_INFORMACAO, SEM_PERIODICIDADE)

# Prazo, em dias, de cada periodicidade do domínio do PDA
DIAS_POR_PERIODICIDADE: dict[str, int] = {
    "Diária": 1, "Semanal": 7, "Quinzenal": 15, "Mensal": 30, "Bimestral": 60, "Trimestral": 90,
    "Quadrimestral": 120, "Semestral": 180, "Anual": 365, "Bienal": 730, "Quadrienal": 1460,
    "Quinquenal": 1825,
}
# Sem prazo fixo: muda só quando acontece algo (Eventual) ou não muda mais (Estática)
SEM_PRAZO = frozenset({"Eventual", "Estática"})
MULTIPLA = "Múltipla"
# "Próximo do vencimento" a partir de 80% do prazo (faltando 20% ou menos)
FRACAO_ALERTA = 0.8



def _chave(texto: str) -> str:
    """Só letras, sem acento, minúsculas: ' Mensal.' → 'mensal'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


_CHAVE_PERIODICIDADE = {_chave(p): p for p in DIAS_POR_PERIODICIDADE} | {"diario": "Diária"}


def prazo_em_dias(periodicidade: str | None, original: str | None = None) -> int | None:
    """Dias do prazo de atualização. "Múltipla" (ex.: "Mensal/Trimestral/Semestral") usa a MENOR
    periodicidade citada no texto original, a mais exigente. Sem prazo fixo ou sem informação →
    None."""
    if periodicidade in DIAS_POR_PERIODICIDADE:
        return DIAS_POR_PERIODICIDADE[periodicidade]
    if periodicidade != MULTIPLA:
        return None
    partes = re.split(r"[/,;|+]|\s+e\s+|\s+ou\s+", original or "")
    dias = [DIAS_POR_PERIODICIDADE[p] for parte in partes
            if (p := _CHAVE_PERIODICIDADE.get(_chave(parte)))]
    return min(dias) if dias else None


def vencimento_atualizacao(periodicidade: str | None, ultima: datetime | None,
                           original: str | None = None) -> date | None:
    """Data até a qual a próxima atualização é esperada (última atualização + prazo)."""
    dias = prazo_em_dias(periodicidade, original)
    if dias is None or ultima is None:
        return None
    return ultima.date() + timedelta(days=dias)


def situacao_periodicidade(periodicidade: str | None, ultima: datetime | None, hoje: date,
                           original: str | None = None) -> str:
    """PBI-27/28 — situação da atualização de uma base pela periodicidade do PDA vigente.

    Eventual/Estática → "Sem periodicidade definida". Sem prazo conhecido ou sem data de
    atualização → "Sem informação". Senão, com `d` = dias desde a última atualização real:
    `d > prazo` → "Atrasado"; `d >= 80% do prazo` → "Próximo do vencimento"; senão "Atualizado".
    Ex.: Mensal (30 dias) → atualizado até 23 dias, próximo de 24 a 30, atrasado a partir de 31.
    """
    if periodicidade in SEM_PRAZO:
        return SEM_PERIODICIDADE
    dias = prazo_em_dias(periodicidade, original)
    if dias is None or ultima is None:
        return SEM_INFORMACAO
    decorridos = (hoje - ultima.date()).days
    if decorridos > dias:
        return ATRASADO
    if decorridos >= FRACAO_ALERTA * dias:
        return PROXIMO_DO_VENCIMENTO
    return ATUALIZADO
