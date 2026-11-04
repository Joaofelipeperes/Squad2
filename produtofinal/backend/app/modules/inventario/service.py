"""Coleta do inventário CKAN → banco local (PBI-07 a PBI-11, PBI-71).

Implementação de referência da base comum: percorre organizações e datasets pela API pública,
faz upsert do estado atual e grava uma fotografia por dataset para o diff da rastreabilidade.
"""
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual
from app.integrations.ckan.client import CkanClient
from app.modules.atualizacoes.regras import ultima_atualizacao_real
from app.modules.inventario import regras
from app.modules.inventario.dao import InventarioDao
from app.modules.inventario.models import Coleta, Dataset, DatasetSnapshot, Organizacao, Recurso
from app.modules.inventario.schemas import (
    DatasetDetalheOut,
    DatasetOut,
    DatasetsOpcoesOut,
    DatasetsOut,
    OpcaoOut,
    RecursoOut,
)

log = logging.getLogger(__name__)


class ColetaEmAndamento(RuntimeError):
    pass


def recursos_atuais(ds: Dataset) -> list[Recurso]:
    """Recursos do dataset que vieram no pacote da última coleta dele (ver `regras.recurso_atual`).
    Recurso apagado do CKAN fica no banco, mas não conta para publicação nem atualização."""
    return [r for r in ds.recursos if regras.recurso_atual(r, ds)]


def condicao_recurso_atual():
    """Mesma regra de `recursos_atuais` para consultas SQL (exige o join Recurso × Dataset)."""
    return Recurso.ultima_coleta_id.is_not_distinct_from(Dataset.ultima_coleta_id)


def coleta_em_andamento(db: Session) -> Coleta | None:
    return InventarioDao(db).coleta_em_andamento()


def ultima_coleta(db: Session) -> Coleta | None:
    return InventarioDao(db).ultima_coleta()


def historico_coletas(db: Session, limite: int = 30) -> list[Coleta]:
    return InventarioDao(db).historico_coletas(limite)


def iniciar(db: Session, origem: str, solicitante: str | None = None,
            usuario_id: int | None = None) -> Coleta:
    """Registra a coleta. `usuario_id` = quem pediu a coleta manual (vai para `created_id`)."""
    dao = InventarioDao(db, usuario_id)
    if dao.coleta_em_andamento():
        raise ColetaEmAndamento("Já existe uma coleta em execução.")
    return dao.criar_coleta(origem, solicitante)


def executar(coleta_id: int, client: CkanClient | None = None) -> None:
    """Roda a coleta completa (ação do sistema: auditoria sem usuário). Abre a própria sessão
    (é chamado em background ou pelo worker)."""
    db = SessionLocal()
    dao = InventarioDao(db)
    own_client = client is None
    client = client or CkanClient()
    coleta = dao.obter_coleta(coleta_id)
    orgs: list[dict] = []
    try:
        orgs = client.organizations()
        existentes = dao.organizacoes_por_id_ckan()
        for o in orgs:
            org = existentes.get(o["id"]) or Organizacao(id_ckan=o["id"])
            org.name, org.titulo = o["name"], o.get("title") or o["name"]
            org.ultima_coleta_id = coleta_id
            dao.save_generic(org)  # grava antes dos datasets: eles precisam do `id` do órgão
            existentes[o["id"]] = org
        org_por_id_ckan = {id_ckan: o.id for id_ckan, o in existentes.items()}
        n_ds = n_res = 0
        vistos: set[str] = set()
        for pkg in client.iter_datasets():
            _upsert_dataset(dao, pkg, coleta_id, org_por_id_ckan)
            vistos.add(pkg["id"])
            n_ds += 1
            n_res += len(pkg.get("resources", []))
            if n_ds % 100 == 0:
                dao.commit()
        if vistos:
            dao.marcar_fora_do_portal(vistos)
        coleta.total_organizacoes, coleta.total_datasets, coleta.total_recursos = (
            len(orgs), n_ds, n_res)
        coleta.status = "ok"
    except Exception as exc:  # noqa: BLE001 — registrar qualquer falha na coleta (PBI-10)
        dao.rollback()
        coleta = dao.obter_coleta(coleta_id)
        coleta.status, coleta.erro = "erro", f"{type(exc).__name__}: {exc}"[:4000]
        log.exception("Coleta %s falhou", coleta_id)
    finally:
        coleta.finalizada_em = utcnow()
        dao.save_generic(coleta)
        dao.commit()
        concluida = coleta.status == "ok"
        db.close()
        if own_client:
            client.close()
    if concluida:
        _sincronizar_rastreabilidade(orgs)


