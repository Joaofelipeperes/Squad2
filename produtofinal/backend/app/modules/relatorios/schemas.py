from datetime import date

from pydantic import BaseModel


class RelatorioOut(BaseModel):
    """Cartão da tela Relatórios. Só entram os relatórios cujo módulo de origem o usuário acessa."""

    id: str
    titulo: str
    descricao: str
    icone: str


class PreviaOut(BaseModel):
    """Prévia na tela: as primeiras linhas, já como texto (datas em dd/mm/aaaa)."""

    id: str
    titulo: str
    referencia: str | None  # ex.: nome do PDA vigente; None = não depende de plano
    hoje: date
    colunas: list[str]
    linhas: list[list[str]]
    total: int  # linhas do relatório completo (a exportação leva todas)
