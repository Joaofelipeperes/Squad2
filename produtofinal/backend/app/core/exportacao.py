"""Cuidados comuns aos arquivos que a solução gera para abrir em planilha (ADR-0036)."""
import re

_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")
_NUMERO = re.compile(r"[+-]?\d+([.,]\d+)*%?")


def sem_formula(valor: str) -> str:
    """Texto que o Excel leria como fórmula ao abrir um CSV (começa com = + - @) ganha um
    apóstrofo na frente e passa a ser lido como texto. Números ("-12,5") ficam como estão.
    Os textos vêm do CKAN, escritos pelos órgãos: não são confiáveis."""
    if valor.startswith(_INICIO_DE_FORMULA) and not _NUMERO.fullmatch(valor.strip()):
        return "'" + valor
    return valor
