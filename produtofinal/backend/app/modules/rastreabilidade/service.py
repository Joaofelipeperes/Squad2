"""Rastreabilidade (US14, US29) — linha do tempo de alterações no portal.

Fontes (ADR-0009):
- datasets, recursos e DataStore: a auditoria gravada no próprio CKAN pela extensão
  ckanext-dsaudit, lida pela API `dsaudit_activity_list` com um token de usuário EDITOR
  (`GDA_CKAN_AUDITORIA_API_TOKEN`); incremental, para na primeira atividade já conhecida;
- cadastro dos órgãos (a extensão não audita órgãos): comparação da fotografia de cada órgão
  entre coletas (`OrgaoSnapshot`).
A sincronização roda ao fim de cada coleta do inventário.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.integrations.ckan.client import CkanAcessoNegado, CkanClient, CkanError, CkanNaoEncontrado
from app.modules.inventario.models import Coleta, Dataset, DatasetSnapshot, Organizacao, Recurso
from app.modules.inventario.regras import chave_texto, contem_texto
from app.modules.rastreabilidade import regras
from app.modules.rastreabilidade.models import (
    EventoRastreabilidade,
    OrgaoSnapshot,
    SincronizacaoRastreabilidade,
)
from app.modules.rastreabilidade.schemas import (
    DetalheOut,
    DiffLinhaOut,
    DiffOut,
    EventoOut,
    EventosOpcoesOut,
    EventosOut,
    OpcaoOut,
    SincronizacaoOut,
)

log = logging.getLogger(__name__)

PAGINA_CKAN = 100        # atividades por chamada (a extensão aceita até 500)
LIMITE_PADRAO = 300      # eventos devolvidos à tela por consulta
LIMITE_MAXIMO = 2000

MSG_SEM_TOKEN = ("GDA_CKAN_AUDITORIA_API_TOKEN não configurado: defina o token de um usuário "
                 "editor do CKAN para ler a auditoria.")


# ------------------------------------------------------------------ sincronização
def sincronizar(client: CkanClient | None = None, orgaos: list[dict] | None = None) -> int:
    """Grava os eventos novos da linha do tempo. Abre a própria sessão; devolve o id da
    sincronização. Duas etapas independentes:

    1. Cadastro dos órgãos (se `orgaos` vier da coleta): compara com a última fotografia de cada
       órgão e gera evento quando algo mudou. Com o token, completa o evento com quem alterou e
       quando, lidos das atividades nativas do CKAN ("changed organization"); sem token, o evento
       fica sem autor.
    2. Auditoria do CKAN: para cada dataset do inventário (inclusive os que saíram do portal), lê
       `dsaudit_activity_list` e grava as atividades novas. Exige o token de editor.

    Falha de um dataset não interrompe os demais; falha geral fica registrada com status erro."""
    db = SessionLocal()
    sinc = SincronizacaoRastreabilidade()
    db.add(sinc)
    db.commit()
    token = get_settings().ckan_auditoria_api_token
    tem_token = bool(token and token.get_secret_value().strip())
    own_client = client is None and tem_token
    if own_client:
        client = CkanClient(api_token=token.get_secret_value().strip())
    usuarios: dict[str, str | None] = {}
    try:
        if orgaos:
            try:
                sinc.orgaos_consultados = len(orgaos)
                sinc.eventos_novos += _comparar_orgaos(db, orgaos, client, usuarios)
                db.commit()
            except Exception as exc:  # comparação de órgãos não impede a leitura da auditoria
                db.rollback()
                sinc = db.get(SincronizacaoRastreabilidade, sinc.id)
                sinc.erro = f"Cadastro dos órgãos não comparado: {type(exc).__name__}: {exc}"[:4000]
                log.exception("Comparação do cadastro dos órgãos falhou")
                db.commit()
        if client is None:
            sinc.status, sinc.erro = "ignorada", MSG_SEM_TOKEN
            log.info("Rastreabilidade: %s", MSG_SEM_TOKEN)
            return sinc.id
        _ler_auditoria(db, client, sinc, usuarios)
    except Exception as exc:  # registrar qualquer falha (mesmo padrão da coleta)
        db.rollback()
        sinc = db.get(SincronizacaoRastreabilidade, sinc.id)
        sinc.status, sinc.erro = "erro", f"{type(exc).__name__}: {exc}"[:4000]
        log.exception("Sincronização da rastreabilidade %s falhou", sinc.id)
    finally:
        sinc.finalizada_em = utcnow()
        db.commit()
        db.close()
        if own_client:
            client.close()
    return sinc.id


def _ler_auditoria(db: Session, client: CkanClient, sinc: SincronizacaoRastreabilidade,
                   usuarios: dict[str, str | None]) -> None:
    """Etapa 2: atividades novas da extensão de auditoria, dataset por dataset; depois, as
    atividades nativas sem registro da extensão (`_ler_atividades_nativas`)."""
    conhecidos = set(db.scalars(select(EventoRastreabilidade.ckan_activity_id)
                                .where(EventoRastreabilidade.ckan_activity_id.is_not(None))))
    datasets = db.execute(select(Dataset.ckan_id, Dataset.titulo, Dataset.organizacao_id)
                          .order_by(Dataset.ckan_id)).all()
    recursos = dict(db.execute(select(Recurso.ckan_id, Recurso.nome)).all())
    lidos = []  # datasets cuja auditoria foi lida (sem ela não há com o que parear as nativas)
    for ckan_id, titulo, org_id in datasets:
        try:
            novos = _atividades_novas(client, ckan_id, conhecidos)
        except CkanAcessoNegado:
            sinc.datasets_sem_permissao += 1
            continue
        except CkanNaoEncontrado:
            sinc.datasets_nao_encontrados += 1
            continue
        sinc.datasets_consultados += 1
        lidos.append((ckan_id, titulo, org_id))
        for act in novos:
            evs = _eventos(act, ckan_id, titulo, org_id,
                           _nome_usuario(client, act, usuarios), recursos)
            db.add_all(evs)
            sinc.eventos_novos += len(evs)
            if act.get("id"):
                conhecidos.add(act["id"])
        db.commit()
    if datasets and sinc.datasets_consultados == 0 and sinc.datasets_sem_permissao:
        sinc.status = "erro"
        sinc.erro = ("O token configurado não tem permissão de edição em nenhum dataset "
                     "(HTTP 403 em todos).")
        return
    sinc.eventos_novos += _ler_atividades_nativas(db, client, lidos, conhecidos, usuarios,
                                                  sinc.iniciada_em)
    sinc.atividades_nativas_ate = sinc.iniciada_em
    sinc.status = "ok"


MARGEM_NATIVAS_MIN = 10   # relê um pouco antes da última marca (atividades gravadas em paralelo)
MAX_PAGINAS_NATIVAS = 20


def _ler_atividades_nativas(db: Session, client: CkanClient, datasets: list, conhecidos: set[str],
                            usuarios: dict[str, str | None], inicio_sinc: datetime) -> int:
    """Ações fora da edição auditada (ex.: Make public/Make private/Delete em lote na página da
    organização): para cada dataset, lê as atividades nativas novas e grava como evento as que não
    têm atividade da extensão do mesmo dataset a menos de 2 s (as demais já estão na linha do
    tempo). Só considera atividades a partir do primeiro registro da extensão (antes dele não há
    com o que parear). Devolve quantos eventos foram gravados."""
    inicio_auditoria = db.scalar(select(func.min(EventoRastreabilidade.ocorrido_em))
                                 .where(EventoRastreabilidade.origem == regras.ORIGEM_AUDITORIA))
    if inicio_auditoria is None:
        return 0
    limite = _utc(inicio_auditoria)
    marca = db.scalar(select(func.max(SincronizacaoRastreabilidade.atividades_nativas_ate)))
    if marca is not None:
        limite = max(limite, _utc(marca) - timedelta(minutes=MARGEM_NATIVAS_MIN))
    novos = 0
    for ckan_id, titulo, org_id in datasets:
        try:
            nativas_lidas = _nativas_desde(client, ckan_id, limite)
        except (CkanAcessoNegado, CkanNaoEncontrado):
            continue
        fim = _utc(inicio_sinc)
        nativas = [a for a in nativas_lidas if a.get("id") not in conhecidos
                   and _no_intervalo(regras.parse_timestamp(a.get("timestamp")), limite, fim)]
        if not nativas:
            continue
        auditadas = [_utc(t) for t in db.scalars(
            select(EventoRastreabilidade.ocorrido_em).where(
                EventoRastreabilidade.dataset_id == ckan_id,
                EventoRastreabilidade.origem == regras.ORIGEM_AUDITORIA))]
        orfas = regras.nativas_orfas(nativas, auditadas)
        if not orfas:
            continue
        tempos = [regras.parse_timestamp(a["timestamp"]) for a in orfas]
        marcos = _marcos_visibilidade(db, ckan_id)
        privado_atual = _privado_atual(client, ckan_id)
        estimadas = regras.resolver_visibilidade(
            tempos, marcos, privado_atual, _base_visibilidade(db, ckan_id, tempos[0]))
        todas = sorted((a for a in nativas_lidas if regras.parse_timestamp(a.get("timestamp"))),
                       key=lambda a: regras.parse_timestamp(a["timestamp"]))
        versoes: dict[str, dict | None] = {}
        for act, quando, estimada in zip(orfas, tempos, estimadas, strict=True):
            eventos = _eventos_da_orfa(client, act, quando, estimada, todas, auditadas, marcos,
                                       versoes, privado_atual)
            titulo_ev = ((act.get("data") or {}).get("package") or {}).get("title") or titulo
            usuario = _nome_usuario(client, act, usuarios)
            for seq, c in enumerate(eventos):
                db.add(EventoRastreabilidade(
                    origem=regras.ORIGEM_NATIVA, ckan_activity_id=act["id"], sequencia=seq,
                    ocorrido_em=quando, tipo=c.tipo, activity_type=act["activity_type"],
                    dataset_id=ckan_id, dataset_titulo=titulo_ev[:500], organizacao_id=org_id,
                    usuario=usuario[:200] if usuario else None, recurso_id=c.recurso_id,
                    recurso_nome=c.recurso_nome, resumo=c.resumo, detalhes=c.detalhes,
                    tem_diff=False))
                novos += 1
            conhecidos.add(act["id"])
        db.commit()
    return novos


def _eventos_da_orfa(client: CkanClient, act: dict, quando: datetime,
                     estimada: tuple[bool | None, bool | None], todas: list[dict],
                     auditadas: list[datetime], marcos: list, versoes: dict[str, dict | None],
                     privado_atual: bool | None = None) -> list[regras.EventoClassificado]:
    """O que mudou numa atividade nativa sem par. O CKAN guarda a versão completa do dataset em
    cada atividade nativa (`activity_data_show`): comparando com a atividade nativa anterior,
    sabe-se exatamente o que mudou — desde que nenhuma edição auditada tenha ocorrido entre as
    duas (essa já está na linha do tempo e a diferença a misturaria). Sem a versão (sem acesso),
    usa a visibilidade estimada. Lista vazia = nada mudou (ex.: salvar sem alterar).

    Ação em lote (`regras.versao_anterior_a_acao`): a versão guardada é a de ANTES da ação; o
    estado depois dela é o de antes da atividade seguinte (`_privado_antes_de`) ou, sem
    seguinte, a visibilidade atual."""
    antes_est, depois_est = estimada
    if act["activity_type"] == "deleted package":  # a versão do lote ainda diz "active"
        return regras.classificar_orfa("deleted package", None, None)
    versao = _versao(client, act["id"], versoes)
    anterior = next((a for a in reversed(todas)
                     if regras.parse_timestamp(a["timestamp"]) < quando), None)
    if versao is None:
        return regras.classificar_orfa(act["activity_type"], antes_est, depois_est)
    if versao.get("state") == "deleted":
        return regras.classificar_orfa("deleted package", None, None)
    if regras.versao_anterior_a_acao(versao, quando):
        antes = bool(versao.get("private"))
        seguinte = next((a for a in todas
                         if regras.parse_timestamp(a["timestamp"]) > quando), None)
        depois = (_privado_antes_de(client, seguinte, marcos, versoes) if seguinte is not None
                  else privado_atual)
        if depois is None:
            depois = depois_est
        if antes == depois:
            return []  # ex.: Make private num dataset que já era privado
        return regras.classificar_orfa(act["activity_type"], antes, depois)
    depois = bool(versao.get("private"))
    if anterior is None:
        return regras.classificar_orfa(act["activity_type"], antes_est, depois)
    t_ant = regras.parse_timestamp(anterior["timestamp"])
    versao_ant = _versao(client, anterior["id"], versoes)
    if versao_ant is not None and regras.versao_anterior_a_acao(versao_ant, t_ant):
        # a anterior foi ação em lote: sua versão é de antes dela; a visibilidade que ela deixou
        # é a de antes desta atividade (já atribuída ao lote, não a esta)
        versao_ant = {**versao_ant, "private": versao.get("private")}
    auditada_no_meio = any(t_ant < t < quando for t in auditadas)
    if versao_ant is not None and not auditada_no_meio:
        mudancas = regras.mudancas_pacote(versao_ant, versao)
        if not mudancas:
            return []
        return regras.classificar_orfa(act["activity_type"], None, None, mudancas)
    # houve edição auditada entre as duas versões: só a visibilidade é atribuída a esta ação
    marco = max((m for m in marcos if m[0] < quando), key=lambda m: m[0], default=None)
    if marco is not None and (versao_ant is None or marco[0] > t_ant):
        antes = marco[2]
    elif versao_ant is not None:
        antes = bool(versao_ant.get("private"))
    else:
        antes = antes_est
    if antes == depois:
        return []  # visibilidade igual e o resto já está nas edições auditadas
    return regras.classificar_orfa(act["activity_type"], antes, depois)


def _privado_antes_de(client: CkanClient, act: dict, marcos: list,
                      versoes: dict[str, dict | None]) -> bool | None:
    """Visibilidade imediatamente antes da atividade nativa `act` (None = desconhecida).

    - ação em lote ou exclusão: a versão guardada já é a de antes;
    - edição auditada que mudou a visibilidade (marco a menos de 2 s): o valor anterior do marco;
    - demais (edição sem mudança de visibilidade): a visibilidade da própria versão."""
    versao = _versao(client, act["id"], versoes)
    if versao is None:
        return None
    quando = regras.parse_timestamp(act["timestamp"])
    if act.get("activity_type") == "deleted package" or regras.versao_anterior_a_acao(versao,
                                                                                       quando):
        return bool(versao.get("private"))
    marco = next((m for m in marcos
                  if abs((m[0] - quando).total_seconds()) < regras.JANELA_PAR_SEGUNDOS), None)
    if marco is not None:
        return marco[1] if marco[1] is not None else not marco[2]
    return bool(versao.get("private"))


def _versao(client: CkanClient, activity_id: str, cache: dict[str, dict | None]) -> dict | None:
    if activity_id not in cache:
        try:
            cache[activity_id] = client.dados_atividade(activity_id)
        except CkanError:
            cache[activity_id] = None
    return cache[activity_id]


def _no_intervalo(quando: datetime | None, desde: datetime, ate: datetime) -> bool:
    return quando is not None and desde < quando <= ate


def _nativas_desde(client: CkanClient, dataset_id: str, limite: datetime) -> list[dict]:
    """Atividades nativas do dataset, da mais recente até passar de `limite`."""
    atividades: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGINAS_NATIVAS):
        pagina = client.atividades_dataset(dataset_id, limit=PAGINA_CKAN, offset=offset)
        atividades.extend(pagina)
        mais_antiga = regras.parse_timestamp(pagina[-1].get("timestamp")) if pagina else None
        if len(pagina) < PAGINA_CKAN or (mais_antiga is not None and mais_antiga <= limite):
            break
        offset += len(pagina)
    return atividades


def _marcos_visibilidade(db: Session, dataset_id: str) -> list[tuple[datetime, bool | None, bool]]:
    """Mudanças de visibilidade já conhecidas do dataset: (data, privado antes, privado depois)."""
    marcos = []
    for quando, detalhes in db.execute(
            select(EventoRastreabilidade.ocorrido_em, EventoRastreabilidade.detalhes).where(
                EventoRastreabilidade.dataset_id == dataset_id)):
        for d in detalhes or []:
            if d.get("escopo") == "dataset" and d.get("campo") == "visibilidade":
                depois = regras.visibilidade(d.get("novo"))
                if depois is not None:
                    marcos.append((_utc(quando), regras.visibilidade(d.get("anterior")), depois))
    return marcos


def _privado_atual(client: CkanClient, dataset_id: str) -> bool | None:
    try:
        return bool(client.dataset(dataset_id).get("private"))
    except CkanError:
        return None


def _base_visibilidade(db: Session, dataset_id: str, antes_de: datetime) -> bool | None:
    """False (público) se o dataset estava na busca pública da última coleta concluída antes de
    `antes_de`; sem essa evidência, desconhecido (None)."""
    coleta = db.scalar(select(Coleta.id).where(Coleta.status == "ok",
                                               Coleta.finalizada_em <= antes_de)
                       .order_by(Coleta.finalizada_em.desc()).limit(1))
    if coleta is None:
        return None
    existe = db.scalar(select(func.count()).select_from(DatasetSnapshot).where(
        DatasetSnapshot.coleta_id == coleta, DatasetSnapshot.dataset_id == dataset_id))
    return False if existe else None


def _comparar_orgaos(db: Session, orgaos: list[dict], client: CkanClient | None = None,
                     usuarios: dict[str, str | None] | None = None) -> int:
    """Compara o cadastro de cada órgão com a última fotografia dele e grava uma fotografia nova
    só quando mudou (ou quando o órgão sumiu da listagem). Na primeira vez (sem fotografias),
    apenas registra a base, sem gerar eventos. Com `client`, completa cada evento com a autoria
    (`_autoria_orgao`). Devolve quantos eventos foram gravados."""
    ultimos_ids = select(func.max(OrgaoSnapshot.id)).group_by(OrgaoSnapshot.organizacao_id)
    ultimos = {s.organizacao_id: s for s in
               db.scalars(select(OrgaoSnapshot).where(OrgaoSnapshot.id.in_(ultimos_ids)))}
    tem_base = bool(ultimos)
    agora = utcnow()
    usuarios = {} if usuarios is None else usuarios
    novos = 0
    vistos: set[str] = set()
    pendentes: list[tuple[OrgaoSnapshot, OrgaoSnapshot | None, regras.EventoClassificado]] = []
    for org in orgaos:
        oid = org.get("id")
        if not oid:
            continue
        vistos.add(oid)
        payload = regras.payload_orgao(org)
        hash_atual = regras.hash_payload(payload)
        anterior = ultimos.get(oid)
        if anterior is not None and anterior.ativo and anterior.hash_conteudo == hash_atual:
            continue
        snap = OrgaoSnapshot(organizacao_id=oid, capturado_em=agora, ativo=True,
                             hash_conteudo=hash_atual, payload=payload)
        db.add(snap)
        db.flush()
        if not tem_base:
            continue
        antes = anterior.payload if anterior is not None and anterior.ativo else None
        c = regras.comparar_orgao(antes, payload)
        if c is not None:
            pendentes.append((snap, anterior, c))
    for oid, anterior in ultimos.items():
        if oid in vistos or not anterior.ativo:
            continue
        snap = OrgaoSnapshot(organizacao_id=oid, capturado_em=agora, ativo=False,
                             hash_conteudo=anterior.hash_conteudo, payload=anterior.payload)
        db.add(snap)
        db.flush()
        c = regras.comparar_orgao(anterior.payload, None)
        if c is not None:
            pendentes.append((snap, anterior, c))
    for snap, anterior, c in pendentes:
        autoria = []
        if client is not None:
            desde = _utc(anterior.capturado_em) if anterior is not None else None
            autoria = _autoria_orgao(client, snap.organizacao_id, desde, agora, usuarios)
        db.add(_evento_orgao(snap, c, autoria))
        novos += 1
    return novos


MAX_PAGINAS_ORGAO = 10  # organization_activity_list também traz as atividades dos datasets


def _autoria_orgao(client: CkanClient, org_id: str, desde: datetime | None, ate: datetime,
                   usuarios: dict[str, str | None]) -> list[tuple[datetime, str]]:
    """Quem alterou o órgão e quando, entre a fotografia anterior e a atual, pelas atividades
    nativas do CKAN. Lista vazia se o CKAN não permitir ler (o evento fica sem autor)."""
    atividades: list[dict] = []
    offset = 0
    try:
        for _ in range(MAX_PAGINAS_ORGAO):
            pagina = client.atividades_orgao(org_id, limit=PAGINA_CKAN, offset=offset)
            atividades.extend(pagina)
            mais_antiga = regras.parse_timestamp(pagina[-1].get("timestamp")) if pagina else None
            if len(pagina) < PAGINA_CKAN or desde is None or (mais_antiga and mais_antiga <= desde):
                break
            offset += len(pagina)
    except CkanError:
        log.warning("Atividades do órgão %s não puderam ser lidas no CKAN", org_id)
        return []
    return [(quando, _nome_usuario(client, {"user_id": uid}, usuarios) or uid)
            for quando, uid in regras.autoria_no_intervalo(atividades, desde, ate)]


def _evento_orgao(snap: OrgaoSnapshot, c: regras.EventoClassificado,
                  autoria: list[tuple[datetime, str]] | None = None) -> EventoRastreabilidade:
    """Evento do cadastro do órgão. Com autoria (atividades nativas do CKAN): usuários que
    alteraram o órgão no intervalo e a data da alteração mais recente. Sem autoria: usuário vazio
    e a data em que a diferença foi detectada (fim da coleta)."""
    detalhes = list(c.detalhes)
    usuario = None
    ocorrido_em = snap.capturado_em
    if autoria:
        nomes = list(dict.fromkeys(nome for _, nome in autoria))
        usuario = ", ".join(nomes)[:200]
        ocorrido_em = autoria[-1][0]
        detalhes.append({"escopo": "orgao", "recurso": None, "situacao": None,
                         "campo": "alterações registradas no CKAN no período",
                         "anterior": None,
                         "novo": regras.texto_autoria(autoria)})
    return EventoRastreabilidade(
        origem=regras.ORIGEM_COMPARACAO, orgao_snapshot_id=snap.id, ckan_activity_id=None,
        sequencia=0, ocorrido_em=ocorrido_em, tipo=c.tipo, activity_type="organization",
        dataset_id=None, dataset_titulo=None, organizacao_id=snap.organizacao_id,
        usuario=usuario, resumo=c.resumo, detalhes=detalhes, tem_diff=False)


def _atividades_novas(client: CkanClient, dataset_id: str, conhecidos: set[str]) -> list[dict]:
    """Atividades ainda não gravadas, da mais recente para a mais antiga. A API devolve em ordem
    decrescente de data: a primeira já conhecida encerra a leitura do dataset."""
    novas: list[dict] = []
    offset = 0
    while True:
        pagina = client.auditoria_dataset(dataset_id, limit=PAGINA_CKAN, offset=offset)
        resultados = pagina.get("results") or []
        for act in resultados:
            if act.get("id") in conhecidos:
                return novas
            novas.append(act)
        offset += len(resultados)
        if not resultados or offset >= int(pagina.get("count") or 0):
            return novas


def _nome_usuario(client: CkanClient, act: dict, cache: dict[str, str | None]) -> str | None:
    uid = act.get("user_id")
    if not uid:
        return None
    if uid not in cache:
        try:
            u = client.usuario(uid)
            cache[uid] = u.get("name") or u.get("fullname") or uid
        except CkanError:
            cache[uid] = uid
    return cache[uid]


def _eventos(act: dict, dataset_id: str, titulo_atual: str, org_id: str | None,
             usuario: str | None, recursos: dict[str, str | None]) -> list[EventoRastreabilidade]:
    """Uma atividade → um ou mais eventos (ex.: Privação + Alteração), com `sequencia` 0, 1..."""
    data = act.get("data") or {}
    quando = regras.parse_timestamp(act.get("timestamp"))
    if quando is None or not act.get("id"):
        return []
    eventos = []
    for seq, c in enumerate(regras.classificar(act.get("activity_type") or "", data)):
        recurso_nome = c.recurso_nome
        if c.recurso_id and not recurso_nome:
            recurso_nome = _nome_recurso(data, c.recurso_id) or recursos.get(c.recurso_id)
        eventos.append(EventoRastreabilidade(
            ckan_activity_id=act["id"], sequencia=seq, ocorrido_em=quando, tipo=c.tipo,
            activity_type=act.get("activity_type") or "", dataset_id=dataset_id,
            dataset_titulo=(regras.titulo_do_pacote(data) or titulo_atual)[:500],
            organizacao_id=org_id, recurso_id=c.recurso_id,
            recurso_nome=recurso_nome[:500] if recurso_nome else None,
            usuario=usuario[:200] if usuario else None, resumo=c.resumo, detalhes=c.detalhes,
            tem_diff=c.tem_diff))
    return eventos


def _nome_recurso(data: dict, recurso_id: str) -> str | None:
    versao = data.get("version") or {}
    return versao.get("filename") if data.get("resource_id") == recurso_id else None


# ------------------------------------------------------------------ tela (PBI-85)
def _utc(valor: datetime | None) -> datetime | None:
    return valor.replace(tzinfo=UTC) if valor is not None and valor.tzinfo is None else valor


def ultima_sincronizacao(db: Session) -> SincronizacaoRastreabilidade | None:
    return db.scalar(select(SincronizacaoRastreabilidade)
                     .order_by(SincronizacaoRastreabilidade.id.desc()).limit(1))


def listar_eventos(db: Session, user: UsuarioAtual, *, tipo: str | None = None,
                   orgao: str | None = None, dataset: str | None = None,
                   busca: str | None = None, desde: datetime | None = None,
                   ate: datetime | None = None, ordem: str = "recentes",
                   limite: int = LIMITE_PADRAO) -> EventosOut:
    """Linha do tempo no escopo de órgão do usuário. Filtros: tipo (código), órgão (ID da
    organização), dataset (ID do CKAN), busca (título ou nome do dataset, sem diferenciar acento
    nem maiúscula), período (desde/até, inclusive) e ordem por data (recentes | antigos)."""
    limite = max(1, min(limite, LIMITE_MAXIMO))
    base = filtrar_por_orgao(select(EventoRastreabilidade),
                             EventoRastreabilidade.organizacao_id, user)
    orgaos = {o.ckan_id: o.titulo.strip() for o in db.scalars(select(Organizacao))}
    presentes = {o for o in db.scalars(
        filtrar_por_orgao(select(EventoRastreabilidade.organizacao_id).distinct(),
                          EventoRastreabilidade.organizacao_id, user)) if o}

    stmt = base
    if tipo:
        stmt = stmt.where(EventoRastreabilidade.tipo == tipo)
    if orgao:
        stmt = stmt.where(EventoRastreabilidade.organizacao_id == orgao)
    if dataset:
        stmt = stmt.where(EventoRastreabilidade.dataset_id == dataset)
    if busca:
        stmt = stmt.where(_condicao_busca(db, busca))
    if desde:
        stmt = stmt.where(EventoRastreabilidade.ocorrido_em >= desde)
    if ate:
        stmt = stmt.where(EventoRastreabilidade.ocorrido_em <= ate)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if ordem == "antigos":
        ordenacao = (EventoRastreabilidade.ocorrido_em.asc(), EventoRastreabilidade.id.asc())
    else:
        ordenacao = (EventoRastreabilidade.ocorrido_em.desc(), EventoRastreabilidade.id.desc())
    linhas = db.scalars(stmt.order_by(*ordenacao).limit(limite)).all()
    sinc = ultima_sincronizacao(db)
    return EventosOut(
        total=total, exibidos=len(linhas),
        opcoes=EventosOpcoesOut(
            tipos=[OpcaoOut(valor=k, rotulo=v) for k, v in regras.TIPOS.items()],
            orgaos=sorted((OpcaoOut(valor=i, rotulo=orgaos[i]) for i in presentes if i in orgaos),
                          key=lambda o: chave_texto(o.rotulo))),
        sincronizacao=SincronizacaoOut.model_validate(sinc) if sinc else None,
        eventos=[_saida(e, orgaos) for e in linhas])


def _condicao_busca(db: Session, busca: str):
    """Dataset cujo título ou nome atual (inventário) contém o texto, sem acento — ou cujo
    título na data do evento contém o texto, ou cujo ID é o texto. Para eventos do cadastro do
    órgão, o título ou nome do órgão."""
    ids = [ckan_id for ckan_id, titulo, name in
           db.execute(select(Dataset.ckan_id, Dataset.titulo, Dataset.name))
           if contem_texto(busca, titulo, name)]
    orgaos = [ckan_id for ckan_id, titulo, name in
              db.execute(select(Organizacao.ckan_id, Organizacao.titulo, Organizacao.name))
              if contem_texto(busca, titulo, name)]
    return or_(EventoRastreabilidade.dataset_id.in_(ids),
               EventoRastreabilidade.dataset_id == busca.strip(),
               EventoRastreabilidade.dataset_titulo.icontains(busca.strip(), autoescape=True),
               (EventoRastreabilidade.origem == regras.ORIGEM_COMPARACAO)
               & EventoRastreabilidade.organizacao_id.in_(orgaos))


def _saida(e: EventoRastreabilidade, orgaos: dict[str, str]) -> EventoOut:
    return EventoOut(
        id=e.id, origem=e.origem, ocorrido_em=_utc(e.ocorrido_em), tipo=e.tipo,
        tipo_rotulo=regras.TIPOS.get(e.tipo, e.tipo), dataset_id=e.dataset_id,
        dataset_titulo=e.dataset_titulo, organizacao_id=e.organizacao_id,
        orgao_nome=orgaos.get(e.organizacao_id or ""), recurso_id=e.recurso_id,
        recurso_nome=e.recurso_nome, usuario=e.usuario, resumo=e.resumo,
        detalhes=[DetalheOut(**d) for d in e.detalhes or []], tem_diff=e.tem_diff)


# ------------------------------------------------------------------ diff sob demanda
class EventoNaoEncontrado(LookupError):
    pass


class DiffIndisponivel(RuntimeError):
    pass


MAX_PAGINAS_DIFF = 20


def diff_evento(db: Session, user: UsuarioAtual, evento_id: int,
                client: CkanClient | None = None) -> DiffOut:
    """Diff linha a linha de uma troca de arquivo ou de um upsert no DataStore, lido do CKAN
    na hora (a auditoria fica lá; aqui nada é gravado, pois os valores podem conter dado
    pessoal). Evento de outro órgão para usuário restrito → não encontrado."""
    stmt = filtrar_por_orgao(select(EventoRastreabilidade),
                             EventoRastreabilidade.organizacao_id, user)
    ev = db.scalar(stmt.where(EventoRastreabilidade.id == evento_id))
    if ev is None:
        raise EventoNaoEncontrado("Evento não encontrado.")
    if not ev.tem_diff:
        raise DiffIndisponivel("Este evento não tem comparação linha a linha.")
    token = get_settings().ckan_auditoria_api_token
    if client is None and not (token and token.get_secret_value().strip()):
        raise DiffIndisponivel(MSG_SEM_TOKEN)
    own_client = client is None
    client = client or CkanClient(api_token=token.get_secret_value().strip())
    try:
        act = _buscar_atividade(client, ev)
    except CkanError as exc:
        raise DiffIndisponivel(f"Não foi possível ler a auditoria no CKAN: {exc}") from exc
    finally:
        if own_client:
            client.close()
    if act is None:
        raise DiffIndisponivel("A atividade não foi encontrada na auditoria do CKAN.")
    data = act.get("data") or {}
    linhas, total = regras.linhas_do_diff(data.get("changes"))
    versao, anterior = data.get("version") or {}, data.get("previous_version") or {}
    return DiffOut(
        evento_id=ev.id, recurso_nome=ev.recurso_nome,
        arquivo_anterior=anterior.get("filename"), arquivo_novo=versao.get("filename"),
        versao_anterior=anterior.get("version"), versao_nova=versao.get("version"),
        colunas_chave=[str(k) for k in data.get("keys") or []],
        total_linhas=total, linhas=[DiffLinhaOut(**linha) for linha in linhas])


def _buscar_atividade(client: CkanClient, ev: EventoRastreabilidade) -> dict | None:
    offset = 0
    for _ in range(MAX_PAGINAS_DIFF):
        pagina = client.auditoria_dataset(ev.dataset_id, limit=PAGINA_CKAN, offset=offset,
                                          resource_id=ev.recurso_id,
                                          activity_type=ev.activity_type)
        resultados = pagina.get("results") or []
        for act in resultados:
            if act.get("id") == ev.ckan_activity_id:
                return act
        offset += len(resultados)
        if not resultados or offset >= int(pagina.get("count") or 0):
            return None
    return None


# ------------------------------------------------------------------ contrato futuro (opção C)
def diff_coletas(db, coleta_anterior_id: int, coleta_atual_id: int):
    """PBI-43 — compara dataset_snapshot de duas coletas e gera eventos:
    inclusão, alteração, privação/exclusão (dataset some), recurso atualizado.
    Complemento previsto na ADR-0009 para portais sem a extensão de auditoria."""
    raise NotImplementedError
