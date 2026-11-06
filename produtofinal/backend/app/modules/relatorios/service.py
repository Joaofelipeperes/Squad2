"""Relatórios da tela Saídas → Relatórios (US20, PBI-60/61/77) — responsável: João.
Cada relatório monta uma tabela (colunas + linhas) com os services dos módulos de origem, no
escopo de órgão do usuário; a prévia mostra as primeiras linhas e a exportação leva todas.

Relatório de um órgão: o usuário escolhe um órgão e quantos relatórios quiser; o "Resumo do órgão"
(os indicadores do relatório por órgão, em "Indicador | Valor"), quando escolhido, abre o documento,
que segue com uma seção por relatório escolhido, montado só com as linhas daquele órgão (PDF com
seções, XLSX com uma aba por seção, CSV com as seções em sequência)."""
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import UsuarioAtual
from app.modules.atualizacoes import regras as regras_atualizacao
from app.modules.lgpd import service as lgpd
from app.modules.metadados.service import datasets_sem_recurso, recursos_formato_fechado
from app.modules.painel import service as painel
from app.modules.parametros.router import obter as obter_parametro
from app.modules.pda import service as pda
from app.modules.pda.regras import normalizar_texto
from app.modules.relatorios import regras
from app.modules.relatorios.dao import RelatoriosDao
from app.modules.relatorios.schemas import (
    OrgaoOpcaoOut,
    PreviaOut,
    RelatorioOrgaoOut,
    RelatorioOut,
)

PREVIA_LINHAS = 50


class ErroRelatorio(Exception):
    pass


class NaoEncontrado(ErroRelatorio):
    pass


class SemPermissao(ErroRelatorio):
    pass


class Invalido(ErroRelatorio):
    pass


@dataclass
class Tabela:
    colunas: list[str]
    linhas: list[list]
    referencia: str | None = None


def catalogo(user: UsuarioAtual) -> list[RelatorioOut]:
    """Relatórios que o usuário pode gerar: exige também o acesso ao módulo de origem."""
    return [RelatorioOut(id=d.id, titulo=d.titulo, descricao=d.descricao, icone=d.icone)
            for d in regras.CATALOGO if user.pode(d.permissao_origem)]


def _definicao(nome: str, user: UsuarioAtual) -> regras.Definicao:
    definicao = regras.POR_ID.get(nome)
    if definicao is None:
        raise NaoEncontrado("Relatório não encontrado.")
    if not user.pode(definicao.permissao_origem):
        raise SemPermissao(f"Sem a permissão {definicao.permissao_origem} exigida por este "
                           "relatório.")
    return definicao


# ------------------------------------------------------------------ relatórios
# Cada montador recebe `orgao` (id da organização): None = todos os órgãos do escopo do usuário.
def _bases_vigentes(db: Session, user: UsuarioAtual, orgao: int | None = None):
    plano = pda.plano_vigente(db)
    bases = pda.bases_do_plano(db, plano.id, user) if plano else []
    if orgao is not None:
        bases = [b for b in bases if b.orgao_chave == str(orgao)]
    return plano, bases


def _pda(db: Session, user: UsuarioAtual, orgao: int | None = None) -> Tabela:
    """PBI-61 — situação das bases do PDA vigente (mesma ordem da tela Monitoramento do PDA)."""
    plano, bases = _bases_vigentes(db, user, orgao)
    return Tabela(
        colunas=["Sigla", "Órgão", "Base prevista", "Situação", "Prazo de abertura",
                 "Periodicidade", "Vínculo", "Dataset no portal", "Recursos válidos",
                 "Formatos", "Data de publicação"],
        linhas=[[b.orgao_sigla, b.orgao_nome, b.nome_previsto, b.situacao, b.prazo_abertura,
                 b.periodicidade, b.vinculo.replace("_", " "), b.dataset_titulo,
                 b.recursos_validos if b.dataset_id else None, ", ".join(b.formatos),
                 b.data_publicacao] for b in bases],
        referencia=plano.nome if plano else None)


