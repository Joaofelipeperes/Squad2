"""Regras puras dos backups (sem banco, sem I/O): referências, validade e dados de conexão."""
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.engine import make_url

from app.core.config import get_settings

TIPOS = ("diario", "mensal")


def referencia_diaria(hoje: date) -> str:
    """O backup diário das 00:00 de `hoje` é identificado pela data de hoje."""
    return hoje.isoformat()


def referencia_mensal(hoje: date) -> str:
    """O backup mensal roda à 00:00 do dia 1 e cobre o mês que acabou de terminar."""
    ultimo_do_mes_anterior = hoje.replace(day=1) - timedelta(days=1)
    return f"{ultimo_do_mes_anterior.year:04d}-{ultimo_do_mes_anterior.month:02d}"


def expira_em(tipo: str, a_partir_de: datetime) -> datetime:
    """Diário: 7 dias. Mensal: 1 ano (365 dias). Configurável por GDA_BACKUP_RETENCAO_*."""
    s = get_settings()
    if tipo == "diario":
        return a_partir_de + timedelta(days=s.backup_retencao_diaria_dias)
    if tipo == "mensal":
        return a_partir_de + timedelta(days=s.backup_retencao_mensal_dias)
    raise ValueError(f"Tipo de backup desconhecido: {tipo!r}")


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


@dataclass(frozen=True)
class DadosConexao:
    host: str | None
    porta: int | None
    usuario: str | None
    senha: str | None
    banco: str | None


def dados_conexao(database_url: str) -> DadosConexao:
    u = make_url(database_url)
    return DadosConexao(u.host, u.port, u.username, u.password, u.database)
