"""Regras puras do módulo relatorios: catálogo dos relatórios e geração de CSV/XLSX/PDF (PBI-60/61),
de um relatório só ou de vários num documento (relatório de um órgão: uma seção por relatório).
Sem banco nem FastAPI (reaproveitáveis numa extensão CKAN — ADR-0004)."""
import csv
import io
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    CondPageBreak,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from app.core.exportacao import sem_formula

FORMATOS = ("xlsx", "csv", "pdf")
MIME = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv; charset=utf-8", "pdf": "application/pdf"}
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
              "Datasets publicados (do PDA ou espontâneos) com atualização em atraso, próxima do "
              "vencimento ou periodicidade não informada, pelo campo Atualização do CKAN e o "
              "last_modified dos recursos.",
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
# Colunas que identificam o órgão: saem no relatório de um órgão só (o órgão vai no título)
COLUNAS_DE_ORGAO = frozenset({"Sigla", "Órgão", "Siglas no PDA"})


@dataclass(frozen=True)
class Secao:
    """Um relatório dentro do documento do órgão."""

    titulo: str
    colunas: list[str]
    linhas: list[list]
    referencia: str | None = None


def sem_colunas_de_orgao(colunas: list[str], linhas: list[list]) -> tuple[list[str], list[list]]:
    """Tira as colunas de `COLUNAS_DE_ORGAO` (relatório já filtrado por um órgão)."""
    manter = [i for i, c in enumerate(colunas) if c not in COLUNAS_DE_ORGAO]
    return [colunas[i] for i in manter], [[linha[i] for i in manter] for linha in linhas]


def transpor(colunas: list[str], linha: list) -> tuple[list[str], list[list]]:
    """Uma linha larga → tabela "Indicador | Valor" (resumo de um órgão)."""
    return ["Indicador", "Valor"], [[c, v] for c, v in zip(colunas, linha, strict=True)]


def slug(texto_: str) -> str:
    """Para nome de arquivo: 'Secretaria da Administração' → 'secretaria-da-administracao'."""
    t = unicodedata.normalize("NFKD", texto_).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "orgao"


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
    if isinstance(valor, float):  # padrão brasileiro; inteiro sem ",0"
        return str(int(valor)) if valor.is_integer() else f"{valor:.1f}".replace(".", ",")
    return str(valor)


def _linha_csv(valores) -> list[str]:
    return [sem_formula(texto(v)) for v in valores]


def gerar_csv(colunas: list[str], linhas: list[list]) -> bytes:
    """CSV para o Excel em pt-BR: BOM UTF-8 e ';' como separador (mesmo padrão do log de acesso)."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(_linha_csv(colunas))
    escritor.writerows(_linha_csv(linha) for linha in linhas)
    return ("﻿" + saida.getvalue()).encode("utf-8")


def gerar_csv_secoes(titulo: str, secoes: Sequence[Secao]) -> bytes:
    """Vários relatórios num CSV só: título do documento e, por seção, uma linha com o título,
    o cabeçalho, as linhas e uma linha em branco."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(_linha_csv([titulo]))
    escritor.writerow([])
    for secao in secoes:
        escritor.writerow(_linha_csv([secao.titulo]
                                     + ([secao.referencia] if secao.referencia else [])))
        escritor.writerow(_linha_csv(secao.colunas))
        escritor.writerows(_linha_csv(linha) for linha in secao.linhas)
        escritor.writerow([])
    return ("﻿" + saida.getvalue()).encode("utf-8")


def _celula(valor):
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)  # openpyxl não grava fuso horário
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    return valor


def _preencher_aba(ws, colunas: list[str], linhas: list[list]) -> None:
    """Cabeçalho em negrito, cabeçalho congelado, filtro, largura ajustada e datas formatadas."""
    for linha in [colunas, *linhas]:
        ws.append([_celula(v) for v in linha])
        # Texto começando com "=" seria gravado como fórmula: força o tipo texto (ADR-0036)
        for c in ws[ws.max_row]:
            if c.data_type == "f":
                c.data_type = "s"
    for c in ws[1]:
        c.font = Font(bold=True)
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


def _salvar(wb: Workbook) -> bytes:
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_xlsx(titulo: str, colunas: list[str], linhas: list[list]) -> bytes:
    """Planilha de um relatório (aba com o título)."""
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]  # limite do Excel para nome de aba
    _preencher_aba(ws, colunas, linhas)
    return _salvar(wb)


def _nome_aba(titulo: str, usados: set[str]) -> str:
    """Nome de aba único de até 31 caracteres ('Relatório de Atualizações' → 'Atualizações')."""
    base = re.sub(r"^Relatório (de |por )?", "", titulo).strip()[:31] or "Relatório"
    nome, n = base, 2
    while nome.lower() in usados:
        sufixo = f" ({n})"
        nome, n = base[:31 - len(sufixo)] + sufixo, n + 1
    usados.add(nome.lower())
    return nome


def gerar_xlsx_secoes(secoes: Sequence[Secao]) -> bytes:
    """Vários relatórios numa planilha: uma aba por seção."""
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    for secao in secoes:
        _preencher_aba(wb.create_sheet(_nome_aba(secao.titulo, usados)), secao.colunas,
                       secao.linhas)
    return _salvar(wb)


PDF_FONTE = 7.5  # pt, células e cabeçalho
PDF_FOLGA = 8  # pt, padding esquerdo + direito da célula
PDF_LARGURA_DESEJADA = 220  # pt, teto do texto de uma célula numa linha só


