from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field


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


class OrgaoOpcaoOut(BaseModel):
    """Órgão que pode ser escolhido no relatório de um órgão (escopo de órgão do usuário)."""

    id: int
    nome: str


class RelatorioOrgaoOut(BaseModel):
    """Prévia do relatório de um órgão: uma seção por relatório escolhido, já filtrada."""

    orgao: OrgaoOpcaoOut
    hoje: date
    secoes: list[PreviaOut]


LINHAS_MAXIMO_TABELA = 20000  # o inventário inteiro tem ~3 mil recursos; folga para crescer
# Tetos da exportação de tabela (ADR-0036): o PDF custa CPU e memória por célula, e o pedido vem
# do navegador — sem teto, um único pedido ocupava a API por minutos.
CELULA_MAXIMO = 2000            # caracteres por célula
LINHAS_MAXIMO_PDF = 5000
CARACTERES_MAXIMO_PDF = 1_500_000  # soma do texto de todas as células


class TabelaExportarIn(BaseModel):
    """Tabela de uma tela (Datasets, PDA, Atualizações, Organizações) como o usuário a vê — com os
    filtros e a ordenação da tela, todas as páginas — para virar PDF ou Excel (ADR-0031)."""

    titulo: str = Field(min_length=1, max_length=120)
    filtros: str | None = Field(default=None, max_length=500)  # ex.: "Órgão: SES · Situação: Atrasado"
    colunas: list[Annotated[str, Field(max_length=200)]] = Field(min_length=1, max_length=30)
    linhas: list[list[Annotated[str, Field(max_length=CELULA_MAXIMO)] | int | float | None]] = (
        Field(max_length=LINHAS_MAXIMO_TABELA))
    formato: Literal["pdf", "xlsx"]