def _sincronizar_rastreabilidade(orgs: list[dict]) -> None:
    """Depois de cada coleta concluída, lê a auditoria do CKAN e compara o cadastro dos órgãos
    recém-coletados (módulo rastreabilidade, ADR-0009). Falha ali não altera o resultado da
    coleta: fica na própria sincronização."""
    from app.modules.rastreabilidade.service import sincronizar  # import tardio evita ciclo
    try:
        sincronizar(orgaos=orgs)
    except Exception:
        log.exception("Sincronização da rastreabilidade após a coleta falhou")


def _upsert_dataset(dao: InventarioDao, pkg: dict, coleta_id: int,
                    org_por_id_ckan: dict[str, int]) -> None:
    """Upsert do dataset e dos recursos casando pelo `id_ckan` entre os registros ativos (a chave
    primária é nossa)."""
    extras = regras.extras_como_dict(pkg.get("extras"))
    ds = dao.dataset_por_id_ckan(pkg["id"]) or Dataset(id_ckan=pkg["id"])
    ds.name, ds.titulo = pkg["name"], pkg.get("title") or pkg["name"]
    ds.descricao = (pkg.get("notes") or "").strip() or None
    ds.organizacao_id = org_por_id_ckan.get((pkg.get("organization") or {}).get("id"))
    ds.autor, ds.autor_email = pkg.get("author"), pkg.get("author_email")
    ds.licenca = pkg.get("license_id")
    ds.periodicidade_declarada = regras.periodicidade_declarada(extras, pkg)
    ds.metadata_created = regras.parse_ckan_datetime(pkg.get("metadata_created"))
    ds.metadata_modified = regras.parse_ckan_datetime(pkg.get("metadata_modified"))
    ds.extras, ds.ativo_no_portal, ds.ultima_coleta_id = extras, True, coleta_id
    dao.save_generic(ds)  # garante ds.id para os recursos e a fotografia
    pacote = pkg.get("resources", [])
    existentes = dao.recursos_por_id_ckan([r["id"] for r in pacote])
    for r in pacote:
        rec = existentes.get(r["id"]) or Recurso(id_ckan=r["id"])
        rec.dataset_id, rec.nome = ds.id, r.get("name")
        rec.formato = (r.get("format") or "").upper() or None
        rec.url, rec.url_type = r.get("url"), r.get("url_type") or None
        rec.created_ckan = regras.parse_ckan_datetime(r.get("created"))
        rec.last_modified = regras.parse_ckan_datetime(r.get("last_modified"))
        rec.datastore_active = bool(r.get("datastore_active"))
        rec.eh_dicionario_dados = regras.eh_dicionario_de_dados(r.get("name"),
                                                                r.get("description"))
        rec.ultima_coleta_id = coleta_id
        dao.salvar_recurso(rec)
        existentes[r["id"]] = rec  # recurso repetido no mesmo pacote não vira duas linhas
    payload = regras.snapshot_payload(pkg)
    dao.gravar_fotografia(DatasetSnapshot(coleta_id=coleta_id, dataset_id=ds.id,
                                          hash_conteudo=regras.hash_payload(payload),
                                          payload=payload))


def job_coleta_diaria() -> None:
    db = SessionLocal()
    try:
        c = iniciar(db, origem="agendada")
    except ColetaEmAndamento:
        log.info("Coleta agendada ignorada: já há uma em execução.")
        return
    finally:
        db.close()
    executar(c.id)


# ------------------------------------------------------------------ tela Datasets (PBI-83)
class DatasetNaoEncontrado(LookupError):
    pass


def _utc(valor: datetime | None) -> datetime | None:
    return valor.replace(tzinfo=UTC) if valor is not None and valor.tzinfo is None else valor


