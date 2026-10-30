"""Regras puras do módulo relatorios: catálogo dos relatórios e geração de CSV/XLSX (PBI-60/61).
Sem banco nem FastAPI (reaproveitáveis numa extensão CKAN — ADR-0004)."""
import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

FORMATOS = ("xlsx", "csv")
MIME = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv; charset=utf-8"}
LARGURA_MAXIMA = 60  # colunas do XLSX (em caracteres)


@dataclass(frozen=True)
class Definicao:
    """Relatório do catálogo. `permissao_origem` = permissão de acesso do módulo de onde vêm os
    dados (além de relatorios.acessar)."""

    id: str
    titulo: str
    descricao: str
    icone: str
    permissao_origem: str


# Ordem e textos do protótipo V1 (#screen-reports, PBI-77)
CATALOGO: tuple[Definicao, ...] = (
    Definicao("pda", "Relatório de Cumprimento do PDA",
              "Situação das bases previstas no Plano de Dados Abertos vigente, por órgão e prazo.",
              "fa-clipboard-check", "pda.acessar"),
    Definicao("atualizacoes", "Relatório de Atualizações",
              "Bases vinculadas com atualização em atraso ou próxima do vencimento, pela "
              "periodicidade do PDA e o last_modified dos recursos.",
              "fa-rotate", "atualizacoes.acessar"),
    Definicao("lgpd", "Relatório de Dados Pessoais",
              "Sinalizações de possíveis dados pessoais pendentes de revisão humana, por "
              "prioridade.", "fa-shield-halved", "lgpd.acessar"),
    Definicao("orgaos", "Relatório por Órgão",
              "Resumo de cumprimento do PDA, atualização e formatos por órgão.",
              "fa-building-columns", "painel.acessar"),
    Definicao("sem-recurso", "Relatório de Datasets sem Recurso",
              "Datasets ativos no portal sem nenhum recurso válido publicado.",
              "fa-circle-question", "inventario.acessar"),
    Definicao("formatos", "Relatório de Formatos não Abertos",
              "Recursos publicados em formatos fora da lista de formatos abertos da GEDA.",
              "fa-file-circle-exclamation", "inventario.acessar"),
)
POR_ID = {d.id: d for d in CATALOGO}


def texto(valor) -> str:
    """Valor de célula como texto (CSV e prévia): datas em dd/mm/aaaa, vazio para None."""
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    return str(valor)


def gerar_csv(colunas: list[str], linhas: list[list]) -> bytes:
    """CSV para o Excel em pt-BR: BOM UTF-8 e ';' como separador (mesmo padrão do log de acesso)."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(colunas)
    escritor.writerows([texto(v) for v in linha] for linha in linhas)
    return ("﻿" + saida.getvalue()).encode("utf-8")


def _celula(valor):
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)  # openpyxl não grava fuso horário
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    return valor


def gerar_xlsx(titulo: str, colunas: list[str], linhas: list[list]) -> bytes:
    """Planilha com cabeçalho em negrito, cabeçalho congelado, filtro e largura ajustada."""
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]  # limite do Excel para nome de aba
    ws.append(colunas)
    for c in ws[1]:
        c.font = Font(bold=True)
    for linha in linhas:
        ws.append([_celula(v) for v in linha])
    for i, nome in enumerate(colunas, start=1):
        letra = get_column_letter(i)
        maior = max([len(nome), *(len(texto(linha[i - 1])) for linha in linhas)])
        ws.column_dimensions[letra].width = min(maior + 2, LARGURA_MAXIMA)
        for (c,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            if isinstance(c.value, datetime):
                c.number_format = "dd/mm/yyyy hh:mm"
            elif isinstance(c.value, date):
                c.number_format = "dd/mm/yyyy"
    ws.freeze_panes = "A2"
    if linhas:
        ws.auto_filter.ref = ws.dimensions
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def nome_arquivo(relatorio_id: str, formato: str, hoje: date) -> str:
    return f"relatorio-{relatorio_id}-{hoje.isoformat()}.{formato}"
