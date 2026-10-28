"""Monitoramento do PDA — responsável: Humberto (Eixo 1).

- PBI-12: importação da planilha do PDA e vínculo das bases com o CKAN;
- PBI-13: vínculo SEMPRE pelo ID do dataset (o `name` da planilha só serve para achar o ID);
- PBI-15: dataset vinculado que sumiu do portal (excluído/privado) volta a "não publicado";
- PBI-19: situação de cada base quanto ao prazo de abertura;
- PBI-20/21: lista e filtros da tela; PBI-22: janela de alerta (parâmetro da GEDA).

Vários PDAs podem estar cadastrados; o VIGENTE rege a tela e os indicadores de gestão (decisão de
07/10/2026, Humberto — pendente de validação da GEDA). Para outros módulos (painel, relatorios,
assistente): `plano_vigente(db)` e `bases_do_plano(db, plano_id, user)`.

Acesso ao banco só pelo `PdaDao` (ADR-0019): excluir é exclusão lógica e toda gravação registra
o usuário que agiu (`created_id`/`changed_id`).
"""
import re
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.deps import UsuarioAtual, exigir_mesmo_orgao
from app.modules.atualizacoes.service import ultima_atualizacao_real
from app.modules.inventario.models import Dataset
from app.modules.inventario.service import recursos_atuais
from app.modules.parametros.router import obter as obter_parametro
from app.modules.pda import regras
from app.modules.pda.dao import PdaDao
from app.modules.pda.models import BasePrevista, PlanoPda
from app.modules.pda.schemas import (
    BaseIn,
    BaseOut,
    BasesOut,
    CampoPlanilhaOut,
    ColunasPlanilhaOut,
    DatasetOpcaoOut,
    FormularioOut,
    IdsCkanOut,
    ImportacaoResumoOut,
    LinhaIdCkanOut,
    LinhaIgnoradaOut,
    OpcaoOut,
    OpcoesOut,
    PlanoIn,
    PlanoOut,
)


# ------------------------------------------------------------------ erros de domínio
class ErroPda(Exception):
    status_http = 400


class NaoEncontrado(ErroPda):
    status_http = 404


class Conflito(ErroPda):
    status_http = 409


class Invalido(ErroPda):
    status_http = 422


_MSG_CONFLITO = ("Conflito ao gravar o PDA (nome repetido ou outro PDA definido como vigente ao "
                 "mesmo tempo). Atualize a tela e tente novamente.")


@contextmanager
def _transacao(dao: PdaDao) -> Iterator[None]:
    """Executa a gravação e o commit. Violação de índice único em QUALQUER etapa (no PostgreSQL
    ela ocorre no flush do INSERT/UPDATE, não no commit) → 409; qualquer erro → rollback."""
    try:
        yield
        dao.commit()
    except IntegrityError as exc:  # corrida: mesmo nome ou dois vigentes em paralelo
        dao.rollback()
        raise Conflito(_MSG_CONFLITO) from exc
    except Exception:
        dao.rollback()
        raise


# ------------------------------------------------------------------ contexto de cálculo
def hoje_local() -> date:
    """Data de hoje no fuso da aplicação (America/Sao_Paulo)."""
    try:
        fuso = ZoneInfo(get_settings().timezone)
    except ZoneInfoNotFoundError:  # SO sem base de fusos: Brasília é UTC-3 fixo desde 2019
        fuso = timezone(timedelta(hours=-3))
    return datetime.now(fuso).date()


def janela_alerta_dias(db: Session) -> int:
    """PBI-22 — parâmetro `janela_alerta_prazo_dias` editável pela GEDA."""
    return int(obter_parametro(db, "janela_alerta_prazo_dias"))


# ------------------------------------------------------------------ planos
def plano_vigente(db: Session) -> PlanoPda | None:
    """PDA vigente — rege a tela e os indicadores/relatórios de gestão das bases."""
    return PdaDao(db).plano_vigente()


def _plano_ou_404(dao: PdaDao, plano_id: int) -> PlanoPda:
    plano = dao.plano(plano_id)
    if plano is None:
        raise NaoEncontrado("PDA não encontrado.")
    return plano


@dataclass(frozen=True)
class _Contagens:
    bases: int = 0       # bases visíveis ao usuário (todas, sem escopo de órgão)
    resolvidos: int = 0  # vínculos resolvidos
    pendentes: int = 0   # vínculos pendentes


def _contagens(dao: PdaDao, user: UsuarioAtual | None = None,
               plano_ids: list[int] | None = None) -> dict[int, _Contagens]:
    """plano_id → contagens das bases. Com `user`, aplica o escopo de órgão (usuário restrito só
    conta as bases do próprio órgão, como em `GET /bases`)."""
    return {pid: _Contagens(int(n), int(res), int(pend))
            for pid, n, res, pend in dao.contagens(user, plano_ids)}


