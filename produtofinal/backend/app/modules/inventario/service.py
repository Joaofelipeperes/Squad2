"""Coleta do inventário CKAN → banco local (PBI-07 a PBI-11, PBI-71).

Implementação de referência da base comum: percorre organizações e datasets pela API pública,
faz upsert do estado atual e grava uma fotografia por dataset para o diff da rastreabilidade.
"""
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.integrations.ckan.client import CkanClient
from app.modules.atualizacoes.regras import ultima_atualizacao_real
from app.modules.inventario import regras
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
    return db.scalar(select(Coleta).where(Coleta.status == "executando"))


def ultima_coleta(db: Session) -> Coleta | None:
    return db.scalar(select(Coleta).order_by(Coleta.id.desc()).limit(1))


def iniciar(db: Session, origem: str, solicitante: str | None = None) -> Coleta:
    if coleta_em_andamento(db):
        raise ColetaEmAndamento("Já existe uma coleta em execução.")
    c = Coleta(origem=origem, solicitada_por=solicitante)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def executar(coleta_id: int, client: CkanClient | None = None) -> None:
    """Roda a coleta completa. Abre a própria sessão (é chamado em background ou pelo worker)."""
    db = SessionLocal()
    own_client = client is None
    client = client or CkanClient()
    coleta = db.get(Coleta, coleta_id)
    try:
        orgs = client.organizations()
        for o in orgs:
            db.merge(Organizacao(ckan_id=o["id"], name=o["name"], titulo=o.get("title") or o["name"],
                                 ultima_coleta_id=coleta_id))
        # Grava os órgãos antes dos datasets: sem relationship Dataset→Organizacao (e com
        # autoflush desligado) o SQLAlchemy não garante essa ordem e a FK falha no PostgreSQL.
        db.flush()
        n_ds = n_res = 0
        vistos: set[str] = set()
        for pkg in client.iter_datasets():
            _upsert_dataset(db, pkg, coleta_id)
            vistos.add(pkg["id"])
            n_ds += 1
            n_res += len(pkg.get("resources", []))
            if n_ds % 100 == 0:
                db.commit()
        # datasets que sumiram do portal (excluídos ou privados) — PBI-15 / US14
        if vistos:
            db.execute(update(Dataset).where(Dataset.ckan_id.not_in(vistos))
                       .values(ativo_no_portal=False))
        coleta.total_organizacoes, coleta.total_datasets, coleta.total_recursos = (
            len(orgs), n_ds, n_res)
        coleta.status = "ok"
    except Exception as exc:  # noqa: BLE001 — registrar qualquer falha na coleta (PBI-10)
        db.rollback()
        coleta = db.get(Coleta, coleta_id)
        coleta.status, coleta.erro = "erro", f"{type(exc).__name__}: {exc}"[:4000]
        log.exception("Coleta %s falhou", coleta_id)
    finally:
        coleta.finalizada_em = utcnow()
        db.commit()
        db.close()
        if own_client:
            client.close()


def _upsert_dataset(db: Session, pkg: dict, coleta_id: int) -> None:
    extras = regras.extras_como_dict(pkg.get("extras"))
    ds = db.get(Dataset, pkg["id"]) or Dataset(ckan_id=pkg["id"])
    ds.name, ds.titulo = pkg["name"], pkg.get("title") or pkg["name"]
    ds.descricao = (pkg.get("notes") or "").strip() or None
    ds.organizacao_id = (pkg.get("organization") or {}).get("id")
    ds.autor, ds.autor_email = pkg.get("author"), pkg.get("author_email")
    ds.licenca = pkg.get("license_id")
    ds.periodicidade_declarada = regras.periodicidade_declarada(extras, pkg)
    ds.metadata_created = regras.parse_ckan_datetime(pkg.get("metadata_created"))
    ds.metadata_modified = regras.parse_ckan_datetime(pkg.get("metadata_modified"))
    ds.extras, ds.ativo_no_portal, ds.ultima_coleta_id = extras, True, coleta_id
    db.merge(ds)
    for r in pkg.get("resources", []):
        db.merge(Recurso(
            ckan_id=r["id"], dataset_id=pkg["id"], nome=r.get("name"),
            formato=(r.get("format") or "").upper() or None, url=r.get("url"),
            url_type=r.get("url_type") or None,
            created=regras.parse_ckan_datetime(r.get("created")),
            last_modified=regras.parse_ckan_datetime(r.get("last_modified")),
            datastore_active=bool(r.get("datastore_active")),
            eh_dicionario_dados=regras.eh_dicionario_de_dados(r.get("name"), r.get("description")),
            ultima_coleta_id=coleta_id,
        ))
    payload = regras.snapshot_payload(pkg)
    db.add(DatasetSnapshot(coleta_id=coleta_id, dataset_id=pkg["id"],
                           hash_conteudo=regras.hash_payload(payload), payload=payload))


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


