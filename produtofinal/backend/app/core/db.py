"""Engine, sessão e Base declarativa do SQLAlchemy (modo síncrono, mais simples para o time).

Toda tabela herda de `Base` as colunas de identidade e auditoria (ADR-0019): `id` (PK inteira),
`deleted` (exclusão lógica), `created`/`created_id` e `changed`/`changed_id` (data e usuário da
criação e da última alteração). Quem preenche a auditoria e filtra os excluídos é o `Dao`
(`app/core/dao.py`) — nenhum módulo acessa a sessão diretamente.
"""
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    MetaData,
    create_engine,
    false,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Nomes determinísticos para constraints: migrações reproduzíveis (e exigido pelo SQLite em batch)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Condição dos registros ativos, usada nos índices únicos parciais (`unico_entre_ativos`)
SO_ATIVOS = "NOT deleted"


class RegistroMixin:
    """Identidade e auditoria comuns a TODAS as tabelas. `created_id`/`changed_id` = `usuario.id`
    de quem criou/alterou por último (None = sistema: coleta, CLI, migração); referência lógica
    sem FK para não criar ciclos (usuario → organizacao → usuario)."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, sort_order=-100)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(),
                                          sort_order=100)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                              server_default=func.current_timestamp(),
                                              sort_order=101)
    created_id: Mapped[int | None] = mapped_column(Integer, nullable=True, sort_order=102)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                              server_default=func.current_timestamp(),
                                              onupdate=utcnow, sort_order=103)
    changed_id: Mapped[int | None] = mapped_column(Integer, nullable=True, sort_order=104)


class Base(RegistroMixin, DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def unico_entre_ativos(tabela: str, *colunas, nome: str | None = None) -> Index:
    """Índice único que vale só entre registros não excluídos (ADR-0019): excluir libera o valor
    (ex.: o e-mail de um usuário excluído pode ser cadastrado de novo). `colunas` aceita nomes ou
    expressões (`text("lower(nome)")`); `nome` é obrigatório para expressões."""
    nome = nome or "uq_" + tabela + "_" + "_".join(str(c) for c in colunas)
    return Index(nome, *colunas, unique=True, postgresql_where=text(SO_ATIVOS),
                 sqlite_where=text(SO_ATIVOS))


_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