def _atualizacoes(db: Session, user: UsuarioAtual, orgao: int | None = None) -> Tabela:
    """Bases vinculadas do PDA vigente em atraso ou próximas do vencimento (ADR-0023); atrasadas
    primeiro, depois pelo vencimento."""
    plano, bases = _bases_vigentes(db, user, orgao)
    hoje = pda.hoje_local()
    alvo = (regras_atualizacao.ATRASADO, regras_atualizacao.PROXIMO_DO_VENCIMENTO)
    linhas = []
    for b in bases:
        situacao = painel.situacao_atualizacao(b, hoje)
        if situacao not in alvo:
            continue
        vencimento = regras_atualizacao.vencimento_atualizacao(
            b.periodicidade, b.ultima_atualizacao, b.periodicidade_original)
        linhas.append([b.orgao_sigla, b.orgao_nome, b.nome_previsto, b.dataset_titulo,
                       b.periodicidade, b.ultima_atualizacao,
                       b.ultima_atualizacao_estimada, vencimento, situacao])
    linhas.sort(key=lambda x: (alvo.index(x[8]), x[7] or hoje, normalizar_texto(x[0])))
    return Tabela(
        colunas=["Sigla", "Órgão", "Base prevista", "Dataset no portal", "Periodicidade",
                 "Última atualização", "Data estimada", "Vencimento", "Situação"],
        linhas=linhas, referencia=plano.nome if plano else None)


def _lgpd(db: Session, user: UsuarioAtual, orgao: int | None = None) -> Tabela:
    """Achados pendentes de revisão humana, por prioridade e confiança. Nunca leva valores de
    dados pessoais: só a localização e o tipo (o banco também não os guarda)."""
    achados = lgpd.listar_achados(db, user, status="revisar",
                                  orgao=str(orgao) if orgao is not None else None).achados
    return Tabela(
        colunas=["Prioridade", "Órgão", "Dataset", "Recurso", "Tipo", "Coluna",
                 "Ocorrências", "Confiança (%)", "Método", "Atualizado em"],
        linhas=[[a.prioridade, a.orgao_sigla or a.orgao_nome, a.dataset_titulo, a.recurso_nome,
                 a.tipo_rotulo, a.coluna, a.ocorrencias, a.confianca,
                 "IA" if a.metodo == "ia" else "Regra", a.atualizado_em] for a in achados])


def _orgaos(db: Session, user: UsuarioAtual, orgao: int | None = None) -> Tabela:
    """Mesmos indicadores da tela Organizações (US19)."""
    dados = painel.organizacoes(db, user)
    if orgao is not None:
        dados.organizacoes = [o for o in dados.organizacoes if o.organizacao_id == orgao]
    # Riscos LGPD só para quem vê o módulo lgpd (o painel já devolve None sem a permissão)
    lgpd = dados.lgpd_visivel
    return Tabela(
        colunas=["Órgão", "Siglas no PDA", "Bases previstas", "Bases vinculadas",
                 "Bases publicadas", "Bases em atraso", "Próximas do prazo",
                 "Atualização no prazo (%)", "Atualizações atrasadas", "Datasets no portal",
                 "Recursos válidos", "Recursos em formato fechado"]
        + (["Riscos LGPD (recursos)", "Recursos varridos"] if lgpd else [])
        + ["Índice de atenção", "Índice de atenção (0-100)"],
        linhas=[[o.nome, ", ".join(o.siglas), o.bases_previstas, o.bases_vinculadas,
                 o.bases_publicadas, o.bases_em_atraso, o.bases_proximas_do_prazo,
                 o.atualizacao_pct, o.atualizacoes_atrasadas, o.datasets_no_portal,
                 o.recursos_validos, o.recursos_formato_fechado]
                + ([o.riscos_lgpd, o.lgpd_recursos_analisados] if lgpd else [])
                + [o.indice_atencao, o.indice_atencao_valor] for o in dados.organizacoes],
        referencia=dados.plano.nome if dados.plano else None)


def _nome_orgao(orgs, organizacao_id: int | None) -> str | None:
    o = orgs.get(organizacao_id)
    return (o.sigla or o.titulo).strip() if o else None