def _linha(ds: Dataset, orgaos: dict[str, Organizacao]) -> DatasetOut:
    validos = _validos(ds)
    ultima = ultima_atualizacao_real(validos)
    org = orgaos.get(ds.organizacao_id or "")
    return DatasetOut(
        ckan_id=ds.ckan_id, name=ds.name, titulo=ds.titulo, organizacao_id=ds.organizacao_id,
        orgao_nome=org.titulo if org is not None else None,
        recursos_validos=len(validos),
        formatos=sorted({r.formato for r in validos if r.formato}),
        ultima_atualizacao=_utc(ultima.data), ultima_atualizacao_estimada=ultima.estimada,
        metadata_modified=_utc(ds.metadata_modified),
        situacao=regras.situacao_no_portal(ds.ativo_no_portal, len(validos)))


def _consulta_datasets(user: UsuarioAtual):
    """Datasets com recursos em lote (sem N+1), no escopo de órgão do usuário."""
    stmt = select(Dataset).options(selectinload(Dataset.recursos))
    return filtrar_por_orgao(stmt, Dataset.organizacao_id, user)


def _orgaos(db: Session) -> dict[str, Organizacao]:
    return {o.ckan_id: o for o in db.scalars(select(Organizacao))}


def listar_datasets(db: Session, user: UsuarioAtual, *, busca: str | None = None,
                    orgao: str | None = None, formato: str | None = None,
                    situacao: str | None = None) -> DatasetsOut:
    """PBI-83 — tela Datasets: inventário do portal com recursos válidos, formatos, última
    atualização real e situação no portal. Filtros: busca (título ou name, sem acento), órgão
    (ID da organização), formato (algum recurso válido nesse formato) e situação."""
    orgaos = _orgaos(db)
    todas = [_linha(ds, orgaos) for ds in db.scalars(_consulta_datasets(user))]
    filtradas = [
        d for d in todas
        if regras.contem_texto(busca, d.titulo, d.name)
        and (not orgao or d.organizacao_id == orgao)
        and (not formato or formato.upper() in d.formatos)
        and (not situacao or d.situacao == situacao)
    ]
    filtradas.sort(key=lambda d: (regras.chave_texto(d.titulo), d.ckan_id))
    presentes = {d.organizacao_id for d in todas if d.organizacao_id}
    opcoes = DatasetsOpcoesOut(
        orgaos=sorted((OpcaoOut(valor=i, rotulo=orgaos[i].titulo.strip())
                       for i in presentes if i in orgaos),
                      key=lambda o: regras.chave_texto(o.rotulo)),
        formatos=sorted({f for d in todas for f in d.formatos}),
        situacoes=[s for s in regras.SITUACOES_NO_PORTAL if any(d.situacao == s for d in todas)])
    return DatasetsOut(total=len(todas), opcoes=opcoes, datasets=filtradas)


def obter_dataset(db: Session, ckan_id: str, user: UsuarioAtual) -> DatasetDetalheOut:
    """Detalhe do dataset (modal da tela): dados do CKAN e lista dos recursos atuais. Dataset de
    outro órgão para usuário restrito → não encontrado."""
    ds = db.scalar(_consulta_datasets(user).where(Dataset.ckan_id == ckan_id))
    if ds is None:
        raise DatasetNaoEncontrado("Dataset não encontrado no inventário.")
    atuais = recursos_atuais(ds)
    recursos = sorted(atuais, key=lambda r: (r.eh_dicionario_dados,
                                             regras.chave_texto(r.nome), r.ckan_id))
    return DatasetDetalheOut(
        **_linha(ds, _orgaos(db)).model_dump(),
        descricao=ds.descricao, metadata_created=_utc(ds.metadata_created),
        periodicidade_declarada=ds.periodicidade_declarada, licenca=ds.licenca,
        recursos=[RecursoOut(ckan_id=r.ckan_id, nome=r.nome, formato=r.formato, url=r.url,
                             created=_utc(r.created), last_modified=_utc(r.last_modified),
                             eh_dicionario_dados=r.eh_dicionario_dados) for r in recursos],
        recursos_removidos=len(ds.recursos) - len(atuais))
