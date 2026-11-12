"""Regras puras do Assistente (sem banco, sem FastAPI): entender a pergunta.

O Assistente não tem banco vetorial (ADR-0011). Para achar "do que" a pergunta fala, o backend
compara palavras: órgão citado (título, name ou sigla), dataset citado (título, name ou nome de
um recurso/arquivo) e a intenção (atraso, prazo, LGPD...). As mesmas ideias do chatbot do
Protótipo V1 (`findOrgMention`, `findDatasetMention`, `chatbotAnswer`), agora sobre os dados reais.
"""
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

# Palavras sem valor para identificar um dataset (artigos, preposições e termos genéricos do chat)
_VAZIAS = """
a o as os um uma uns umas de da do das dos e em no na nos nas por pela pelo para pra com sem
ao aos qual quais quanto quantos quantas que quem quando onde como sobre tem ha existe existem
me mostre mostra diga liste listar ver veja esta estao esse essa este isso isto ele ela dele dela
base bases dado dados dataset datasets recurso recursos arquivo arquivos portal goias estado
secretaria orgao orgaos sao foi ser seu sua seus suas mais menos ultimo ultima ultimos ultimas
"""
PALAVRAS_VAZIAS = frozenset(_VAZIAS.split())

# Intenções reconhecidas na pergunta → regex sobre o texto normalizado
INTENCOES: dict[str, re.Pattern[str]] = {
    "atraso": re.compile(r"\batras|\bvencid|\bpendent|\bdescumpr"),
    "prazo": re.compile(r"\bprazo|\bvence\b|\bvencer|\bproxim[oa]s? (do )?prazo"),
    "lgpd": re.compile(r"\blgpd\b|dados? pessoa|\bcpf\b|\bsensive|\bprivacidade|\balerta"),
    "atualizacao": re.compile(r"atualiz|desatualiz|\bmodificad|last.?modified"),
    "sem_recurso": re.compile(r"sem recurso|sem arquivo|vazi[oa]s?\b"),
    "nao_publicado": re.compile(r"nao (foi |foram )?publicad|ainda nao (esta|estao) no portal"),
    "contagem": re.compile(r"\bquant[oa]s?\b|\btotal\b|\bnumero de\b"),
    "pda": re.compile(r"\bpda\b|plano de dados"),
}


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento; separadores (_ - . /) viram espaço; espaços colapsados."""
    sem = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    sem = re.sub(r"[_\-./\\:;,()\[\]\"'!?]+", " ", sem.lower())
    return re.sub(r"\s+", " ", sem).strip()


def termos(texto: str | None) -> list[str]:
    """Palavras relevantes (≥3 letras, fora da lista de palavras vazias), na ordem, sem repetir."""
    vistos: dict[str, None] = {}
    for p in normalizar(texto).split():
        if len(p) >= 3 and p not in PALAVRAS_VAZIAS and not p.isdigit():
            vistos.setdefault(p, None)
    return list(vistos)


def _radical(palavra: str) -> str:
    """Radical grosseiro para casar singular/plural e gênero ("matriculas" ~ "matricula")."""
    return palavra[:-1] if len(palavra) > 4 and palavra[-1] in "sa" else palavra


def intencoes(pergunta: str) -> set[str]:
    p = normalizar(pergunta)
    return {nome for nome, rx in INTENCOES.items() if rx.search(p)}


def contem_frase(texto_norm: str, frase: str | None, minimo: int = 3) -> bool:
    """`frase` aparece inteira no texto (com limite de palavra). Frases curtas demais não contam."""
    f = normalizar(frase)
    return len(f) >= minimo and re.search(rf"(^| ){re.escape(f)}($| )", texto_norm) is not None


def sigla_citada(texto_norm: str, sigla: str | None) -> bool:
    """Sigla do órgão citada como palavra ("SES", "seduc"); "SES-GO" casa com "ses"."""
    if not sigla:
        return False
    base = normalizar(sigla).replace(" go", "").strip()
    return len(base) >= 2 and re.search(rf"(^| ){re.escape(base)}( go)?($| )", texto_norm) is not None


@dataclass(frozen=True)
class Candidato:
    """Texto indexável de um dataset: título, name, descrição e nomes dos recursos."""

    chave: str
    titulo: str
    name: str
    descricao: str | None = None
    nomes_recursos: tuple[str, ...] = ()


def pontuar(pergunta: str, c: Candidato) -> float:
    """Quão bem a pergunta aponta para o dataset.

    - Título, name ou nome de arquivo citado por inteiro → 10 (correspondência forte).
    - Senão, soma por palavra da pergunta encontrada: título/name 2, arquivo 1,5, descrição 0,5;
      dividido pela raiz do nº de palavras do título (títulos longos não ganham por volume).
    """
    p = normalizar(pergunta)
    if contem_frase(p, c.titulo, 6) or contem_frase(p, c.name, 6) or any(
            contem_frase(p, n, 6) for n in c.nomes_recursos):
        return 10.0
    q = {_radical(t) for t in termos(pergunta)}
    if not q:
        return 0.0
    tit = {_radical(t) for t in termos(f"{c.titulo} {c.name}")}
    arq = {_radical(t) for n in c.nomes_recursos for t in termos(n)}
    desc = {_radical(t) for t in termos((c.descricao or "")[:600])}
    soma = sum(2.0 if t in tit else 1.5 if t in arq else 0.5 if t in desc else 0.0 for t in q)
    return soma / max(1.0, len(tit) ** 0.5)


def melhores(pergunta: str, candidatos: Iterable[Candidato], limite: int = 5,
             minimo: float = 0.9) -> list[tuple[Candidato, float]]:
    """Os `limite` candidatos com maior pontuação (≥ `minimo`). Havendo correspondência forte,
    só as fortes voltam: quem citou o nome exato de uma base quer aquela base."""
    pontuados = sorted(((c, pontuar(pergunta, c)) for c in candidatos),
                       key=lambda x: (-x[1], normalizar(x[0].titulo)))
    pontuados = [(c, s) for c, s in pontuados if s >= minimo]
    fortes = [(c, s) for c, s in pontuados if s >= 10.0]
    return (fortes or pontuados)[:limite]


def cortar(texto: str | None, limite: int) -> str:
    """Texto numa linha só, cortado em `limite` caracteres (com reticências)."""
    t = re.sub(r"\s+", " ", texto or "").strip()
    return t if len(t) <= limite else t[: limite - 1].rstrip() + "…"
