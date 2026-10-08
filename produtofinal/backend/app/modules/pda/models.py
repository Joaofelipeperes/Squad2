"""Modelo do módulo pda: vários PDAs cadastrados (um vigente) e as bases previstas de cada um.

Decisão de 07/10/2026 (Humberto, Eixo 1 — pendente de validação da GEDA): a solução guarda
vários PDAs identificados por nome; o VIGENTE rege a tela e os indicadores de gestão das bases.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, utcnow
from app.modules.inventario.models import Dataset, Organizacao


class PlanoPda(TimestampMixin, Base):
    """Um Plano de Dados Abertos importado (ex.: "PDA 2025-2027")."""

    __tablename__ = "pda_plano"
    __table_args__ = (
        # No máximo um PDA vigente (índice único parcial; o serviço também garante na transação)
        Index("uq_pda_plano_vigente", "vigente", unique=True,
              postgresql_where=text("vigente"), sqlite_where=text("vigente")),
        # Nome único sem diferenciar maiúsculas ("PDA 2026" × "pda 2026"), inclusive em gravações
        # concorrentes; o serviço transforma a violação em 409
        Index("uq_pda_plano_nome_ci", text("lower(nome)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True)
    vigencia_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente: Mapped[bool] = mapped_column(Boolean, default=False)
    arquivo_nome: Mapped[str | None] = mapped_column(String(300), nullable=True)
    importado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    importado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_bases: Mapped[int] = mapped_column(Integer, default=0)

    bases: Mapped[list["BasePrevista"]] = relationship(
        back_populates="plano", cascade="all, delete-orphan", passive_deletes=True)


class BasePrevista(TimestampMixin, Base):
    """Linha do PDA. O vínculo com o CKAN é SEMPRE pelo ID do dataset (PBI-13); o `name` lido da
    planilha fica em `dataset_name_planilha` apenas para auditoria e para resolver vínculos."""

    __tablename__ = "pda_base_prevista"

    id: Mapped[int] = mapped_column(primary_key=True)
    plano_id: Mapped[int] = mapped_column(ForeignKey("pda_plano.id", ondelete="CASCADE"),
                                          index=True)
    orgao_sigla: Mapped[str] = mapped_column(String(100), index=True)  # como veio da planilha
    organizacao_id: Mapped[str | None] = mapped_column(ForeignKey("organizacao.ckan_id"),
                                                       nullable=True, index=True)
    nome_previsto: Mapped[str] = mapped_column(String(500))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    unidade_responsavel: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prazo_abertura: Mapped[date | None] = mapped_column(Date, nullable=True)
    periodicidade: Mapped[str] = mapped_column(String(40), default="Sem informação")  # normalizada
    periodicidade_original: Mapped[str | None] = mapped_column(String(100), nullable=True)
    politicas_publicas: Mapped[str | None] = mapped_column(String(500), nullable=True)
    possui_conteudo_sigiloso: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("dataset.ckan_id"), nullable=True,
                                                   index=True)
    dataset_name_planilha: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linha_planilha: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classificacao: Mapped[str] = mapped_column(String(20), default="pda")  # pda | espontanea (US7)

    plano: Mapped[PlanoPda] = relationship(back_populates="bases")
    dataset: Mapped[Dataset | None] = relationship()  # carregar com selectinload (sem N+1)
    organizacao: Mapped[Organizacao | None] = relationship()
