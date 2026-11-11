from datetime import datetime

from sqlalchemy import BigInteger, DateTime, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, unico_entre_ativos


class BackupCopia(Base):
    """Cópia completa do banco da aplicação, guardada cifrada na própria tabela (ADR-0034). Uma por
    tipo e referência: diário = data (AAAA-MM-DD, guardado 7 dias); mensal = mês que terminou
    (AAAA-MM, guardado 1 ano). Vencido: a linha é excluída logicamente e o `conteudo` é liberado."""

    __tablename__ = "backup_copia"
    __table_args__ = (unico_entre_ativos("backup_copia", "tipo", "referencia"),)

    tipo: Mapped[str] = mapped_column(String(10))  # diario | mensal
    referencia: Mapped[str] = mapped_column(String(10))  # AAAA-MM-DD (diario) | AAAA-MM (mensal)
    situacao: Mapped[str] = mapped_column(String(10))  # ok | erro
    formato: Mapped[str | None] = mapped_column(String(20), nullable=True)  # pg_dump_custom | sqlite_gzip
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # do dump, sem cifra
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)  # do dump, sem cifra
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Dump cifrado (Fernet, GDA_ENCRYPTION_KEY). Carregado só quando pedido (deferred): listar não lê.
    conteudo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
