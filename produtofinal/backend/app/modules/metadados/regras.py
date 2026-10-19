"""Regras puras do módulo metadados (sem banco, sem FastAPI) — reutilizáveis numa extensão CKAN."""
from collections.abc import Iterable


def normalizar_formato(formato: str | None) -> str:
    """Formato do recurso como chave de comparação: sem espaços nem ponto inicial, maiúsculo
    ('.csv ' → 'CSV'). Vazio → ''."""
    return (formato or "").strip().lstrip(".").upper()


def eh_formato_aberto(formato: str | None, formatos_abertos: Iterable[str]) -> bool:
    """PBI-52/53 — o formato está na lista de formatos abertos (parâmetro `formatos_abertos`,
    editável pela GEDA). Recurso sem formato informado conta como NÃO aberto: não dá para
    afirmar que está em formato aberto."""
    alvo = normalizar_formato(formato)
    return bool(alvo) and alvo in {normalizar_formato(f) for f in formatos_abertos}
