"""Regras puras (sem banco, sem FastAPI) — reutilizáveis caso a entrega vire extensão CKAN."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone

# Heurística provisória até a GEDA confirmar o critério (PBI-11). Aplicada ao texto normalizado
# (sem acento, minúsculo, "_", "-" e "." viram espaço): cobre os nomes das exportações automáticas
# do portal, como "DICIONÁRIO_DE_DADOS_X.pdf" e "dicionario-de-dados-x.pdf".
_DICIONARIO = re.compile(r"\bdicionario( de)? dados\b")


def parse_ckan_datetime(value: str | None) -> datetime | None:
    """CKAN 2.9 devolve ISO sem fuso (UTC implícito): '2026-09-17T14:03:11.123456'."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _normalizar_texto(texto: str) -> str:
    """Sem acento, minúsculo, separadores "_", "-" e "." trocados por espaço, espaços colapsados."""
    t = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    t = re.sub(r"[_\-.]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def eh_dicionario_de_dados(nome: str | None, descricao: str | None = None) -> bool:
    """PBI-11 — recurso é dicionário de dados. Dicionário nunca entra na contagem de recursos.

    Critérios (texto normalizado): "dicionário de dados" / "dicionário dados" no nome ou na
    descrição; ou NOME que começa com "dicionário" ("DICIONARIO CONVENIOS CONCEDIDOS DGPP",
    "Dicionário Licitações GOIÁSTELECOM" — padrão observado no portal em 08/10/2026, a confirmar
    com a GEDA)."""
    if _DICIONARIO.search(_normalizar_texto(f"{nome or ''} {descricao or ''}")):
        return True
    return _normalizar_texto(nome or "").startswith(("dicionario ", "dicionarios "))


def recurso_atual(recurso: object, dataset: object) -> bool:
    """Recurso ainda presente no pacote do dataset: veio na mesma coleta que atualizou o dataset.

    A coleta grava `ultima_coleta_id` no dataset e em cada recurso do pacote; recurso apagado do
    CKAN continua no banco (o histórico de achados LGPD e de correções aponta para ele), mas fica
    com uma coleta anterior à do dataset e não deve contar como publicado.
    """
    return getattr(recurso, "ultima_coleta_id", None) == getattr(dataset, "ultima_coleta_id", None)


def extras_como_dict(extras: list[dict] | None) -> dict:
    return {e.get("key"): e.get("value") for e in (extras or []) if e.get("key")}


# Chaves de extras que guardam a periodicidade declarada, em ordem de preferência.
# No portal de Goiás o extra usado é "Atualização" (ex.: "Mensal", "Anual").
_CHAVES_PERIODICIDADE = ("periodicidade", "atualizacao", "frequencia de atualizacao")


def periodicidade_declarada(extras: dict, pkg: dict | None = None) -> str | None:
    """Periodicidade informada pelo órgão, procurada nos extras sem diferenciar acento,
    maiúsculas ou espaços (o portal usa "Atualização"). Cai no campo `periodicidade` do pacote."""
    normalizados = {_normalizar_texto(k): v for k, v in (extras or {}).items() if k}
    for chave in _CHAVES_PERIODICIDADE:
        valor = normalizados.get(chave)
        if isinstance(valor, str) and valor.strip():
            return " ".join(valor.split())
    valor = (pkg or {}).get("periodicidade")
    return " ".join(valor.split()) if isinstance(valor, str) and valor.strip() else None


def snapshot_payload(pkg: dict) -> dict:
    """Recorte estável do dataset usado para detectar mudanças entre coletas."""
    return {
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "private": pkg.get("private", False),
        "state": pkg.get("state"),
        "organization": (pkg.get("organization") or {}).get("id"),
        "resources": sorted(
            ({"id": r.get("id"), "format": r.get("format"), "last_modified": r.get("last_modified"),
              "url": r.get("url")} for r in pkg.get("resources", [])),
            key=lambda r: r["id"] or "",
        ),
    }


def hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


# ------------------------------------------------------------------ tela Datasets (PBI-83)
PUBLICADO = "Publicado"
SEM_RECURSO = "Sem recurso"
FORA_DO_PORTAL = "Fora do portal"
SITUACOES_NO_PORTAL: tuple[str, ...] = (PUBLICADO, SEM_RECURSO, FORA_DO_PORTAL)


def situacao_no_portal(ativo_no_portal: bool, recursos_validos: int) -> str:
    """Situação do dataset vista só pelo inventário (não é a situação do PDA, que depende do
    vínculo com a base prevista): fora do `package_search` (excluído ou privado) → "Fora do
    portal"; ativo sem recurso válido (só dicionário de dados ou nenhum) → "Sem recurso"; ativo
    com recurso válido → "Publicado"."""
    if not ativo_no_portal:
        return FORA_DO_PORTAL
    return PUBLICADO if recursos_validos > 0 else SEM_RECURSO


def contem_texto(busca: str | None, *campos: str | None) -> bool:
    """Busca sem diferenciar acento, maiúsculas e separadores ("_", "-", "."): 'saude' acha
    'Saúde' e 'indicadores-saude'. Busca vazia → True."""
    alvo = _normalizar_texto(busca or "")
    return not alvo or any(alvo in _normalizar_texto(c or "") for c in campos)


def chave_texto(texto: str | None) -> str:
    """Chave de ordenação e comparação: sem acento, minúscula, separadores viram espaço."""
    return _normalizar_texto(texto or "")
