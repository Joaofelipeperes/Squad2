"""Geração e restauração do dump do banco (ADR-0034).

PostgreSQL (homologação e produção): `pg_dump -Fc` (formato custom, já compactado) e `pg_restore`.
SQLite (desenvolvimento e testes): cópia consistente pela API nativa `sqlite3.backup()`, compactada.
Os dados da própria tabela `backup_copia` ficam de fora, para os backups não crescerem uns dentro
dos outros. Registros excluídos logicamente entram: o backup é do banco inteiro.
"""
import gzip
import os
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.modules.backup.regras import dados_conexao

TABELA_DOS_BACKUPS = "backup_copia"
FORMATO_PG = "pg_dump_custom"
FORMATO_SQLITE = "sqlite_gzip"


class ErroBackup(Exception):
    """Falha ao gerar, ler ou restaurar um backup (mensagem pronta para o log e para o operador)."""


@dataclass(frozen=True)
class Dump:
    dados: bytes
    formato: str


def eh_sqlite(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


def _argumentos_de_conexao(database_url: str, banco: str | None = None) -> tuple[list[str], dict]:
    """Opções de conexão do cliente do PostgreSQL. A senha vai por PGPASSWORD (nunca na linha de
    comando, onde apareceria na lista de processos)."""
    d = dados_conexao(database_url)
    args: list[str] = []
    if d.host:
        args += ["-h", d.host]
    if d.porta:
        args += ["-p", str(d.porta)]
    if d.usuario:
        args += ["-U", d.usuario]
    args += ["-d", banco or d.banco or ""]
    env = dict(os.environ)
    if d.senha:
        env["PGPASSWORD"] = d.senha
    return args, env


def comando_pg_dump(database_url: str) -> tuple[list[str], dict]:
    args, env = _argumentos_de_conexao(database_url)
    cmd = [get_settings().backup_pg_dump, "-Fc", f"--exclude-table-data={TABELA_DOS_BACKUPS}", *args]
    return cmd, env


def comando_pg_restore(database_url: str, banco_destino: str) -> tuple[list[str], dict]:
    args, env = _argumentos_de_conexao(database_url, banco_destino)
    cmd = [get_settings().backup_pg_restore, "--no-owner", "--clean", "--if-exists", *args]
    return cmd, env


def _executar(cmd: list[str], env: dict, entrada: bytes | None = None) -> bytes:
    try:
        r = subprocess.run(cmd, env=env, input=entrada, capture_output=True,
                           timeout=get_settings().backup_timeout_s, check=False)
    except FileNotFoundError as exc:
        raise ErroBackup(f"Programa {cmd[0]!r} não encontrado: instale o cliente do PostgreSQL 16 "
                         "na imagem do backend (ver backend/Dockerfile).") from exc
    except subprocess.TimeoutExpired as exc:
        raise ErroBackup(f"{cmd[0]} excedeu {get_settings().backup_timeout_s} s.") from exc
    if r.returncode != 0:
        detalhe = (r.stderr or b"").decode("utf-8", "replace").strip()[:1500]
        raise ErroBackup(f"{cmd[0]} terminou com erro {r.returncode}: {detalhe}")
    return r.stdout


def _dump_sqlite(database_url: str) -> bytes:
    origem = make_url(database_url).database
    if not origem or origem == ":memory:":
        raise ErroBackup("Backup de SQLite exige um banco em arquivo.")
    with tempfile.TemporaryDirectory() as pasta:
        copia = Path(pasta) / "copia.db"
        src, dst = sqlite3.connect(origem), sqlite3.connect(copia)
        try:
            src.backup(dst)
            existe = dst.execute("select 1 from sqlite_master where type='table' and name=?",
                                 (TABELA_DOS_BACKUPS,)).fetchone()
            if existe:
                dst.execute(f"delete from {TABELA_DOS_BACKUPS}")
                dst.commit()
                dst.execute("vacuum")
        finally:
            src.close()
            dst.close()
        return gzip.compress(copia.read_bytes())


def gerar_dump(database_url: str) -> Dump:
    if eh_sqlite(database_url):
        return Dump(_dump_sqlite(database_url), FORMATO_SQLITE)
    cmd, env = comando_pg_dump(database_url)
    return Dump(_executar(cmd, env), FORMATO_PG)


def restaurar_pg(database_url: str, banco_destino: str, dados: bytes) -> None:
    cmd, env = comando_pg_restore(database_url, banco_destino)
    _executar(cmd, env, entrada=dados)
