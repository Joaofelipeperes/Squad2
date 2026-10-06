"""Perfis de provedor de IA, vínculo tarefa→perfil e registro de uso (sem conteúdo)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, utcnow


class PerfilProvedorIA(TimestampMixin, Base):
    """Uma configuração nomeada de provedor+modelo. Ex.: 'Gemini SECTI', 'Qwen local'."""

    __tablename__ = "ia_perfil_provedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    tipo: Mapped[str] = mapped_column(String(40))            # gemini | ollama | openai_compat | mock
    modelo: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_dica: Mapped[str | None] = mapped_column(String(20), nullable=True)
    execucao_local: Mapped[bool] = mapped_column(Boolean, default=False)
    temperatura: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    timeout_s: Mapped[float] = mapped_column(Float, default=60.0)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class VinculoTarefaIA(TimestampMixin, Base):
    """Qual perfil atende cada tarefa de IA (e qual assume se o principal falhar)."""

    __tablename__ = "ia_vinculo_tarefa"

    tarefa: Mapped[str] = mapped_column(String(40), primary_key=True)
    perfil_id: Mapped[int | None] = mapped_column(ForeignKey("ia_perfil_provedor.id",
                                                             ondelete="SET NULL"), nullable=True)
    perfil_fallback_id: Mapped[int | None] = mapped_column(
        ForeignKey("ia_perfil_provedor.id", ondelete="SET NULL"), nullable=True)
    alterado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)


class UsoIA(Base):
    """Uma linha por chamada. NÃO guarda prompt nem resposta (PBI-35 — não retenção)."""

    __tablename__ = "ia_uso"

    id: Mapped[int] = mapped_column(primary_key=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    tarefa: Mapped[str] = mapped_column(String(40))
    perfil_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    perfil_nome: Mapped[str] = mapped_column(String(120))
    modelo: Mapped[str] = mapped_column(String(200))
    sucesso: Mapped[bool] = mapped_column(Boolean)
    usou_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erro: Mapped[str | None] = mapped_column(String(500), nullable=True)