def _larguras(colunas: list[str], linhas: list[list], total: float) -> list[float]:
    """Larguras somando `total`: cada coluna recebe ao menos a sua maior palavra (não quebra
    palavra no meio) e o espaço que sobra vai para as colunas de texto mais longo."""
    amostra = linhas[:300]
    minimas, desejadas = [], []
    for i, nome in enumerate(colunas):
        textos = [(nome, "Helvetica-Bold")] + [(texto(linha[i]), "Helvetica") for linha in amostra]
        palavra = max(stringWidth(p, fonte, PDF_FONTE) for t, fonte in textos for p in t.split()
                      or [""])
        inteiro = max(stringWidth(t, fonte, PDF_FONTE) for t, fonte in textos)
        minimas.append(palavra + PDF_FOLGA)
        desejadas.append(max(min(inteiro, PDF_LARGURA_DESEJADA) + PDF_FOLGA, minimas[-1]))
    if sum(minimas) >= total:  # nem as palavras cabem: proporcional às mínimas
        return [total * m / sum(minimas) for m in minimas]
    extra = [d - m for d, m in zip(desejadas, minimas, strict=True)]
    sobra = total - sum(minimas)
    if sum(extra) <= sobra:  # tudo cabe numa linha: distribui a folga pelo desejado
        return [total * d / sum(desejadas) for d in desejadas]
    return [m + sobra * e / sum(extra) for m, e in zip(minimas, extra, strict=True)]


def _qtd_linhas(n: int) -> str:
    return f"{n} {'linha' if n == 1 else 'linhas'}"


def _tabela_pdf(colunas: list[str], linhas: list[list], largura: float, estilos) -> LongTable:
    """Tabela do PDF: cabeçalho repetido em cada página e texto quebrado nas células."""
    celula = ParagraphStyle("celula", parent=estilos["BodyText"], fontSize=PDF_FONTE, leading=9)
    cabecalho = ParagraphStyle("cabecalho", parent=celula, fontName="Helvetica-Bold",
                               textColor=colors.HexColor("#334155"))
    dados = [[Paragraph(escape(c), cabecalho) for c in colunas]]
    dados += [[Paragraph(escape(texto(v)), celula) for v in linha] for linha in linhas]
    if not linhas:
        dados.append([Paragraph("Nenhum registro.", celula)] + [""] * (len(colunas) - 1))
    tabela = LongTable(dados, colWidths=_larguras(colunas, linhas, largura), repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        *([("SPAN", (0, 1), (-1, 1))] if not linhas else []),
    ]))
    return tabela


def _documento_pdf(titulo: str, montar_corpo) -> bytes:
    """A4 paisagem (ADR-0027) com rodapé (título e página); `montar_corpo(largura, estilos)`
    devolve os elementos do documento."""
    estilos = getSampleStyleSheet()
    pagina = landscape(A4)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=pagina, leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=titulo,
                            author="Monitor Dados Abertos GO — GEDA/CGE-GO")

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(documento.leftMargin, 0.6 * cm, titulo)
        canvas.drawRightString(pagina[0] - documento.rightMargin, 0.6 * cm,
                               f"Página {documento.page}")
        canvas.restoreState()

    doc.build(montar_corpo(doc.width, estilos), onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()


def gerar_pdf(titulo: str, colunas: list[str], linhas: list[list], *, referencia: str | None,
              gerado_em: datetime) -> bytes:
    """PDF de um relatório (ADR-0027): título, referência, data de geração e total; tabela com o
    cabeçalho repetido em cada página e texto quebrado nas células; rodapé com a paginação."""
    def corpo(largura, estilos):
        subtitulo = " · ".join(filter(None, [
            referencia, f"Gerado em {gerado_em.strftime('%d/%m/%Y %H:%M')}",
            _qtd_linhas(len(linhas))]))
        return [Paragraph(escape(titulo), estilos["Title"]),
                Paragraph(escape(subtitulo), estilos["Normal"]), Spacer(1, 0.4 * cm),
                _tabela_pdf(colunas, linhas, largura, estilos)]
    return _documento_pdf(titulo, corpo)


def gerar_pdf_secoes(titulo: str, secoes: Sequence[Secao], *, subtitulo: str | None,
                     gerado_em: datetime) -> bytes:
    """Vários relatórios num PDF: título e data de geração; por seção, o título, a referência e o
    total de linhas, seguidos da tabela."""
    def corpo(largura, estilos):
        cabeca = " · ".join(filter(None, [subtitulo,
                                          f"Gerado em {gerado_em.strftime('%d/%m/%Y %H:%M')}"]))
        itens = [Paragraph(escape(titulo), estilos["Title"]),
                 Paragraph(escape(cabeca), estilos["Normal"]), Spacer(1, 0.3 * cm)]
        for secao in secoes:
            info = " · ".join(filter(None, [secao.referencia, _qtd_linhas(len(secao.linhas))]))
            # Título da seção não fica sozinho no pé da página, longe da tabela
            itens += [CondPageBreak(4 * cm), Spacer(1, 0.3 * cm),
                      Paragraph(escape(secao.titulo), estilos["Heading2"]),
                      Paragraph(escape(info), estilos["Normal"]), Spacer(1, 0.2 * cm),
                      _tabela_pdf(secao.colunas, secao.linhas, largura, estilos)]
        return itens
    return _documento_pdf(titulo, corpo)


def nome_arquivo(relatorio_id: str, formato: str, hoje: date) -> str:
    return f"relatorio-{relatorio_id}-{hoje.isoformat()}.{formato}"


def nome_arquivo_tabela(titulo: str, formato: str, hoje: date) -> str:
    """Exportação de uma tabela das telas (ADR-0031): `<titulo>-<aaaa-mm-dd>.<formato>`."""
    return f"{slug(titulo) or 'tabela'}-{hoje.isoformat()}.{formato}"


def nome_arquivo_orgao(orgao: str, formato: str, hoje: date) -> str:
    return f"relatorio-{slug(orgao)}-{hoje.isoformat()}.{formato}"