def _sem_recurso(db: Session, user: UsuarioAtual, orgao: int | None = None) -> Tabela:
    """PBI-51 — datasets ativos sem recurso válido, no escopo de órgão do usuário."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    datasets = [d for d in datasets_sem_recurso(db)
                if (not user.restrito_a_orgao or d.organizacao_id in orgs)
                and (orgao is None or d.organizacao_id == orgao)]
    linhas = [[_nome_orgao(orgs, d.organizacao_id), d.titulo, d.name, d.id_ckan,
               d.metadata_created] for d in datasets]
    linhas.sort(key=lambda x: (normalizar_texto(x[0] or ""), normalizar_texto(x[1] or "")))
    return Tabela(colunas=["Órgão", "Dataset", "Name (CKAN)", "ID no CKAN", "Criado em"],
                  linhas=linhas)


def _formatos(db: Session, user: UsuarioAtual, orgao: int | None = None) -> Tabela:
    """PBI-53 — recursos atuais fora do parâmetro `formatos_abertos`, no escopo de órgão."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    abertos = list(obter_parametro(db, "formatos_abertos"))
    recursos = [r for r in recursos_formato_fechado(db, abertos)
                if (not user.restrito_a_orgao or r.dataset.organizacao_id in orgs)
                and (orgao is None or r.dataset.organizacao_id == orgao)]
    linhas = [[_nome_orgao(orgs, r.dataset.organizacao_id), r.dataset.titulo, r.nome,
               (r.formato or "").strip() or "(não informado)", r.last_modified]
              for r in recursos]
    linhas.sort(key=lambda x: (normalizar_texto(x[0] or ""), normalizar_texto(x[1] or ""),
                               normalizar_texto(x[2] or "")))
    return Tabela(colunas=["Órgão", "Dataset", "Recurso", "Formato", "Última atualização"],
                  linhas=linhas, referencia="Formatos abertos: " + ", ".join(abertos))


_MONTADORES: dict[str, Callable[[Session, UsuarioAtual, int | None], Tabela]] = {
    "pda": _pda, "atualizacoes": _atualizacoes, "lgpd": _lgpd, "orgaos": _orgaos,
    "sem-recurso": _sem_recurso, "formatos": _formatos,
}


def montar(db: Session, nome: str, user: UsuarioAtual,
           orgao: int | None = None) -> tuple[regras.Definicao, Tabela]:
    """Tabela do relatório; com `orgao`, só as linhas dele e sem as colunas que identificam o
    órgão (o órgão vai no título). O relatório por órgão vira "Indicador | Valor"."""
    definicao = _definicao(nome, user)
    tabela = _MONTADORES[definicao.id](db, user, orgao)
    if orgao is not None:
        colunas, linhas = regras.sem_colunas_de_orgao(tabela.colunas, tabela.linhas)
        if definicao.id == "orgaos" and len(linhas) == 1:
            colunas, linhas = regras.transpor(colunas, linhas[0])
        tabela = Tabela(colunas, linhas, tabela.referencia)
    return definicao, tabela


def _previa_out(definicao: regras.Definicao, tabela: Tabela, limite: int) -> PreviaOut:
    return PreviaOut(id=definicao.id, titulo=definicao.titulo, referencia=tabela.referencia,
                     hoje=pda.hoje_local(), colunas=tabela.colunas,
                     linhas=[[regras.texto(v) for v in linha] for linha in tabela.linhas[:limite]],
                     total=len(tabela.linhas))


def previa(db: Session, nome: str, user: UsuarioAtual, limite: int = PREVIA_LINHAS) -> PreviaOut:
    definicao, tabela = montar(db, nome, user)
    return _previa_out(definicao, tabela, limite)


# ------------------------------------------------------------------ relatório de um órgão
def _rotulo_orgao(o) -> str:
    titulo = o.titulo.strip()
    return f"{titulo} ({o.sigla.strip()})" if o.sigla and o.sigla.strip() else titulo


def orgaos_disponiveis(db: Session, user: UsuarioAtual) -> list[OrgaoOpcaoOut]:
    """Órgãos que o usuário pode escolher (o escopo de órgão dele), por nome."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    return sorted((OrgaoOpcaoOut(id=i, nome=_rotulo_orgao(o)) for i, o in orgs.items()),
                  key=lambda o: normalizar_texto(o.nome))


RESUMO = "orgaos"  # o relatório por órgão vira o "Resumo do órgão", 1ª seção quando escolhido
TITULO_RESUMO = "Resumo do órgão"


def _orgao_e_relatorios(db: Session, orgao: int, relatorios: list[str],
                        user: UsuarioAtual) -> tuple[OrgaoOpcaoOut, list[str]]:
    """Valida o órgão (no escopo do usuário) e monta a lista das seções escolhidas, sem
    repetição, cada uma com a permissão do módulo de origem: o resumo do órgão ("orgaos") primeiro,
    se escolhido, e depois os relatórios na ordem do catálogo."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    if orgao not in orgs:
        raise NaoEncontrado("Órgão não encontrado.")
    escolhidos = {r.strip() for r in relatorios if r and r.strip()}
    for nome in escolhidos:
        _definicao(nome, user)  # 404 desconhecido, 403 sem permissão de origem
    resumo = [RESUMO] if RESUMO in escolhidos else []
    ordem = resumo + [d.id for d in regras.CATALOGO if d.id in escolhidos - {RESUMO}]
    if not ordem:
        raise Invalido("Escolha ao menos um relatório.")
    return OrgaoOpcaoOut(id=orgao, nome=_rotulo_orgao(orgs[orgao])), ordem


