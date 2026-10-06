"""Proposta inicial — ajustar pelo responsável do Eixo 1."""
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class BasePrevista(TimestampMixin, Base):
    """Linha do PDA 2025/2027. O vínculo com o CKAN é SEMPRE pelo ID do dataset (PBI-13)."""

    __tablename__ = "pda_base_prevista"

    id: Mapped[int] = mapped_column(primary_key=True)
    orgao_sigla: Mapped[str] = mapped_column(String(40), index=True)
    nome_previsto: Mapped[str] = mapped_column(String(500))
    prazo_abertura: Mapped[date | None] = mapped_column(Date, nullable=True)
    periodicidade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("dataset.ckan_id"), nullable=True,
                                                   index=True)
    classificacao: Mapped[str] = mapped_column(String(20), default="pda")  # pda | espontanea (US7)
