"""Regras puras do painel (ADR-0004): índice de atenção por órgão (ADR-0030, PBI-76/84)."""
from dataclasses import dataclass

ALTO, MEDIO, BAIXO = "Alto", "Médio", "Baixo"
FAIXAS = (ALTO, MEDIO, BAIXO)
LGPD, ATUALIZACAO = "Risco LGPD", "Atraso de atualização"


@dataclass(frozen=True)
class CriterioAtencao:
    """Pesos e faixas do índice, lidos dos Parâmetros (editáveis pela GEDA)."""

    peso_lgpd: int
    peso_atualizacao: int
    limite_medio: int
    limite_alto: int


@dataclass(frozen=True)
class IndiceAtencao:
    valor: int  # 0 a 100
    faixa: str  # Alto | Médio | Baixo
    componentes: list[str]  # o que entrou na média (LGPD, ATUALIZACAO)


def pct(parte: int, total: int) -> int | None:
    return round(100 * parte / total) if total else None


def faixa(valor: float, criterio: CriterioAtencao) -> str:
    if valor >= criterio.limite_alto:
        return ALTO
    return MEDIO if valor >= criterio.limite_medio else BAIXO


def indice_atencao(risco_lgpd_pct: float | None, atraso_pct: float | None,
                   criterio: CriterioAtencao) -> IndiceAtencao | None:
    """Média ponderada do risco LGPD (% dos recursos varridos com possível dado pessoal em aberto)
    e do atraso de atualização (% das bases vinculadas com prazo que estão atrasadas), os dois de
    0 a 100. Componente sem dado (None) ou com peso 0 fica fora e os pesos dos demais são
    redistribuídos; sem nenhum componente, não há índice (None)."""
    partes = [(nome, v, peso) for nome, v, peso in (
        (LGPD, risco_lgpd_pct, criterio.peso_lgpd),
        (ATUALIZACAO, atraso_pct, criterio.peso_atualizacao)) if v is not None and peso > 0]
    if not partes:
        return None
    valor = round(sum(v * peso for _, v, peso in partes) / sum(peso for *_, peso in partes))
    return IndiceAtencao(valor=valor, faixa=faixa(valor, criterio),
                         componentes=[nome for nome, *_ in partes])
