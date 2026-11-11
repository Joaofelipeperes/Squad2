"""Backups internos do banco (ADR-0034): execução agendada, limpeza, exportação e restauração.

Os jobs rodam no worker (ADR-0012). Uma falha vira registro `situacao="erro"` e linha de log, nunca
derruba o worker; a execução seguinte da mesma referência reaproveita o registro de erro.
"""
import gzip
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.core.db import SessionLocal, utcnow
from app.modules.backup import regras
from app.modules.backup.dao import BackupDao
from app.modules.backup.gerador import (
    FORMATO_PG,
    FORMATO_SQLITE,
    ErroBackup,
    gerar_dump,
    restaurar_pg,
)
from app.modules.backup.models import BackupCopia

log = logging.getLogger("backup")

__all__ = [
    "ErroBackup",
    "executar_backup",
    "exportar",
    "job_diario",
    "job_limpeza",
    "job_mensal",
    "limpar_vencidos",
    "listar",
    "restaurar",
]


def _hoje_local() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _url_do_banco() -> str:
    return get_settings().database_url


def executar_backup(tipo: str, hoje: date | None = None) -> BackupCopia:
    """Gera o backup `tipo` ("diario" | "mensal") da referência de `hoje` (padrão: hoje, no fuso do
    sistema). Já existindo um backup ok da referência, não gera outro. Não levanta em falha do dump:
    devolve o registro com `situacao="erro"`."""
    if tipo not in regras.TIPOS:
        raise ValueError(f"Tipo de backup desconhecido: {tipo!r}")
    hoje = hoje or _hoje_local()
    referencia = (regras.referencia_diaria(hoje) if tipo == "diario"
                  else regras.referencia_mensal(hoje))

    with SessionLocal() as db:
        existente = BackupDao(db).por_referencia(tipo, referencia)
        if existente is not None and existente.situacao == "ok":
            log.info("Backup %s %s já existe (id %s): nada a fazer", tipo, referencia, existente.id)
            return existente
        existente_id = existente.id if existente else None

    iniciado_em = utcnow()
    dump = token = sha = erro = None
    try:  # o dump roda sem sessão aberta: pode levar minutos
        dump = gerar_dump(_url_do_banco())
        sha = regras.sha256(dump.dados)
        token = encrypt_bytes(dump.dados)
    except Exception as exc:
        erro = f"{type(exc).__name__}: {exc}"[:2000]
        log.exception("Backup %s %s falhou", tipo, referencia)

    with SessionLocal() as db:
        dao = BackupDao(db)
        copia = dao.obter(BackupCopia, existente_id) or BackupCopia(tipo=tipo, referencia=referencia)
        copia.situacao = "erro" if erro else "ok"
        copia.erro = erro
        copia.formato = dump.formato if dump else None
        copia.iniciado_em, copia.concluido_em = iniciado_em, utcnow()
        copia.expira_em = regras.expira_em(tipo, iniciado_em)
        copia.tamanho_bytes = len(dump.dados) if dump else None
        copia.sha256 = sha
        copia.conteudo = token  # None em erro (atribuição explícita: nunca fica "não carregado")
        dao.gravar(copia)
    if not erro:
        log.info("Backup %s %s concluído: %s bytes (id %s)", tipo, referencia,
                 copia.tamanho_bytes, copia.id)
    return copia


def limpar_vencidos(agora: datetime | None = None) -> int:
    """Libera o conteúdo e exclui logicamente os backups vencidos. Retorna quantos."""
    with SessionLocal() as db:
        n = BackupDao(db).expirar_vencidos(agora or utcnow())
    if n:
        log.info("Backups vencidos liberados: %s", n)
    return n


def listar(tipo: str | None = None) -> list[BackupCopia]:
    with SessionLocal() as db:
        return BackupDao(db).listar(tipo)


def _dump_decifrado(id_: int) -> tuple[BackupCopia, bytes]:
    with SessionLocal() as db:
        copia = BackupDao(db).com_conteudo(id_)
    if copia is None or copia.situacao != "ok" or not copia.conteudo:
        raise ErroBackup(f"Backup {id_} não encontrado, com erro ou já expirado.")
    try:
        dados = decrypt_bytes(copia.conteudo)
    except RuntimeError as exc:
        raise ErroBackup(f"Backup {id_}: {exc} (a GDA_ENCRYPTION_KEY mudou?)") from exc
    if regras.sha256(dados) != copia.sha256:
        raise ErroBackup(f"Backup {id_} falhou na conferência de integridade (sha256).")
    return copia, dados


def exportar(id_: int, destino: Path) -> Path:
    """Decifra, confere a integridade e grava o dump em `destino`: arquivo `.dump` do pg_dump
    (para o `pg_restore`) ou o banco SQLite descompactado."""
    copia, dados = _dump_decifrado(id_)
    destino = Path(destino)
    destino.write_bytes(gzip.decompress(dados) if copia.formato == FORMATO_SQLITE else dados)
    return destino


def restaurar(id_: int, banco_destino: str, sobrescrever: bool = False) -> None:
    """Restaura um backup de PostgreSQL no banco `banco_destino` (que já deve existir) com o
    `pg_restore`. Restaurar no banco em uso exige `sobrescrever=True`. Em SQLite use `exportar`."""
    copia, dados = _dump_decifrado(id_)
    if copia.formato != FORMATO_PG:
        raise ErroBackup("Este backup não é do PostgreSQL: use exportar e substitua o arquivo do banco.")
    url = _url_do_banco()
    if banco_destino == regras.dados_conexao(url).banco and not sobrescrever:
        raise ErroBackup(f"{banco_destino!r} é o banco em uso: restaurar nele apaga os dados atuais. "
                         "Restaure num banco novo ou confirme com sobrescrever.")
    restaurar_pg(url, banco_destino, dados)
    log.warning("Backup %s restaurado em %r", id_, banco_destino)


# ------------------------------------------------------------------ jobs do worker
def job_diario() -> None:
    executar_backup("diario")


def job_mensal() -> None:
    executar_backup("mensal")


def job_limpeza() -> None:
    limpar_vencidos()
