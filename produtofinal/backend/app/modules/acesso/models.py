"""Usuários, papéis e permissões (RBAC). O catálogo de permissões vive em app/core/permissoes.py;
aqui fica só a atribuição: usuário ↔ papéis ↔ códigos de permissão.

As associações são tabelas com `id` próprio e exclusão lógica (ADR-0019); as relações `papeis` e
`permissoes` são só leitura e enxergam apenas as associações ativas — quem grava é o `AcessoDao`.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, unico_entre_ativos, utcnow


class Papel(Base):
    """Conjunto nomeado de permissões atribuível a usuários (ex.: Gerência GEDA)."""

    __tablename__ = "acesso_papel"
    __table_args__ = (unico_entre_ativos("acesso_papel", "codigo"),)

    codigo: Mapped[str] = mapped_column(String(60))
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    sistema: Mapped[bool] = mapped_column(Boolean, default=False)      # criado pelo catálogo
    exige_orgao: Mapped[bool] = mapped_column(Boolean, default=False)  # usuário precisa de órgão
    todas: Mapped[bool] = mapped_column(Boolean, default=False)        # administrador

    permissoes: Mapped[list["PapelPermissao"]] = relationship(
        primaryjoin="and_(Papel.id == PapelPermissao.papel_id, PapelPermissao.deleted.is_(False))",
        viewonly=True, lazy="selectin", order_by="PapelPermissao.permissao")


class PapelPermissao(Base):
    """Código de permissão do catálogo (app/core/permissoes.py) concedido a um papel."""

    __tablename__ = "acesso_papel_permissao"
    __table_args__ = (unico_entre_ativos("acesso_papel_permissao", "papel_id", "permissao"),)

    papel_id: Mapped[int] = mapped_column(ForeignKey("acesso_papel.id", ondelete="CASCADE"),
                                          index=True)
    permissao: Mapped[str] = mapped_column(String(80))


class UsuarioPapel(Base):
    """Papel atribuído a um usuário."""

    __tablename__ = "acesso_usuario_papel"
    __table_args__ = (unico_entre_ativos("acesso_usuario_papel", "usuario_id", "papel_id"),)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"),
                                            index=True)
    papel_id: Mapped[int] = mapped_column(ForeignKey("acesso_papel.id", ondelete="CASCADE"),
                                          index=True)


class Usuario(Base):
    """Pessoa com acesso à solução; com órgão vinculado, fica restrita aos dados dele."""

    __tablename__ = "usuario"
    __table_args__ = (unico_entre_ativos("usuario", "email"),)

    email: Mapped[str] = mapped_column(String(200))
    nome: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Preenchido = usuário restrito aos dados deste órgão (ex.: órgão publicador)
    orgao_id: Mapped[int | None] = mapped_column(ForeignKey("organizacao.id"), nullable=True)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    papeis: Mapped[list[Papel]] = relationship(
        secondary="acesso_usuario_papel",
        primaryjoin="and_(Usuario.id == UsuarioPapel.usuario_id, UsuarioPapel.deleted.is_(False))",
        secondaryjoin="Papel.id == UsuarioPapel.papel_id",
        viewonly=True, lazy="selectin")


class LogAcesso(Base):
    """Log de acesso: uma linha por requisição à API (quem, de onde, o quê, resultado). Só inserção."""

    __tablename__ = "acesso_log"

    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                  index=True)
    usuario: Mapped[str | None] = mapped_column(String(200), index=True)  # e-mail; None = anônimo
    metodo: Mapped[str] = mapped_column(String(10))                       # GET, POST, PUT, DELETE
    caminho: Mapped[str] = mapped_column(String(500))                     # URL com query string
    rota: Mapped[str | None] = mapped_column(String(200))  # modelo da rota: /api/v1/pda/planos/{id}
    acao: Mapped[str | None] = mapped_column(String(100))  # função que atendeu: excluir_papel
    status_http: Mapped[int] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
