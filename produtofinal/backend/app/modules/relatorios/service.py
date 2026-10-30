"""Relatórios da tela Saídas → Relatórios (US20, PBI-60/61/77) — responsável: João.
Cada relatório monta uma tabela (colunas + linhas) com os services dos módulos de origem, no
escopo de órgão do usuário; a prévia mostra as primeiras linhas e a exportação leva todas."""
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

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
from app.modules.relatorios.schemas import PreviaOut, RelatorioOut

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
def _bases_vigentes(db: Session, user: UsuarioAtual):
    plano = pda.plano_vigente(db)
    return plano, (pda.bases_do_plano(db, plano.id, user) if plano else [])


def _pda(db: Session, user: UsuarioAtual) -> Tabela:
    """PBI-61 — situação das bases do PDA vigente (mesma ordem da tela Monitoramento do PDA)."""
    plano, bases = _bases_vigentes(db, user)
    return Tabela(
        colunas=["Sigla", "Órgão", "Base prevista", "Situação", "Prazo de abertura",
                 "Periodicidade", "Vínculo", "Dataset no portal", "Recursos válidos",
                 "Formatos", "Data de publicação"],
        linhas=[[b.orgao_sigla, b.orgao_nome, b.nome_previsto, b.situacao, b.prazo_abertura,
                 b.periodicidade, b.vinculo.replace("_", " "), b.dataset_titulo,
                 b.recursos_validos if b.dataset_id else None, ", ".join(b.formatos),
                 b.data_publicacao] for b in bases],
        referencia=plano.nome if plano else None)


def _atualizacoes(db: Session, user: UsuarioAtual) -> Tabela:
    """Bases vinculadas do PDA vigente em atraso ou próximas do vencimento (ADR-0023); atrasadas
    primeiro, depois pelo vencimento."""
    plano, bases = _bases_vigentes(db, user)
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


def _lgpd(db: Session, user: UsuarioAtual) -> Tabela:
    """Achados pendentes de revisão humana, por prioridade e confiança. Nunca leva valores de
    dados pessoais: só a localização e o tipo (o banco também não os guarda)."""
    achados = lgpd.listar_achados(db, user, status="revisar").achados
    return Tabela(
        colunas=["Prioridade", "Órgão", "Dataset", "Recurso", "Tipo", "Coluna",
                 "Ocorrências", "Confiança (%)", "Método", "Atualizado em"],
        linhas=[[a.prioridade, a.orgao_sigla or a.orgao_nome, a.dataset_titulo, a.recurso_nome,
                 a.tipo_rotulo, a.coluna, a.ocorrencias, a.confianca,
                 "IA" if a.metodo == "ia" else "Regra", a.atualizado_em] for a in achados])


def _orgaos(db: Session, user: UsuarioAtual) -> Tabela:
    """Mesmos indicadores da tela Organizações (US19)."""
    dados = painel.organizacoes(db, user)
    return Tabela(
        colunas=["Órgão", "Siglas no PDA", "Bases previstas", "Bases vinculadas",
                 "Bases publicadas", "Bases em atraso", "Próximas do prazo",
                 "Atualização no prazo (%)", "Atualizações atrasadas", "Datasets no portal",
                 "Recursos válidos", "Recursos em formato fechado"],
        linhas=[[o.nome, ", ".join(o.siglas), o.bases_previstas, o.bases_vinculadas,
                 o.bases_publicadas, o.bases_em_atraso, o.bases_proximas_do_prazo,
                 o.atualizacao_pct, o.atualizacoes_atrasadas, o.datasets_no_portal,
                 o.recursos_validos, o.recursos_formato_fechado] for o in dados.organizacoes],
        referencia=dados.plano.nome if dados.plano else None)


def _nome_orgao(orgs, organizacao_id: int | None) -> str | None:
    o = orgs.get(organizacao_id)
    return (o.sigla or o.titulo).strip() if o else None


def _sem_recurso(db: Session, user: UsuarioAtual) -> Tabela:
    """PBI-51 — datasets ativos sem recurso válido, no escopo de órgão do usuário."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    datasets = [d for d in datasets_sem_recurso(db)
                if not user.restrito_a_orgao or d.organizacao_id in orgs]
    linhas = [[_nome_orgao(orgs, d.organizacao_id), d.titulo, d.name, d.id_ckan,
               d.metadata_created] for d in datasets]
    linhas.sort(key=lambda x: (normalizar_texto(x[0] or ""), normalizar_texto(x[1] or "")))
    return Tabela(colunas=["Órgão", "Dataset", "Name (CKAN)", "ID no CKAN", "Criado em"],
                  linhas=linhas)


def _formatos(db: Session, user: UsuarioAtual) -> Tabela:
    """PBI-53 — recursos atuais fora do parâmetro `formatos_abertos`, no escopo de órgão."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    abertos = list(obter_parametro(db, "formatos_abertos"))
    recursos = [r for r in recursos_formato_fechado(db, abertos)
                if not user.restrito_a_orgao or r.dataset.organizacao_id in orgs]
    linhas = [[_nome_orgao(orgs, r.dataset.organizacao_id), r.dataset.titulo, r.nome,
               (r.formato or "").strip() or "(não informado)", r.last_modified]
              for r in recursos]
    linhas.sort(key=lambda x: (normalizar_texto(x[0] or ""), normalizar_texto(x[1] or ""),
                               normalizar_texto(x[2] or "")))
    return Tabela(colunas=["Órgão", "Dataset", "Recurso", "Formato", "Última atualização"],
                  linhas=linhas, referencia="Formatos abertos: " + ", ".join(abertos))


_MONTADORES: dict[str, Callable[[Session, UsuarioAtual], Tabela]] = {
    "pda": _pda, "atualizacoes": _atualizacoes, "lgpd": _lgpd, "orgaos": _orgaos,
    "sem-recurso": _sem_recurso, "formatos": _formatos,
}


def montar(db: Session, nome: str, user: UsuarioAtual) -> tuple[regras.Definicao, Tabela]:
    definicao = _definicao(nome, user)
    return definicao, _MONTADORES[definicao.id](db, user)


def previa(db: Session, nome: str, user: UsuarioAtual, limite: int = PREVIA_LINHAS) -> PreviaOut:
    definicao, tabela = montar(db, nome, user)
    return PreviaOut(id=definicao.id, titulo=definicao.titulo, referencia=tabela.referencia,
                     hoje=pda.hoje_local(), colunas=tabela.colunas,
                     linhas=[[regras.texto(v) for v in linha] for linha in tabela.linhas[:limite]],
                     total=len(tabela.linhas))


def exportar(db: Session, nome: str, formato: str, user: UsuarioAtual) -> tuple[bytes, str, str]:
    """PBI-60/61 — arquivo completo do relatório: (conteúdo, media type, nome do arquivo)."""
    if formato not in regras.FORMATOS:
        raise Invalido(f"Formato inválido: use {' ou '.join(regras.FORMATOS)}.")
    definicao, tabela = montar(db, nome, user)
    conteudo = (regras.gerar_xlsx(definicao.titulo, tabela.colunas, tabela.linhas)
                if formato == "xlsx" else regras.gerar_csv(tabela.colunas, tabela.linhas))
    return conteudo, regras.MIME[formato], regras.nome_arquivo(definicao.id, formato,
                                                               pda.hoje_local())
