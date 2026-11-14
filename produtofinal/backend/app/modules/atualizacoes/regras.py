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


# ------------------------------------------------------------------ periodicidade declarada no CKAN
# ADR-0037 (critérios da GEDA de 13/11/2026, substitui a ADR-0023): a periodicidade de atualização
# vem SÓ do campo customizado "Atualização" do dataset no CKAN, para todas as bases publicadas no
# portal — previstas no PDA ou espontâneas. A periodicidade da planilha do PDA não entra aqui.
SEM_ATUALIZACAO_PERIODICA = "Sem atualização periódica"  # declaração válida do órgão
PERIODICIDADE_NAO_INFORMADA = "Periodicidade não informada"  # campo vazio ou inválido: não conforme

# Prazo, em dias, de cada periodicidade aceita no campo "Atualização"
DIAS_POR_PERIODICIDADE: dict[str, int] = {
    "Diária": 1, "Semanal": 7, "Quinzenal": 15, "Mensal": 30, "Bimestral": 60, "Trimestral": 90,
    "Quadrimestral": 120, "Semestral": 180, "Anual": 365, "Bienal": 730, "Quadrienal": 1460,
    "Quinquenal": 1825,
}
# Valor que o órgão escolhe no portal quando a base não tem periodicidade fixa
VALOR_CKAN_SEM_PERIODICIDADE = "Não possui atualização periódica"
# Domínio do indicador, na ordem dos filtros
PERIODICIDADES: tuple[str, ...] = (*DIAS_POR_PERIODICIDADE, SEM_ATUALIZACAO_PERIODICA,
                                   PERIODICIDADE_NAO_INFORMADA)


def _chave(texto: str) -> str:
    """Só letras, sem acento, minúsculas: ' Mensal.' → 'mensal'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


# O próprio rótulo do domínio também é aceito, para a normalização ser idempotente
_VALORES_CKAN = ({_chave(p): p for p in DIAS_POR_PERIODICIDADE}
                 | {_chave(VALOR_CKAN_SEM_PERIODICIDADE): SEM_ATUALIZACAO_PERIODICA,
                    _chave(SEM_ATUALIZACAO_PERIODICA): SEM_ATUALIZACAO_PERIODICA})


def periodicidade_ckan(declarada: object) -> str:
    """Campo "Atualização" do CKAN → valor do domínio (`PERIODICIDADES`).

    Aceita os valores do portal sem diferenciar maiúsculas, acentos, espaços e pontuação
    (' Mensal ', 'Não possui atualização periódica\t'). "Não possui atualização periódica" →
    "Sem atualização periódica" (declaração válida). Vazio, ausente ou qualquer outro texto →
    "Periodicidade não informada": nunca chuta e nunca confunde com "sem atualização periódica".
    """
    if not isinstance(declarada, str):
        return PERIODICIDADE_NAO_INFORMADA
    return _VALORES_CKAN.get(_chave(declarada), PERIODICIDADE_NAO_INFORMADA)


# ------------------------------------------------------------------ situação de atualização
# PBI-27/28. Prazo da periodicidade sem tolerância; "Próximo do vencimento" a partir de 80% do prazo.
ATUALIZADO = "Atualizado"
PROXIMO_DO_VENCIMENTO = "Próximo do vencimento"
ATRASADO = "Atrasado"
SEM_DATA = "Sem data de atualização"  # periodicidade válida, mas nenhum recurso válido com data
SITUACOES_ATUALIZACAO: tuple[str, ...] = (ATUALIZADO, PROXIMO_DO_VENCIMENTO, ATRASADO,
                                          SEM_ATUALIZACAO_PERIODICA, PERIODICIDADE_NAO_INFORMADA,
                                          SEM_DATA)
# Situações com prazo avaliado: só elas entram no % de atualização e no índice de atenção
COM_PRAZO: tuple[str, ...] = (ATUALIZADO, PROXIMO_DO_VENCIMENTO, ATRASADO)
FRACAO_ALERTA = 0.8


def prazo_em_dias(periodicidade: str | None) -> int | None:
    """Dias do prazo de atualização; sem prazo fixo ou periodicidade não informada → None."""
    return DIAS_POR_PERIODICIDADE.get(periodicidade_ckan(periodicidade))


def vencimento_atualizacao(periodicidade: str | None, ultima: datetime | None) -> date | None:
    """Data até a qual a próxima atualização é esperada (última atualização + prazo)."""
    dias = prazo_em_dias(periodicidade)
    if dias is None or ultima is None:
        return None
    return ultima.date() + timedelta(days=dias)


def situacao_periodicidade(periodicidade: str | None, ultima: datetime | None,
                           hoje: date) -> str:
    """PBI-27/28 — situação de atualização de um dataset publicado (ADR-0037).

    `periodicidade` = campo "Atualização" do CKAN (cru ou já passado por `periodicidade_ckan`).
    Ordem: "Sem atualização periódica" (declaração válida, sem prazo); "Periodicidade não
    informada" (vazio ou inválido, não conforme — vale mesmo com data de atualização); "Sem data
    de atualização" (periodicidade válida, nenhum recurso válido com data). Senão, com `d` = dias
    desde a última atualização real: `d > prazo` → "Atrasado"; `d >= 80% do prazo` → "Próximo do
    vencimento"; senão "Atualizado". Ex.: Mensal (30 dias) → atualizado até 23 dias, próximo de
    24 a 30, atrasado a partir de 31.
    """
    valor = periodicidade_ckan(periodicidade)
    if valor in (SEM_ATUALIZACAO_PERIODICA, PERIODICIDADE_NAO_INFORMADA):
        return valor
    dias = DIAS_POR_PERIODICIDADE[valor]
    if ultima is None:
        return SEM_DATA
    decorridos = (hoje - ultima.date()).days
    if decorridos > dias:
        return ATRASADO
    if decorridos >= FRACAO_ALERTA * dias:
        return PROXIMO_DO_VENCIMENTO
    return ATUALIZADO
