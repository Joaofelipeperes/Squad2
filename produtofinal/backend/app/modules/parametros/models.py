from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Parametro(TimestampMixin, Base):
    __tablename__ = "parametro"

    chave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[object] = mapped_column(JSON)
    alterado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
