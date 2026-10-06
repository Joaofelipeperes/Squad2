"""Usuários, papéis e permissões (RBAC). O catálogo de permissões vive em app/core/permissoes.py;
aqui fica só a atribuição: usuário ↔ papéis ↔ códigos de permissão."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin

usuario_papel = Table(
    "acesso_usuario_papel", Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True),
    Column("papel_id", ForeignKey("acesso_papel.id", ondelete="CASCADE"), primary_key=True),
)


class Papel(TimestampMixin, Base):
    __tablename__ = "acesso_papel"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    sistema: Mapped[bool] = mapped_column(Boolean, default=False)      # criado pelo catálogo
    exige_orgao: Mapped[bool] = mapped_column(Boolean, default=False)  # usuário precisa de órgão
    todas: Mapped[bool] = mapped_column(Boolean, default=False)        # administrador

    permissoes: Mapped[list["PapelPermissao"]] = relationship(
        back_populates="papel", cascade="all, delete-orphan", lazy="selectin")


class PapelPermissao(Base):
    __tablename__ = "acesso_papel_permissao"

    papel_id: Mapped[int] = mapped_column(ForeignKey("acesso_papel.id", ondelete="CASCADE"),
                                          primary_key=True)
    permissao: Mapped[str] = mapped_column(String(80), primary_key=True)

    papel: Mapped[Papel] = relationship(back_populates="permissoes")


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Preenchido = usuário restrito aos dados deste órgão (ex.: órgão publicador)
    orgao_id: Mapped[str | None] = mapped_column(ForeignKey("organizacao.ckan_id"), nullable=True)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    papeis: Mapped[list[Papel]] = relationship(secondary=usuario_papel, lazy="selectin")
