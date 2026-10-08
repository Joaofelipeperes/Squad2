"""Coleta do inventário CKAN → banco local (PBI-07 a PBI-11, PBI-71).

Implementação de referência da base comum: percorre organizações e datasets pela API pública,
faz upsert do estado atual e grava uma fotografia por dataset para o diff da rastreabilidade.
"""
import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, utcnow
from app.integrations.ckan.client import CkanClient
from app.modules.inventario import regras
from app.modules.inventario.models import Coleta, Dataset, DatasetSnapshot, Organizacao, Recurso

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
    ds.organizacao_id = (pkg.get("organization") or {}).get("id")
    ds.autor, ds.autor_email = pkg.get("author"), pkg.get("author_email")
    ds.licenca = pkg.get("license_id")
    ds.periodicidade_declarada = extras.get("periodicidade") or pkg.get("periodicidade")
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
