"""Relatórios da tela Saídas → Relatórios (US20, PBI-60/61/77) — responsável: João.
Cada relatório monta uma tabela (colunas + linhas) com os services dos módulos de origem, no
escopo de órgão do usuário; a prévia mostra as primeiras linhas e a exportação leva todas.

Relatório de um órgão: o usuário escolhe um órgão e quantos relatórios quiser; o "Resumo do órgão"
(os indicadores do relatório por órgão, em "Indicador | Valor"), quando escolhido, abre o documento,
que segue com uma seção por relatório escolhido, montado só com as linhas daquele órgão (PDF com
seções, XLSX com uma aba por seção, CSV com as seções em sequência)."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import UsuarioAtual
from app.core.permissoes import P
from app.modules.atualizacoes import regras as regras_atualizacao
from app.modules.inventario import regras as regras_inventario
from app.modules.inventario.service import listar_datasets
from app.modules.lgpd import regras as regras_lgpd
from app.modules.lgpd import service as lgpd
from app.modules.metadados import regras as regras_metadados
from app.modules.metadados.service import (
    datasets_sem_recurso,
    recursos_formato_fechado,
    recursos_validos,
)
from app.modules.painel import service as painel
from app.modules.parametros.router import obter as obter_parametro
from app.modules.pda import service as pda
from app.modules.pda.regras import (
    EM_ATRASO,
    EM_DIA,
    NAO_PUBLICADO,
    PRAZO_VENCIDO,
    PROXIMO_DO_PRAZO,
    PUBLICADO,
    SEM_RECURSO,
    normalizar_texto,
)
from app.modules.relatorios import regras
from app.modules.relatorios.dao import RelatoriosDao
from app.modules.relatorios.schemas import (
    OrgaoOpcaoOut,
    PreviaOut,
    RelatorioOrgaoOut,
    RelatorioOut,
    TabelaExportarIn,
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
    linhas = [[_nome_orgao(orgs, d.organizacao_id), d.titulo, d.id_ckan,
               d.metadata_created] for d in datasets]
    linhas.sort(key=lambda x: (normalizar_texto(x[0] or ""), normalizar_texto(x[1] or "")))
    return Tabela(colunas=["Órgão", "Dataset", "ID no CKAN", "Criado em"],
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


# Seções do relatório detalhado do órgão (pedido da GEDA em 05/11): cada número do resumo vira a
# lista dos itens que ele conta. Cada seção exige o acesso ao módulo de onde vêm os dados.
_ORDEM_SITUACAO_PDA = {EM_ATRASO: 0, PROXIMO_DO_PRAZO: 1, PRAZO_VENCIDO: 2, NAO_PUBLICADO: 3,
                       SEM_RECURSO: 4, EM_DIA: 5, PUBLICADO: 6}
_ORDEM_ATUALIZACAO = {regras_atualizacao.ATRASADO: 0, regras_atualizacao.PROXIMO_DO_VENCIMENTO: 1,
                      regras_atualizacao.ATUALIZADO: 2}
_COLUNAS_BASES = ["Base prevista", "Situação", "Prazo de abertura", "Periodicidade",
                  "Dataset no portal", "Data de publicação"]


def _dia(valor: datetime | None) -> date | None:
    """Data-hora → dia no fuso da aplicação (as listas do relatório mostram só a data)."""
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC)
    return valor.astimezone(_agora_local().tzinfo).date()


def _dataset_da_base(b) -> str | None:
    """Dataset do portal ligado à base, pelo título do CKAN (o informado no PDA se pendente)."""
    if b.vinculo == "resolvido":
        nome = b.dataset_titulo or b.dataset_name or "—"
        return nome + (" (fora do portal)" if b.dataset_ativo is False else "")
    if b.vinculo == "pendente":
        return f"{b.dataset_name_planilha or b.dataset_id_ckan_planilha} (vínculo pendente)"
    return None


def _linhas_bases(bases) -> list[list]:
    """Bases do PDA: as que pedem ação primeiro (em atraso, próximas do prazo...), depois prazo."""
    ordenadas = sorted(bases, key=lambda b: (_ORDEM_SITUACAO_PDA.get(b.situacao, 9),
                                             b.prazo_abertura or date.max,
                                             normalizar_texto(b.nome_previsto)))
    return [[b.nome_previsto, b.situacao, b.prazo_abertura, b.periodicidade, _dataset_da_base(b),
             _dia(b.data_publicacao)] for b in ordenadas]


def _secoes_pda(db: Session, user: UsuarioAtual, orgao: int) -> list[tuple[str, regras.Secao]]:
    plano, bases = _bases_vigentes(db, user, orgao)
    ref = plano.nome if plano else "Nenhum PDA vigente"
    secoes = [("bases", regras.Secao("Bases previstas no PDA", _COLUNAS_BASES,
                                      _linhas_bases(bases), ref)),
              ("bases-em-atraso", regras.Secao(
                  "Bases em atraso", _COLUNAS_BASES,
                  _linhas_bases([b for b in bases if b.situacao == EM_ATRASO]), ref)),
              ("bases-proximas", regras.Secao(
                  "Bases próximas do prazo", _COLUNAS_BASES,
                  _linhas_bases([b for b in bases if b.situacao == PROXIMO_DO_PRAZO]), ref))]
    return secoes


def _secao_atualizacao(db: Session, user: UsuarioAtual, orgao: int) -> regras.Secao:
    """Cada base vinculada com a situação de atualização pela periodicidade do PDA (ADR-0023):
    atrasadas primeiro, depois pelo vencimento."""
    plano, bases = _bases_vigentes(db, user, orgao)
    hoje = pda.hoje_local()
    linhas = []
    for b in bases:
        if not b.dataset_id:
            continue
        vencimento = regras_atualizacao.vencimento_atualizacao(
            b.periodicidade, b.ultima_atualizacao, b.periodicidade_original)
        linhas.append([b.nome_previsto, _dataset_da_base(b), b.periodicidade,
                       _dia(b.ultima_atualizacao), b.ultima_atualizacao_estimada, vencimento,
                       painel.situacao_atualizacao(b, hoje)])
    linhas.sort(key=lambda x: (_ORDEM_ATUALIZACAO.get(x[6], 9), x[5] or date.max,
                               normalizar_texto(x[0])))
    return regras.Secao("Atualização das bases",
                        ["Base prevista", "Dataset no portal", "Periodicidade",
                         "Última atualização", "Data estimada", "Vencimento", "Situação"],
                        linhas, plano.nome if plano else "Nenhum PDA vigente")


def _secoes_portal(db: Session, user: UsuarioAtual, orgao: int) -> list[tuple[str, regras.Secao]]:
    """Datasets e recursos do órgão no portal (inventário da última coleta)."""
    datasets = [d for d in listar_datasets(db, user, orgao=orgao).datasets
                if d.situacao != regras_inventario.FORA_DO_PORTAL]
    datasets.sort(key=lambda d: normalizar_texto(d.titulo))
    abertos = list(obter_parametro(db, "formatos_abertos"))
    recursos = sorted((r for r in recursos_validos(db) if r.dataset.organizacao_id == orgao),
                      key=lambda r: (normalizar_texto(r.dataset.titulo),
                                     normalizar_texto(r.nome or ""), r.id))

    def ultima(r) -> str:
        data = _dia(r.last_modified or r.created_ckan)
        return regras.texto(data) + (" (est.)" if data and not r.last_modified else "")

    fechados = [r for r in recursos if not regras_metadados.eh_formato_aberto(r.formato, abertos)]
    ref_formatos = f"Formatos abertos (parâmetro da GEDA): {', '.join(abertos)}"
    return [
        ("datasets", regras.Secao(
            "Datasets no portal",
            ["Dataset", "Criado no CKAN", "Recursos válidos", "Formatos", "Última atualização",
             "Tipo de base", "Situação no portal"],
            [[d.titulo, _dia(d.metadata_created), d.recursos_validos, ", ".join(d.formatos),
              _dia(d.ultima_atualizacao), d.tipo_base, d.situacao] for d in datasets])),
        ("sem-recurso", regras.Secao(
            "Datasets sem recurso", ["Dataset", "Criado no CKAN", "ID no CKAN"],
            [[d.titulo, _dia(d.metadata_created), d.id_ckan] for d in datasets
             if d.situacao == regras_inventario.SEM_RECURSO])),
        ("recursos", regras.Secao(
            "Recursos válidos", ["Dataset", "Recurso", "Formato", "Formato aberto",
                                 "Última atualização"],
            [[r.dataset.titulo, r.nome, r.formato or "sem formato",
              regras_metadados.eh_formato_aberto(r.formato, abertos), ultima(r)]
             for r in recursos], ref_formatos)),
        ("formatos", regras.Secao(
            "Recursos em formato fechado", ["Dataset", "Recurso", "Formato", "Última atualização"],
            [[r.dataset.titulo, r.nome, r.formato or "sem formato", ultima(r)] for r in fechados],
            ref_formatos)),
    ]


def _secao_lgpd(db: Session, user: UsuarioAtual, orgao: int) -> regras.Secao:
    """Achados ainda em aberto (aguardando revisão ou confirmados): onde estão e de que tipo.
    Nunca o valor encontrado (o banco também não o guarda)."""
    achados = [a for a in lgpd.listar_achados(db, user, orgao=str(orgao)).achados
               if a.status in regras_lgpd.EM_ABERTO]
    return regras.Secao(
        "Possíveis dados pessoais em aberto",
        ["Prioridade", "Dataset", "Arquivo", "Tipo", "Coluna", "Primeira linha", "Células",
         "Situação"],
        [[a.prioridade, a.dataset_titulo, a.recurso_nome, a.tipo_rotulo, a.coluna, a.linha,
          a.ocorrencias, regras_lgpd.STATUS.get(a.status, a.status)] for a in achados])


def _secoes_do_orgao(db: Session, orgao: int,
                     user: UsuarioAtual) -> tuple[OrgaoOpcaoOut, list[tuple[str, regras.Secao]]]:
    """Valida o órgão (escopo do usuário) e monta o relatório detalhado: o resumo e, para cada
    número dele, a lista do que ele conta. Seção sem a permissão do módulo de origem fica fora."""
    orgs = RelatoriosDao.de(db, user).organizacoes_visiveis(user)
    if orgao not in orgs:
        raise NaoEncontrado("Órgão não encontrado.")
    secoes: list[tuple[str, regras.Secao]] = []
    if user.pode(P.PAINEL_ACESSAR):
        _, tabela = montar(db, "orgaos", user, orgao)
        secoes.append(("resumo", regras.Secao("Resumo do órgão", tabela.colunas, tabela.linhas,
                                              tabela.referencia)))
    if user.pode(P.PDA_ACESSAR):
        secoes += _secoes_pda(db, user, orgao)
    if user.pode(P.ATUALIZACOES_ACESSAR):
        secoes.append(("atualizacao", _secao_atualizacao(db, user, orgao)))
    if user.pode(P.INVENTARIO_ACESSAR):
        secoes += _secoes_portal(db, user, orgao)
    if user.pode(P.LGPD_ACESSAR):
        secoes.append(("dados-pessoais", _secao_lgpd(db, user, orgao)))
    if not secoes:
        raise SemPermissao("Sem acesso aos módulos que compõem o relatório do órgão.")
    return OrgaoOpcaoOut(id=orgao, nome=_rotulo_orgao(orgs[orgao])), secoes


def previa_orgao(db: Session, orgao: int, user: UsuarioAtual,
                 limite: int = PREVIA_LINHAS) -> RelatorioOrgaoOut:
    """Prévia do relatório detalhado de um órgão: as primeiras linhas de cada seção."""
    escolhido, secoes = _secoes_do_orgao(db, orgao, user)
    hoje = pda.hoje_local()
    return RelatorioOrgaoOut(orgao=escolhido, hoje=hoje, secoes=[
        PreviaOut(id=id_, titulo=s.titulo, referencia=s.referencia, hoje=hoje, colunas=s.colunas,
                  linhas=[[regras.texto(v) for v in linha] for linha in s.linhas[:limite]],
                  total=len(s.linhas)) for id_, s in secoes])


def exportar_orgao(db: Session, orgao: int, formato: str,
                   user: UsuarioAtual) -> tuple[bytes, str, str]:
    """Arquivo do relatório detalhado de um órgão: (conteúdo, media type, nome do arquivo)."""
    if formato not in regras.FORMATOS:
        raise Invalido(f"Formato inválido: use {', '.join(regras.FORMATOS)}.")
    escolhido, pares = _secoes_do_orgao(db, orgao, user)
    secoes = [s for _, s in pares]
    titulo = f"Relatório do órgão — {escolhido.nome}"
    if formato == "xlsx":
        conteudo = regras.gerar_xlsx_secoes(secoes)
    elif formato == "pdf":
        conteudo = regras.gerar_pdf_secoes(titulo, secoes, subtitulo=None,
                                           gerado_em=_agora_local())
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


def exportar_tabela(dados: TabelaExportarIn) -> tuple[bytes, str, str]:
    """Exportação de uma tabela das telas (ADR-0031): o navegador manda as linhas que o usuário já
    vê (filtros e ordenação da tela) e aqui só se gera o arquivo, com o mesmo gerador dos
    relatórios. Não consulta o banco: nada além do que a tela já mostrou sai no arquivo."""
    largura = len(dados.colunas)
    if any(len(linha) != largura for linha in dados.linhas):
        raise Invalido("Toda linha deve ter o mesmo número de colunas do cabeçalho.")
    if dados.formato == "xlsx":
        conteudo = regras.gerar_xlsx(dados.titulo, dados.colunas, dados.linhas)
    else:
        conteudo = regras.gerar_pdf(dados.titulo, dados.colunas, dados.linhas,
                                    referencia=dados.filtros, gerado_em=_agora_local())
    return (conteudo, regras.MIME[dados.formato],
            regras.nome_arquivo_tabela(dados.titulo, dados.formato, pda.hoje_local()))
