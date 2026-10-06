"""Proposta inicial — ajustar pela responsável do Eixo 2.

Não retenção (PBI-35): o achado guarda LOCALIZAÇÃO (recurso, coluna, linha) e o tipo, nunca o
valor encontrado. A cópia do original para reversão (PBI-94) vive fora do banco, com prazo de
retenção definido pela GEDA.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Achado(TimestampMixin, Base):
    __tablename__ = "lgpd_achado"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurso_id: Mapped[str] = mapped_column(ForeignKey("recurso.ckan_id"), index=True)
    coluna: Mapped[str] = mapped_column(String(300))
    linha: Mapped[int | None] = mapped_column(Integer, nullable=True)  # primeira ocorrência
    ocorrencias: Mapped[int] = mapped_column(Integer, default=1)
    tipo: Mapped[str] = mapped_column(String(40))                     # cpf, email, nome...
    metodo: Mapped[str] = mapped_column(String(20))                   # regra | ia
    confianca: Mapped[int] = mapped_column(Integer)                   # 0–100 (PBI-86)
    prioridade: Mapped[str] = mapped_column(String(10))               # Alta | Média | Baixa
    status: Mapped[str] = mapped_column(String(20), default="revisar")  # revisar|confirmado|falso_positivo|tratado
    impressao_digital: Mapped[str] = mapped_column(String(64), index=True)  # evita reapresentar (PBI-41)


class DecisaoTriagem(Base):
    """Histórico imutável das decisões humanas (PBI-42)."""

    __tablename__ = "lgpd_decisao"

    id: Mapped[int] = mapped_column(primary_key=True)
    achado_id: Mapped[int] = mapped_column(ForeignKey("lgpd_achado.id"), index=True)
    decisao: Mapped[str] = mapped_column(String(20))
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario: Mapped[str] = mapped_column(String(200))
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorrecaoPublicada(TimestampMixin, Base):
    """Trilha da anonimização publicada no CKAN (PBI-92 a PBI-94)."""

    __tablename__ = "lgpd_correcao"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurso_id: Mapped[str] = mapped_column(ForeignKey("recurso.ckan_id"), index=True)
    aprovado_por: Mapped[str] = mapped_column(String(200))
    aprovado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    caminho_backup: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pendente")  # pendente|publicada|revertida|erro
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
