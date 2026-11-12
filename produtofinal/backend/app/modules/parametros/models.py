from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, unico_entre_ativos


class Parametro(Base):
    """Valor de negócio editável pela GEDA; ausente no banco = vale o padrão do catálogo."""

    __tablename__ = "parametro"
    __table_args__ = (unico_entre_ativos("parametro", "chave"),)

    chave: Mapped[str] = mapped_column(String(80))
    valor: Mapped[object] = mapped_column(JSON)
    alterado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