def _utc(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


def plano_out(plano: PlanoPda, contagens: _Contagens | None = None, *,
              restrito: bool = False) -> PlanoOut:
    """`restrito=True` (usuário restrito a órgão): `total_bases` passa a ser o total de bases do
    órgão dele (`contagens.bases`), coerente com `total_previstas` de `GET /bases`."""
    c = contagens or _Contagens()
    return PlanoOut(
        id=plano.id, nome=plano.nome, vigencia_inicio=plano.vigencia_inicio,
        vigencia_fim=plano.vigencia_fim, vigente=plano.vigente, arquivo_nome=plano.arquivo_nome,
        importado_por=plano.importado_por, importado_em=_utc(plano.importado_em),
        total_bases=c.bases if restrito else plano.total_bases,
        vinculos_resolvidos=c.resolvidos, vinculos_pendentes=c.pendentes)


def _restrito(user: UsuarioAtual | None) -> bool:
    return user is not None and user.restrito_a_orgao


def _plano_out_db(dao: PdaDao, plano: PlanoPda, user: UsuarioAtual | None = None) -> PlanoOut:
    return plano_out(plano, _contagens(dao, user, [plano.id]).get(plano.id),
                     restrito=_restrito(user))


def listar_planos(db: Session, user: UsuarioAtual | None = None) -> list[PlanoOut]:
    """PDAs cadastrados: vigente primeiro, depois os importados mais recentemente. Totais e
    vínculos respeitam o escopo de órgão do `user`."""
    dao = PdaDao.de(db, user)
    contagens = _contagens(dao, user)
    return [plano_out(p, contagens.get(p.id), restrito=_restrito(user)) for p in dao.planos()]


def _tornar_unico_vigente(dao: PdaDao, plano: PlanoPda) -> None:
    """Desmarca todos e marca o escolhido, nessa ordem (o índice único parcial
    `uq_pda_plano_vigente` recusaria dois vigentes ao mesmo tempo)."""
    dao.desmarcar_vigentes()
    plano.vigente = True
    dao.save_generic(plano)


def definir_vigente(db: Session, plano_id: int, user: UsuarioAtual | None = None) -> PlanoOut:
    """Escolhe o PDA vigente (há no máximo um). Troca concorrente → 409."""
    dao = PdaDao.de(db, user)
    plano = _plano_ou_404(dao, plano_id)
    if not plano.vigente:
        with _transacao(dao):
            _tornar_unico_vigente(dao, plano)
    return _plano_out_db(dao, plano)


def excluir_plano(db: Session, plano_id: int, user: UsuarioAtual | None = None) -> None:
    """Exclui (exclusão lógica) um PDA e suas bases. O vigente só pode ser excluído quando é o
    ÚNICO PDA cadastrado (havendo outros, defina outro como vigente antes)."""
    dao = PdaDao.de(db, user)
    plano = _plano_ou_404(dao, plano_id)
    if plano.vigente and dao.total_de_planos() > 1:
        raise Conflito("O PDA vigente não pode ser excluído enquanto houver outros PDAs. Defina "
                       "outro PDA como vigente antes.")
    with _transacao(dao):
        dao.excluir_plano(plano)


def obter_plano(db: Session, plano_id: int, user: UsuarioAtual | None = None) -> PlanoOut:
    dao = PdaDao.de(db, user)
    return _plano_out_db(dao, _plano_ou_404(dao, plano_id), user)


def _validar_plano(dao: PdaDao, nome: str | None, inicio: date | None, fim: date | None, *,
                   ignorar_id: int | None = None) -> str:
    """Nome obrigatório e único (espaços colapsados, sem diferenciar maiúsculas) e vigência
    coerente. Retorna o nome normalizado."""
    nome = re.sub(r"\s+", " ", nome or "").strip()
    if not nome:
        raise Invalido("Informe o nome do PDA.")
    if len(nome) > 200:
        raise Invalido("O nome do PDA deve ter no máximo 200 caracteres.")
    if inicio and fim and fim < inicio:
        raise Invalido("O fim da vigência não pode ser anterior ao início.")
    if _nome_em_uso(dao, nome, ignorar_id):
        raise Conflito(f'Já existe um PDA chamado "{nome}".')
    return nome


def criar_plano(db: Session, dados: PlanoIn, criado_por: str | None,
                user: UsuarioAtual | None = None) -> PlanoOut:
    """Cria um PDA vazio, sem planilha; as bases são incluídas depois, uma a uma (`criar_base`).
    O primeiro PDA cadastrado vira vigente mesmo sem `definir_vigente`."""
    dao = PdaDao.de(db, user)
    nome = _validar_plano(dao, dados.nome, dados.vigencia_inicio, dados.vigencia_fim)
    with _transacao(dao):
        primeiro_pda = dao.total_de_planos() == 0
        plano = PlanoPda(nome=nome, vigencia_inicio=dados.vigencia_inicio,
                         vigencia_fim=dados.vigencia_fim, vigente=False, arquivo_nome=None,
                         importado_por=_corte(criado_por, 200), importado_em=utcnow(),
                         total_bases=0)
        dao.save_generic(plano)
        if dados.definir_vigente or primeiro_pda:
            _tornar_unico_vigente(dao, plano)
    return plano_out(plano)


def atualizar_plano(db: Session, plano_id: int, dados: PlanoIn,
                    user: UsuarioAtual | None = None) -> PlanoOut:
    """Edita nome e vigência de um PDA (importado ou manual). Não troca o vigente: para isso,
    `definir_vigente`. As bases não são alteradas."""
    dao = PdaDao.de(db, user)
    plano = _plano_ou_404(dao, plano_id)
    nome = _validar_plano(dao, dados.nome, dados.vigencia_inicio, dados.vigencia_fim,
                          ignorar_id=plano.id)
    with _transacao(dao):
        plano.nome = nome
        plano.vigencia_inicio = dados.vigencia_inicio
        plano.vigencia_fim = dados.vigencia_fim
        dao.save_generic(plano)
    return _plano_out_db(dao, plano)


# ------------------------------------------------------------------ importação (PBI-12/13)
def _corte(valor: str | None, tamanho: int) -> str | None:
    return valor[:tamanho] if valor else valor


def _nome_em_uso(dao: PdaDao, nome: str, ignorar_id: int | None = None) -> bool:
    """Checagem prévia, só para a mensagem amigável; quem garante a unicidade sem diferenciar
    maiúsculas é o índice `uq_pda_plano_nome_ci` (lower(nome), só entre os PDAs não excluídos).
    `ignorar_id`: o próprio PDA, na edição. Nome de PDA excluído pode ser reaproveitado."""
    return nome.casefold() in {n.casefold() for n in dao.nomes_de_planos(ignorar_id)}


def _datasets_por_name(dao: PdaDao, names: set[str]) -> dict[str, Dataset]:
    """name → Dataset do inventário, usado SÓ para descobrir o ID (PBI-13). Se o inventário tiver
    mais de um dataset com o mesmo name (ex.: excluído e recriado), prefere o ativo no portal;
    persistindo a ambiguidade, não resolve."""
    encontrados: dict[str, list[Dataset]] = {}
    for ds in dao.datasets_por_name(names):
        encontrados.setdefault(ds.name, []).append(ds)
    resultado: dict[str, Dataset] = {}
    for name, candidatos in encontrados.items():
        ativos = [d for d in candidatos if d.ativo_no_portal] or candidatos
        if len(ativos) == 1:
            resultado[name] = ativos[0]
    return resultado


def importar_plano(db: Session, *, nome: str, vigencia_inicio: date | None,
                   vigencia_fim: date | None, definir_vigente: bool, arquivo_nome: str,
                   conteudo: bytes, importado_por: str | None,
                   user: UsuarioAtual | None = None,
                   mapeamento: regras.Mapeamento | None = None) -> ImportacaoResumoOut:
    """PBI-12/13 — importa a planilha de um PDA (atômico: qualquer erro → nada gravado).

    `mapeamento` = colunas escolhidas pelo usuário na etapa de mapeamento (`colunas_planilha`);
    sem ele, as colunas são achadas pelo cabeçalho.

    Vínculo: name extraído da URL "Disponível no Portal" → `Dataset.id` do inventário
    ("resolvido"); name sem dataset no inventário → "pendente" (resolver depois com
    `resolver_vinculos_pendentes`); sem URL → "sem_vinculo". Órgão da base: o do dataset
    vinculado; sem vínculo, o das bases da MESMA sigla vinculadas por ID neste PDA (se todas
    apontarem para uma só organização); por fim, `regras.casar_orgao`. O primeiro PDA cadastrado
    vira vigente mesmo sem `definir_vigente`. O arquivo bruto não é gravado.
    """
    dao = PdaDao.de(db, user)
    nome = _validar_plano(dao, nome, vigencia_inicio, vigencia_fim)
    try:
        lida = regras.ler_planilha(conteudo, arquivo_nome, mapeamento)
    except regras.PlanilhaInvalida as exc:
        raise Invalido(str(exc)) from exc
    if not lida.linhas:
        raise Invalido("Nenhuma base prevista encontrada na planilha (verifique se as colunas "
                       '"Órgão" e "Base de Dados" estão preenchidas).')

    with _transacao(dao):
        names = [regras.extrair_name_da_url(ln.disponivel_no_portal) for ln in lida.linhas]
        datasets = _datasets_por_name(dao, {n for n in names if n})
        vinculados = [datasets.get(n) if n else None for n in names]
        org_por_evidencia = regras.orgao_por_evidencia(
            (ln.orgao_sigla, ds.organizacao_id)
            for ln, ds in zip(lida.linhas, vinculados, strict=True) if ds is not None)
        orgaos = [(o.id, o.name, o.titulo, o.sigla) for o in dao.organizacoes()]
        orgao_por_sigla: dict[str, int | None] = {}
        sem_correspondencia: set[str] = set()
        resolvidos = pendentes = sem_vinculo = 0

        primeiro_pda = dao.total_de_planos() == 0
        plano = PlanoPda(nome=nome, vigencia_inicio=vigencia_inicio, vigencia_fim=vigencia_fim,
                         vigente=False, arquivo_nome=_corte(arquivo_nome, 300),
                         importado_por=_corte(importado_por, 200), importado_em=utcnow(),
                         total_bases=len(lida.linhas))
        for ln, name, ds in zip(lida.linhas, names, vinculados, strict=True):
            if ds is not None:
                resolvidos += 1
            elif name:
                pendentes += 1
            else:
                sem_vinculo += 1
            # 1) base vinculada: o órgão do dataset prevalece sobre a heurística pela sigla
            organizacao_id = ds.organizacao_id if ds is not None else None
            # 2) evidência por ID: outras bases da mesma sigla vinculadas a UMA organização
            if organizacao_id is None:
                organizacao_id = org_por_evidencia.get(regras.chave_sigla(ln.orgao_sigla))
            # 3) heurística pela sigla (nunca chuta)
            if organizacao_id is None:
                if ln.orgao_sigla not in orgao_por_sigla:
                    orgao_por_sigla[ln.orgao_sigla] = regras.casar_orgao(ln.orgao_sigla, orgaos)
                organizacao_id = orgao_por_sigla[ln.orgao_sigla]
            if organizacao_id is None:
                sem_correspondencia.add(ln.orgao_sigla)
            plano.bases.append(BasePrevista(
                orgao_sigla=_corte(ln.orgao_sigla, 100), organizacao_id=organizacao_id,
                nome_previsto=_corte(ln.nome_previsto, 500), descricao=ln.descricao,
                unidade_responsavel=_corte(ln.unidade_responsavel, 500),
                prazo_abertura=ln.prazo,
                periodicidade=regras.normalizar_periodicidade(ln.periodicidade_original),
                periodicidade_original=_corte(ln.periodicidade_original, 100),
                politicas_publicas=_corte(ln.politicas_publicas, 500),
                possui_conteudo_sigiloso=ln.possui_conteudo_sigiloso,
                dataset_id=ds.id if ds is not None else None,
                dataset_name_planilha=_corte(name, 200), linha_planilha=ln.linha,
                classificacao="pda"))

        dao.save_generic(plano, *plano.bases)
        if definir_vigente or primeiro_pda:
            _tornar_unico_vigente(dao, plano)

    return ImportacaoResumoOut(
        plano=plano_out(plano, _Contagens(len(lida.linhas), resolvidos, pendentes)),
        bases_importadas=len(lida.linhas),
        linhas_ignoradas=[LinhaIgnoradaOut(linha=n, motivo=m) for n, m in lida.ignoradas],
        vinculos_resolvidos=resolvidos, vinculos_pendentes=pendentes, sem_vinculo=sem_vinculo,
        orgaos_sem_correspondencia=sorted(sem_correspondencia, key=regras.normalizar_texto),
        tem_coluna_prazo=lida.tem_coluna_prazo,
        tem_coluna_portal=lida.tem_coluna_portal,
        colunas_opcionais_ausentes=lida.colunas_opcionais_ausentes)


def _evidencia_do_plano(dao: PdaDao, plano_id: int) -> dict[str, int]:
    """{chave_sigla: organização} das bases do plano vinculadas por ID (organização única)."""
    return regras.orgao_por_evidencia(
        (sigla, org) for sigla, org in dao.siglas_vinculadas(plano_id))


def _completar_orgao_por_evidencia(dao: PdaDao, plano_id: int) -> int:
    """Bases do plano SEM organização herdam a organização das bases da mesma sigla vinculadas
    por ID, quando todas apontam para uma só organização. Nunca sobrescreve organização já
    definida. Retorna quantas bases foram completadas."""
    mapa = _evidencia_do_plano(dao, plano_id)
    if not mapa:
        return 0
    completadas = []
    for base in dao.bases_sem_organizacao(plano_id):
        organizacao_id = mapa.get(regras.chave_sigla(base.orgao_sigla))
        if organizacao_id:
            base.organizacao_id = organizacao_id
            completadas.append(base)
    dao.save_generic(*completadas)
    return len(completadas)


def resolver_vinculos_pendentes(db: Session, plano_id: int, user: UsuarioAtual | None = None
                                ) -> dict[str, int]:
    """PBI-12/13 — tenta de novo SÓ as bases com `dataset_id` nulo e name da planilha (ex.: o
    dataset foi publicado depois da importação). Vínculo já resolvido nunca é recalculado pelo
    nome. Depois, as bases do plano sem organização herdam a organização das bases da mesma sigla
    vinculadas por ID (organização única). Retorna os vínculos resolvidos nesta execução e os que
    continuam pendentes."""
    dao = PdaDao.de(db, user)
    _plano_ou_404(dao, plano_id)
    pendentes = dao.bases_pendentes(plano_id)
    datasets = _datasets_por_name(dao, {b.dataset_name_planilha for b in pendentes})
    resolvidas = []
    for base in pendentes:
        ds = datasets.get(base.dataset_name_planilha)
        if ds is None:
            continue
        base.dataset_id = ds.id
        if ds.organizacao_id:
            base.organizacao_id = ds.organizacao_id
        resolvidas.append(base)
    with _transacao(dao):
        dao.save_generic(*resolvidas)
        _completar_orgao_por_evidencia(dao, plano_id)
    resolvidos = len(resolvidas)
    return {"vinculos_resolvidos": resolvidos, "vinculos_pendentes": len(pendentes) - resolvidos}


# ------------------------------------------------------------------ mapeamento de colunas
def colunas_planilha(conteudo: bytes, arquivo_nome: str) -> ColunasPlanilhaOut:
    """Etapa de mapeamento da importação: cabeçalho da planilha, campo do sistema com a coluna
    sugerida (nome igual ou muito parecido) e prévia das primeiras linhas. Nada é gravado; na
    confirmação o arquivo é enviado de novo com o `MapeamentoIn` (o servidor não guarda arquivo)."""
    try:
        lido = regras.ler_cabecalho(conteudo, arquivo_nome)
    except regras.PlanilhaInvalida as exc:
        raise Invalido(str(exc)) from exc
    return ColunasPlanilhaOut(
        aba=lido.aba, linha=lido.linha, colunas=lido.colunas, previa=lido.previa,
        campos=[CampoPlanilhaOut(campo=c, rotulo=r, obrigatorio=o, sugestao=lido.sugestao.get(c))
                for c, r, o in regras.CAMPOS_PDA])


# ------------------------------------------------------------------ IDs do CKAN em lote
def importar_ids_ckan(db: Session, plano_id: int, conteudo: bytes, arquivo_nome: str,
                      user: UsuarioAtual, *, aplicar: bool, sobrescrever: bool) -> IdsCkanOut:
    """Grava o ID do dataset (o vínculo — ADR-0006) nas bases do PDA a partir de um CSV com
    SIGLA, NOME_PDA, NOME_DATASET e ID_DATASET. Cada linha casa com UMA base pela SIGLA + nome da
    base (sem diferença de maiúsculas, acentos e espaços extras). O ID precisa ser um UUID e
    existir no inventário. `aplicar=False` só analisa; base que já tem OUTRO ID só é alterada com
    `sobrescrever=True`. Bases fora do escopo de órgão do usuário não são vistas."""
    dao = PdaDao.de(db, user)
    plano = _plano_ou_404(dao, plano_id)
    try:
        linhas = regras.ler_ids_ckan(conteudo, arquivo_nome)
    except regras.PlanilhaInvalida as exc:
        raise Invalido(str(exc)) from exc
    if not linhas:
        raise Invalido("Nenhuma linha de dados no arquivo de IDs.")

    por_chave: dict[tuple[str, str], list[BasePrevista]] = defaultdict(list)
    for b in dao.bases_do_plano(plano.id, user):
        por_chave[regras.chave_base(b.orgao_sigla, b.nome_previsto)].append(b)
    uuids = {u for u in (regras.normalizar_uuid(ln.id_informado) for ln in linhas) if u}
    datasets = {d.id_ckan: d for d in dao.datasets_por_id_ckan(uuids)}

    sem_base: list[LinhaIdCkanOut] = []
    invalidas: list[LinhaIdCkanOut] = []
    candidatas: list[tuple[LinhaIdCkanOut, BasePrevista]] = []
    sem_id = 0
    for ln in linhas:
        uuid = regras.normalizar_uuid(ln.id_informado)
        saida = LinhaIdCkanOut(linha=ln.linha, sigla=ln.sigla, nome_pda=ln.nome_pda,
                               dataset_id=uuid or ln.id_informado)
        if ln.id_informado is None:
            sem_id += 1
            continue
        achadas = por_chave.get(regras.chave_base(ln.sigla, ln.nome_pda), [])
        if not achadas:
            sem_base.append(saida.model_copy(update={"motivo": "Nenhuma base do PDA com essa "
                                                                "sigla e nome."}))
        elif len(achadas) > 1:
            sem_base.append(saida.model_copy(update={"motivo": f"{len(achadas)} bases do PDA com "
                                                                "essa sigla e nome."}))
        elif uuid is None:
            invalidas.append(saida.model_copy(update={"motivo": "ID não é um UUID válido."}))
        elif uuid not in datasets:
            invalidas.append(saida.model_copy(update={
                "motivo": "ID não encontrado no inventário do portal (rode a coleta)."}))
        elif user.restrito_a_orgao and datasets[uuid].organizacao_id != user.orgao_id:
            invalidas.append(saida.model_copy(update={"motivo": "Dataset de outro órgão."}))
        else:
            b = achadas[0]
            atual = b.dataset.id_ckan if b.dataset is not None else None
            candidatas.append((saida.model_copy(update={
                "base_id": b.id, "base_nome": b.nome_previsto, "id_atual": atual}), b))

    # Mesma base em mais de uma linha: com IDs diferentes, nenhuma é aplicada
    ids_por_base: dict[int, set[str]] = defaultdict(set)
    for saida, b in candidatas:
        ids_por_base[b.id].add(saida.dataset_id or "")
    atualizar: list[tuple[LinhaIdCkanOut, BasePrevista]] = []
    substituir: list[tuple[LinhaIdCkanOut, BasePrevista]] = []
    iguais = 0
    vistas: set[int] = set()
    for saida, b in candidatas:
        if len(ids_por_base[b.id]) > 1:
            invalidas.append(saida.model_copy(update={
                "motivo": "A mesma base aparece em outra linha com outro ID."}))
        elif b.id in vistas or b.dataset_id == datasets[saida.dataset_id or ""].id:
            iguais += 1
        elif b.dataset_id is None:
            atualizar.append((saida, b))
        else:
            substituir.append((saida, b))
        vistas.add(b.id)

    gravar = atualizar + (substituir if sobrescrever else [])
    if aplicar and gravar:
        for saida, b in gravar:
            ds = datasets[saida.dataset_id or ""]
            b.dataset_id = ds.id
            if ds.organizacao_id:  # o órgão do dataset vinculado prevalece (como no CRUD)
                b.organizacao_id = ds.organizacao_id
        with _transacao(dao):
            dao.save_generic(*(b for _, b in gravar))
            _completar_orgao_por_evidencia(dao, plano.id)
    return IdsCkanOut(
        aplicado=aplicar, total_linhas=len(linhas), atualizadas=len(gravar) if aplicar else 0,
        atualizar=[s for s, _ in atualizar], substituir=[s for s, _ in substituir], iguais=iguais,
        sem_id=sem_id, sem_base=sem_base, invalidas=sorted(invalidas, key=lambda s: s.linha))


# ------------------------------------------------------------------ situação (PBI-15/19/22)
@dataclass(frozen=True)
class BaseCalculada:
    """Base prevista com situação calculada sobre o inventário (mesmos campos de BaseOut)."""

    id: int
    plano_id: int
    plano_nome: str
    orgao_sigla: str
    orgao_chave: str
    orgao_nome: str | None
    nome_previsto: str
    descricao: str | None
    unidade_responsavel: str | None
    periodicidade: str
    periodicidade_original: str | None
    politicas_publicas: str | None
    possui_conteudo_sigiloso: bool | None
    prazo_abertura: date | None
    vinculo: str  # resolvido | pendente | sem_vinculo
    dataset_id: int | None
    dataset_id_ckan: str | None
    dataset_name: str | None
    dataset_titulo: str | None
    dataset_name_planilha: str | None
    dataset_ativo: bool | None
    data_publicacao: datetime | None  # metadata_created do dataset vinculado e ativo
    recursos_validos: int
    formatos: tuple[str, ...]  # formatos dos recursos válidos, sem repetição
    ultima_atualizacao: datetime | None
    ultima_atualizacao_estimada: bool
    situacao: str
    flag_prazo: str  # vencido | proximo | ""
    classificacao: str


def orgao_chave(organizacao_id: int | None, orgao_sigla: str) -> str:
    """Chave do filtro de órgão: `id` da organização (texto) ou 'sigla:<SIGLA>' sem
    correspondência."""
    if organizacao_id is not None:
        return str(organizacao_id)
    return "sigla:" + regras.chave_sigla(orgao_sigla)


def calcular_base(base: BasePrevista, plano_nome: str, hoje: date, janela_dias: int
                  ) -> BaseCalculada:
    ds = base.dataset if base.dataset_id else None
    # Só os recursos que ainda estão no pacote do dataset (recurso apagado do CKAN não conta)
    recursos = recursos_atuais(ds) if ds is not None else []
    validos = [r for r in recursos if not r.eh_dicionario_dados]  # dicionário nunca conta
    ultima = ultima_atualizacao_real(recursos)
    ativo = ds.ativo_no_portal if ds is not None else None
    return BaseCalculada(
        id=base.id, plano_id=base.plano_id, plano_nome=plano_nome, orgao_sigla=base.orgao_sigla,
        orgao_chave=orgao_chave(base.organizacao_id, base.orgao_sigla),
        orgao_nome=base.organizacao.titulo if base.organizacao is not None else None,
        nome_previsto=base.nome_previsto, descricao=base.descricao,
        unidade_responsavel=base.unidade_responsavel, periodicidade=base.periodicidade,
        periodicidade_original=base.periodicidade_original,
        politicas_publicas=base.politicas_publicas,
        possui_conteudo_sigiloso=base.possui_conteudo_sigiloso,
        prazo_abertura=base.prazo_abertura,
        vinculo=("resolvido" if base.dataset_id else
                 "pendente" if base.dataset_name_planilha else "sem_vinculo"),
        dataset_id=base.dataset_id,
        dataset_id_ckan=ds.id_ckan if ds is not None else None,
        dataset_name=ds.name if ds is not None else None,
        dataset_titulo=ds.titulo if ds is not None else None,
        dataset_name_planilha=base.dataset_name_planilha, dataset_ativo=ativo,
        data_publicacao=(_utc(ds.metadata_created)
                         if ds is not None and ativo and ds.metadata_created else None),
        recursos_validos=len(validos),
        formatos=tuple(sorted({r.formato for r in validos if r.formato})),
        ultima_atualizacao=ultima.data,
        ultima_atualizacao_estimada=ultima.estimada,
        situacao=regras.situacao_base(vinculada=ds is not None, dataset_ativo=ativo,
                                      recursos_validos=len(validos), prazo=base.prazo_abertura,
                                      hoje=hoje, janela_dias=janela_dias),
        flag_prazo=regras.flag_prazo(base.prazo_abertura, hoje, janela_dias),
        classificacao=base.classificacao,
    )


def _ordem(b: BaseCalculada):
    return regras.normalizar_texto(b.orgao_sigla), regras.normalizar_texto(b.nome_previsto), b.id


def bases_do_plano(db: Session, plano_id: int, user: UsuarioAtual | None = None, *,
                   hoje: date | None = None, janela_dias: int | None = None
                   ) -> list[BaseCalculada]:
    """PBI-19 — bases do PDA com situação calculada, ordenadas por órgão e nome. Para painel,
    relatórios e assistente. `user=None` = sem escopo de órgão (uso interno consolidado)."""
    dao = PdaDao.de(db, user)
    plano = _plano_ou_404(dao, plano_id)
    hoje = hoje or hoje_local()
    janela = janela_alerta_dias(db) if janela_dias is None else janela_dias
    bases = dao.bases_do_plano(plano.id, user)
    return sorted((calcular_base(b, plano.nome, hoje, janela) for b in bases), key=_ordem)


def _opcoes(bases: list[BaseCalculada]) -> OpcoesOut:
    orgaos: dict[str, str] = {}
    for b in bases:  # já ordenadas por sigla: a primeira sigla de cada órgão dá o rótulo
        orgaos.setdefault(b.orgao_chave,
                          b.orgao_sigla + (f" — {b.orgao_nome}" if b.orgao_nome else ""))
    presentes = {b.periodicidade for b in bases}
    return OpcoesOut(
        orgaos=sorted((OpcaoOut(valor=v, rotulo=r) for v, r in orgaos.items()),
                      key=lambda o: regras.normalizar_texto(o.rotulo)),
        periodicidades=[p for p in regras.DOMINIO_PERIODICIDADE if p in presentes]
        + sorted(presentes - set(regras.DOMINIO_PERIODICIDADE)),
        anos=sorted({b.prazo_abertura.year for b in bases if b.prazo_abertura}, reverse=True),
    )


def listar_bases(db: Session, user: UsuarioAtual, *, plano_id: int | None = None,
                 orgao: str | None = None, situacao: str | None = None,
                 periodicidade: str | None = None, ano: int | None = None,
                 prazo: str | None = None) -> BasesOut:
    """PBI-20/21 — tela Monitoramento do PDA. Sem `plano_id` usa o PDA vigente. Filtros:
    orgao = orgao_chave; situacao = rótulo; periodicidade = normalizada; ano = ano do prazo;
    prazo = 'vencido' | 'proximo' (janela do PBI-22)."""
    dao = PdaDao.de(db, user)
    hoje, janela = hoje_local(), janela_alerta_dias(db)
    plano = _plano_ou_404(dao, plano_id) if plano_id is not None else dao.plano_vigente()
    if plano is None:
        return BasesOut(plano=None, hoje=hoje, janela_alerta_dias=janela, total_previstas=0,
                        opcoes=OpcoesOut(orgaos=[], periodicidades=[], anos=[]), bases=[])
    todas = bases_do_plano(db, plano.id, user, hoje=hoje, janela_dias=janela)
    filtradas = [
        b for b in todas
        if (not orgao or b.orgao_chave == orgao)
        and (not situacao or b.situacao == situacao)
        and (not periodicidade or b.periodicidade == periodicidade)
        and (ano is None or (b.prazo_abertura is not None and b.prazo_abertura.year == ano))
        and (not prazo or b.flag_prazo == prazo)
    ]
    return BasesOut(plano=_plano_out_db(dao, plano, user), hoje=hoje, janela_alerta_dias=janela,
                    total_previstas=len(todas), opcoes=_opcoes(todas),
                    bases=[BaseOut.model_validate(b) for b in filtradas])


def bases_do_dataset(db: Session, dataset_id: int, user: UsuarioAtual | None = None
                     ) -> list[BaseCalculada]:
    """Bases previstas vinculadas (pelo ID) a um dataset do portal, em todos os PDAs: o vigente
    primeiro, depois os importados mais recentemente. Para a tela Datasets mostrar prazo,
    periodicidade e situação do PDA. Sem vínculo → lista vazia (nunca casa pelo nome)."""
    hoje, janela = hoje_local(), janela_alerta_dias(db)
    bases = PdaDao.de(db, user).bases_do_dataset(dataset_id, user)
    bases = sorted(bases, key=lambda b: (not b.plano.vigente, -b.plano.importado_em.timestamp(),
                                         b.id))
    return [calcular_base(b, b.plano.nome, hoje, janela) for b in bases]


def obter_base(db: Session, base_id: int, user: UsuarioAtual) -> BaseCalculada:
    """Detalhe de uma base (modal da tela). Base de outro órgão para usuário restrito → 404."""
    base = PdaDao.de(db, user).base_visivel(base_id, user)
    if base is None:
        raise NaoEncontrado("Base prevista não encontrada.")
    return calcular_base(base, base.plano.nome, hoje_local(), janela_alerta_dias(db))


# ------------------------------------------------------------------ cadastro manual das bases
def opcoes_formulario(db: Session, user: UsuarioAtual) -> FormularioOut:
    """Opções do formulário de base: organizações do portal visíveis ao usuário e o domínio de
    periodicidade."""
    orgs = PdaDao.de(db, user).organizacoes(user)
    opcoes = [OpcaoOut(valor=str(o.id), rotulo=(o.titulo or o.name).strip()
                       + (f" ({o.sigla})" if o.sigla else "")) for o in orgs]
    return FormularioOut(
        organizacoes=sorted(opcoes, key=lambda o: regras.normalizar_texto(o.rotulo)),
        periodicidades=list(regras.DOMINIO_PERIODICIDADE))


_LIMITE_BUSCA = 20


def buscar_datasets(db: Session, user: UsuarioAtual, busca: str | None) -> list[DatasetOpcaoOut]:
    """Busca do formulário de base: datasets do inventário pelo título, name, ID ou link do portal
    (ativos primeiro, no máximo 20), no escopo de órgão do usuário. O vínculo gravado é o ID."""
    texto = _limpo(busca)
    if texto is None or len(texto) < 2:
        return []
    name = regras.extrair_name_da_url(texto)
    condicao = (Dataset.name == name if name else
                Dataset.titulo.icontains(texto, autoescape=True)
                | Dataset.name.icontains(texto, autoescape=True)
                | (Dataset.id_ckan == texto))
    achados = PdaDao.de(db, user).buscar_datasets(condicao, user, _LIMITE_BUSCA)
    return [DatasetOpcaoOut(id=ds.id, id_ckan=ds.id_ckan, name=ds.name, titulo=ds.titulo,
                            organizacao_id=ds.organizacao_id, orgao_nome=orgao_nome,
                            ativo_no_portal=ds.ativo_no_portal)
            for ds, orgao_nome in achados]


def _limpo(valor: str | None) -> str | None:
    return (valor.strip() or None) if valor is not None else None


def _base_ou_404(dao: PdaDao, base_id: int) -> BasePrevista:
    base = dao.base(base_id)
    if base is None:
        raise NaoEncontrado("Base prevista não encontrada.")
    return base


def _vinculo_informado(dao: PdaDao, link: str | None, atual: BasePrevista | None
                       ) -> tuple[int | None, str | None]:
    """Endereço do dataset digitado → (dataset_id, dataset_name_planilha). O name serve só para
    achar o ID (PBI-13); name sem dataset no inventário → vínculo pendente. Na edição, endereço
    igual ao atual mantém o vínculo resolvido (nunca é recalculado pelo nome)."""
    texto = _limpo(link)
    if texto is None:
        return None, None
    name = regras.name_do_link(texto)
    if name is None:
        raise Invalido("Endereço do dataset não reconhecido: informe o link do portal "
                       "(https://dadosabertos.go.gov.br/dataset/<name>) ou o name do dataset.")
    if atual is not None and atual.dataset_id:
        nome_atual = atual.dataset.name if atual.dataset is not None else None
        if name in {atual.dataset_name_planilha, nome_atual}:
            return atual.dataset_id, atual.dataset_name_planilha or name
    ds = _datasets_por_name(dao, {name}).get(name)
    return (ds.id if ds is not None else None), name


def _vinculo_escolhido(dao: PdaDao, dataset_id: int, atual: BasePrevista | None
                       ) -> tuple[int, str]:
    """Dataset escolhido na busca → (dataset_id, dataset_name_planilha). Mesmo dataset da base
    mantém o name lido da planilha (auditoria); outro dataset grava o name atual dele."""
    ds = dao.dataset(dataset_id)
    if ds is None:
        raise Invalido("Dataset não encontrado no inventário do portal.")
    if atual is not None and atual.dataset_id == ds.id:
        return ds.id, atual.dataset_name_planilha or ds.name
    return ds.id, ds.name


def _vinculo_por_id_ckan(dao: PdaDao, id_ckan: str | None, link: str | None,
                         atual: BasePrevista | None) -> tuple[int | None, str | None]:
    """ID do dataset no CKAN digitado (ADR-0006) → (dataset_id, dataset_name_planilha). Tem
    prioridade sobre o endereço: precisa existir no inventário e, se o endereço também achar um
    dataset, os dois têm de ser o mesmo. Endereço sem dataset no inventário (nome do PDA diferente
    do name do portal) não impede: o name fica só para auditoria."""
    id_link, name = _vinculo_informado(dao, link, atual)
    ident = _limpo(id_ckan)
    if ident is None:
        return id_link, name
    ds = dao.dataset_por_id_ckan(ident)
    if ds is None:
        raise Invalido("ID do dataset não encontrado no inventário do portal: confira o ID ou "
                       "rode a coleta (Atualizar dados).")
    if id_link is not None and id_link != ds.id:
        raise Invalido("O ID e o endereço informados apontam para datasets diferentes: corrija um "
                       "deles ou deixe o endereço vazio.")
    return ds.id, name


def _orgao_informado(dao: PdaDao, plano_id: int, sigla: str, escolhido: int | None,
                     dataset_id: int | None) -> int | None:
    """Órgão da base cadastrada à mão: o do dataset vinculado; senão o escolhido no formulário;
    senão, como na importação, a evidência do vínculo por ID e `casar_orgao` (nunca chuta)."""
    if escolhido is not None and dao.organizacao(escolhido) is None:
        raise Invalido("Organização não encontrada no inventário do portal.")
    org_dataset = dao.organizacao_do_dataset(dataset_id) if dataset_id is not None else None
    if org_dataset:
        if escolhido is not None and escolhido != org_dataset:
            raise Invalido("O dataset informado pertence a outra organização do portal: ajuste o "
                           "órgão ou o endereço do dataset.")
        return org_dataset
    if escolhido is not None:
        return escolhido
    evidencia = _evidencia_do_plano(dao, plano_id).get(regras.chave_sigla(sigla))
    if evidencia:
        return evidencia
    orgaos = [(o.id, o.name, o.titulo, o.sigla) for o in dao.organizacoes()]
    return regras.casar_orgao(sigla, orgaos)


def _valores_da_base(dao: PdaDao, plano_id: int, dados: BaseIn,
                     atual: BasePrevista | None = None) -> dict[str, object]:
    """Valida o formulário e calcula os campos da base (nada é gravado aqui)."""
    sigla, nome = _limpo(dados.orgao_sigla), _limpo(dados.nome_previsto)
    if not sigla:
        raise Invalido("Informe o órgão (sigla).")
    if not nome:
        raise Invalido("Informe o nome da base prevista.")
    original = _limpo(dados.periodicidade)
    periodicidade = regras.periodicidade_informada(original)
    if atual is not None and periodicidade == atual.periodicidade:
        original = atual.periodicidade_original  # mantém o texto da planilha ("Mnsal")
    # Prioridade: dataset escolhido na busca > ID do CKAN digitado > endereço (só acha o ID)
    escolhido = dados.dataset_id
    dataset_id, name = (_vinculo_escolhido(dao, escolhido, atual) if escolhido is not None
                        else _vinculo_por_id_ckan(dao, dados.dataset_id_ckan, dados.dataset_link,
                                                  atual))
    return {
        "orgao_sigla": sigla,
        "organizacao_id": _orgao_informado(dao, plano_id, sigla, dados.organizacao_id,
                                           dataset_id),
        "nome_previsto": nome,
        "descricao": _limpo(dados.descricao),
        "unidade_responsavel": _limpo(dados.unidade_responsavel),
        "periodicidade": periodicidade,
        "periodicidade_original": original,
        "prazo_abertura": dados.prazo_abertura,
        "politicas_publicas": _limpo(dados.politicas_publicas),
        "possui_conteudo_sigiloso": dados.possui_conteudo_sigiloso,
        "dataset_id": dataset_id,
        "dataset_name_planilha": name,
    }


def criar_base(db: Session, plano_id: int, dados: BaseIn, user: UsuarioAtual) -> BaseCalculada:
    """Inclui uma base prevista no PDA (PDA criado à mão ou base que faltou na planilha)."""
    dao = PdaDao.de(db, user)
    plano = _plano_ou_404(dao, plano_id)
    valores = _valores_da_base(dao, plano.id, dados)
    exigir_mesmo_orgao(user, valores["organizacao_id"])
    with _transacao(dao):
        base = BasePrevista(plano_id=plano.id, linha_planilha=None, classificacao="pda", **valores)
        dao.save_generic(base)
        dao.atualizar_total(plano.id)
    dao.expirar()
    return obter_base(db, base.id, user)


def atualizar_base(db: Session, base_id: int, dados: BaseIn, user: UsuarioAtual
                   ) -> BaseCalculada:
    """Edita os dados de uma base prevista, inclusive o endereço do dataset (vínculo por ID)."""
    dao = PdaDao.de(db, user)
    base = _base_ou_404(dao, base_id)
    exigir_mesmo_orgao(user, base.organizacao_id)
    valores = _valores_da_base(dao, base.plano_id, dados, base)
    exigir_mesmo_orgao(user, valores["organizacao_id"])
    with _transacao(dao):
        for campo, valor in valores.items():
            setattr(base, campo, valor)
        dao.save_generic(base)
    dao.expirar()
    return obter_base(db, base.id, user)


def excluir_base(db: Session, base_id: int, user: UsuarioAtual) -> None:
    """Remove (exclusão lógica) uma base prevista do PDA (nada é alterado no CKAN)."""
    dao = PdaDao.de(db, user)
    base = _base_ou_404(dao, base_id)
    exigir_mesmo_orgao(user, base.organizacao_id)
    with _transacao(dao):
        dao.delete_generic(base)
        dao.atualizar_total(base.plano_id)