def _secao_do_orgao(db: Session, nome: str, user: UsuarioAtual,
                    orgao: int) -> tuple[regras.Definicao, Tabela]:
    """Seção do documento do órgão; o relatório por órgão leva o título "Resumo do órgão"."""
    definicao, tabela = montar(db, nome, user, orgao)
    if nome == RESUMO:
        definicao = replace(definicao, titulo=TITULO_RESUMO)
    return definicao, tabela


def previa_orgao(db: Session, orgao: int, relatorios: list[str], user: UsuarioAtual,
                 limite: int = PREVIA_LINHAS) -> RelatorioOrgaoOut:
    """Prévia do relatório de um órgão: uma seção por item escolhido (resumo primeiro)."""
    escolhido, nomes = _orgao_e_relatorios(db, orgao, relatorios, user)
    secoes = [_previa_out(*_secao_do_orgao(db, nome, user, orgao), limite) for nome in nomes]
    return RelatorioOrgaoOut(orgao=escolhido, hoje=pda.hoje_local(), secoes=secoes)


def exportar_orgao(db: Session, orgao: int, relatorios: list[str], formato: str,
                   user: UsuarioAtual) -> tuple[bytes, str, str]:
    """Arquivo do relatório de um órgão: (conteúdo, media type, nome do arquivo)."""
    if formato not in regras.FORMATOS:
        raise Invalido(f"Formato inválido: use {', '.join(regras.FORMATOS)}.")
    escolhido, nomes = _orgao_e_relatorios(db, orgao, relatorios, user)
    secoes = []
    for nome in nomes:
        definicao, tabela = _secao_do_orgao(db, nome, user, orgao)
        secoes.append(regras.Secao(definicao.titulo, tabela.colunas, tabela.linhas,
                                   tabela.referencia))
    titulo = f"Relatório do órgão — {escolhido.nome}"
    if formato == "xlsx":
        conteudo = regras.gerar_xlsx_secoes(secoes)
    elif formato == "pdf":
        conteudo = regras.gerar_pdf_secoes(
            titulo, secoes, subtitulo=None, gerado_em=_agora_local())
    else:
        conteudo = regras.gerar_csv_secoes(titulo, secoes)
    return conteudo, regras.MIME[formato], regras.nome_arquivo_orgao(
        _sigla_do_orgao(db, orgao, user), formato, pda.hoje_local())


def _sigla_do_orgao(db: Session, orgao: int, user: UsuarioAtual) -> str:
    """Sigla do órgão (ou o título) para o nome do arquivo."""
    o = RelatoriosDao.de(db, user).organizacoes_visiveis(user)[orgao]
    return (o.sigla or o.titulo).strip()


def _agora_local() -> datetime:
    """Data e hora no fuso da aplicação (mesma regra de `pda.hoje_local`), para o PDF."""
    try:
        fuso = ZoneInfo(get_settings().timezone)
    except ZoneInfoNotFoundError:
        fuso = timezone(timedelta(hours=-3))
    return datetime.now(fuso)


def exportar(db: Session, nome: str, formato: str, user: UsuarioAtual) -> tuple[bytes, str, str]:
    """PBI-60/61 — arquivo completo do relatório: (conteúdo, media type, nome do arquivo).
    PDF (ADR-0027) leva também título, referência e data de geração."""
    if formato not in regras.FORMATOS:
        raise Invalido(f"Formato inválido: use {', '.join(regras.FORMATOS)}.")
    definicao, tabela = montar(db, nome, user)
    if formato == "xlsx":
        conteudo = regras.gerar_xlsx(definicao.titulo, tabela.colunas, tabela.linhas)
    elif formato == "pdf":
        conteudo = regras.gerar_pdf(definicao.titulo, tabela.colunas, tabela.linhas,
                                    referencia=tabela.referencia, gerado_em=_agora_local())
    else:
        conteudo = regras.gerar_csv(tabela.colunas, tabela.linhas)
    return conteudo, regras.MIME[formato], regras.nome_arquivo(definicao.id, formato,
                                                               pda.hoje_local())