def _validos(ds: Dataset) -> list[Recurso]:
    """Recursos que contam: ainda no pacote do dataset e sem dicionário de dados."""
    return [r for r in recursos_atuais(ds) if not r.eh_dicionario_dados]


def _linha(ds: Dataset, orgaos: dict[int, Organizacao]) -> DatasetOut:
    validos = _validos(ds)
    ultima = ultima_atualizacao_real(validos)
    org = orgaos.get(ds.organizacao_id) if ds.organizacao_id is not None else None
    return DatasetOut(
        id=ds.id, id_ckan=ds.id_ckan, name=ds.name, titulo=ds.titulo,
        organizacao_id=ds.organizacao_id,
        orgao_nome=org.titulo if org is not None else None,
        recursos_validos=len(validos),
        formatos=sorted({r.formato for r in validos if r.formato}),
        ultima_atualizacao=_utc(ultima.data), ultima_atualizacao_estimada=ultima.estimada,
        metadata_modified=_utc(ds.metadata_modified),
        situacao=regras.situacao_no_portal(ds.ativo_no_portal, len(validos)))


def listar_datasets(db: Session, user: UsuarioAtual, *, busca: str | None = None,
                    orgao: int | None = None, formato: str | None = None,
                    situacao: str | None = None) -> DatasetsOut:
    """PBI-83 — tela Datasets: inventário do portal com recursos válidos, formatos, última
    atualização real e situação no portal. Filtros: busca (título ou name, sem acento), órgão
    (`id` da organização), formato (algum recurso válido nesse formato) e situação."""
    dao = InventarioDao.de(db, user)
    orgaos = dao.organizacoes()
    todas = [_linha(ds, orgaos) for ds in dao.datasets_visiveis(user)]
    filtradas = [
        d for d in todas
        if regras.contem_texto(busca, d.titulo, d.name)
        and (not orgao or d.organizacao_id == orgao)
        and (not formato or formato.upper() in d.formatos)
        and (not situacao or d.situacao == situacao)
    ]
    filtradas.sort(key=lambda d: (regras.chave_texto(d.titulo), d.id))
    presentes = {d.organizacao_id for d in todas if d.organizacao_id}
    opcoes = DatasetsOpcoesOut(
        orgaos=sorted((OpcaoOut(valor=str(i), rotulo=orgaos[i].titulo.strip())
                       for i in presentes if i in orgaos),
                      key=lambda o: regras.chave_texto(o.rotulo)),
        formatos=sorted({f for d in todas for f in d.formatos}),
        situacoes=[s for s in regras.SITUACOES_NO_PORTAL if any(d.situacao == s for d in todas)])
    return DatasetsOut(total=len(todas), opcoes=opcoes, datasets=filtradas)


def obter_dataset(db: Session, dataset_id: int, user: UsuarioAtual) -> DatasetDetalheOut:
    """Detalhe do dataset (modal da tela): dados do CKAN e lista dos recursos atuais. Dataset de
    outro órgão para usuário restrito → não encontrado."""
    dao = InventarioDao.de(db, user)
    ds = dao.dataset_visivel(dataset_id, user)
    if ds is None:
        raise DatasetNaoEncontrado("Dataset não encontrado no inventário.")
    atuais = recursos_atuais(ds)
    recursos = sorted(atuais, key=lambda r: (r.eh_dicionario_dados,
                                             regras.chave_texto(r.nome), r.id))
    return DatasetDetalheOut(
        **_linha(ds, dao.organizacoes()).model_dump(),
        descricao=ds.descricao, metadata_created=_utc(ds.metadata_created),
        periodicidade_declarada=ds.periodicidade_declarada, licenca=ds.licenca,
        recursos=[RecursoOut(id=r.id, id_ckan=r.id_ckan, nome=r.nome, formato=r.formato,
                             url=r.url,
                             created=_utc(r.created_ckan), last_modified=_utc(r.last_modified),
                             eh_dicionario_dados=r.eh_dicionario_dados) for r in recursos],
        recursos_removidos=len(ds.recursos) - len(atuais))
