"""Backups internos do banco (ADR-0034): agenda, geração, retenção, restauração e falhas."""
import gzip
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.crypto import decrypt_bytes
from app.core.db import SessionLocal
from app.modules import load_modules
from app.modules.backup import gerador, regras, service
from app.modules.backup.dao import BackupDao
from app.modules.backup.models import BackupCopia


# ------------------------------------------------------------------ regras puras
def test_referencia_diaria_e_a_data_local():
    assert regras.referencia_diaria(date(2026, 11, 10)) == "2026-11-10"


@pytest.mark.parametrize("hoje, esperado", [
    (date(2026, 11, 1), "2026-10"),   # roda à 00:00 do dia 1: cobre o mês que acabou
    (date(2027, 1, 1), "2026-12"),    # virada de ano
    (date(2028, 3, 1), "2028-02"),    # ano bissexto
])
def test_referencia_mensal_e_o_mes_anterior(hoje, esperado):
    assert regras.referencia_mensal(hoje) == esperado


def test_validade_diaria_7_dias_e_mensal_1_ano():
    base = datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
    assert regras.expira_em("diario", base) == base + timedelta(days=7)
    assert regras.expira_em("mensal", base) == base + timedelta(days=365)


def test_tipo_desconhecido_e_recusado():
    with pytest.raises(ValueError):
        regras.expira_em("semanal", datetime.now(UTC))


def test_dados_de_conexao_do_postgres():
    d = regras.dados_conexao("postgresql+psycopg://gda:s%40nha@db:5432/gda")
    assert (d.host, d.porta, d.usuario, d.senha, d.banco) == ("db", 5432, "gda", "s@nha", "gda")


# ------------------------------------------------------------------ comandos do PostgreSQL
def test_comando_pg_dump_exclui_os_dados_da_propria_tabela_de_backup():
    cmd, env = gerador.comando_pg_dump("postgresql+psycopg://gda:segredo@db:5432/gda")
    assert cmd[0] == "pg_dump" and "-Fc" in cmd
    assert "--exclude-table-data=backup_copia" in cmd
    assert cmd[cmd.index("-h") + 1] == "db" and cmd[cmd.index("-d") + 1] == "gda"
    assert env["PGPASSWORD"] == "segredo"
    assert "segredo" not in " ".join(cmd)  # a senha nunca vai na linha de comando


def test_comando_pg_restore_nao_toca_no_dono_e_limpa_o_destino():
    cmd, _ = gerador.comando_pg_restore("postgresql+psycopg://gda:x@db:5432/gda", "gda_copia")
    assert cmd[0] == "pg_restore" and "--no-owner" in cmd and "--clean" in cmd
    assert cmd[cmd.index("-d") + 1] == "gda_copia"


def test_pg_dump_com_erro_levanta_com_a_mensagem(monkeypatch):
    class R:
        returncode, stdout, stderr = 1, b"", b"pg_dump: erro de conexao"
    monkeypatch.setattr(gerador.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(gerador.ErroBackup, match="erro de conexao"):
        gerador.gerar_dump("postgresql+psycopg://gda:x@db/gda")


def test_pg_dump_ausente_da_mensagem_clara(monkeypatch):
    def falta(*a, **k):
        raise FileNotFoundError("pg_dump")
    monkeypatch.setattr(gerador.subprocess, "run", falta)
    with pytest.raises(gerador.ErroBackup, match="pg_dump"):
        gerador.gerar_dump("postgresql+psycopg://gda:x@db/gda")


# ------------------------------------------------------------------ SQLite (dev e testes)
def _abrir_dump_sqlite(dados: bytes, destino: Path) -> sqlite3.Connection:
    destino.write_bytes(gzip.decompress(dados))
    return sqlite3.connect(destino)


def test_dump_sqlite_traz_os_dados_e_nao_traz_os_backups(tmp_path):
    url = get_settings().database_url
    service.executar_backup("diario", hoje=date(2026, 11, 10))  # já existe 1 backup na tabela
    dump = gerador.gerar_dump(url)
    con = _abrir_dump_sqlite(dump.dados, tmp_path / "copia.db")
    assert dump.formato == "sqlite_gzip"
    assert con.execute("select count(*) from usuario").fetchone()[0] == 4
    assert con.execute("select count(*) from backup_copia").fetchone()[0] == 0
    con.close()


# ------------------------------------------------------------------ execução dos backups
def _copias(tipo=None):
    with SessionLocal() as db:
        return BackupDao(db).listar(tipo)


def test_backup_diario_grava_cifrado_com_integridade(tmp_path):
    c = service.executar_backup("diario", hoje=date(2026, 11, 10))
    assert (c.tipo, c.referencia, c.situacao) == ("diario", "2026-11-10", "ok")
    assert c.tamanho_bytes and c.concluido_em and c.erro is None
    with SessionLocal() as db:
        guardada = BackupDao(db).com_conteudo(c.id)
        dump = decrypt_bytes(guardada.conteudo)
    assert regras.sha256(dump) == c.sha256
    con = _abrir_dump_sqlite(dump, tmp_path / "x.db")
    assert con.execute("select count(*) from usuario").fetchone()[0] == 4
    con.close()


def test_backup_mensal_referencia_o_mes_que_terminou():
    c = service.executar_backup("mensal", hoje=date(2026, 11, 1))
    assert (c.tipo, c.referencia, c.situacao) == ("mensal", "2026-10", "ok")
    assert c.expira_em - c.iniciado_em >= timedelta(days=364)


def test_executar_duas_vezes_a_mesma_referencia_nao_duplica():
    a = service.executar_backup("diario", hoje=date(2026, 11, 10))
    b = service.executar_backup("diario", hoje=date(2026, 11, 10))
    assert a.id == b.id and len(_copias("diario")) == 1


def test_falha_vira_registro_de_erro_e_a_tentativa_seguinte_reaproveita(monkeypatch):
    def quebra(url):
        raise gerador.ErroBackup("disco cheio")
    monkeypatch.setattr(service, "gerar_dump", quebra)
    c = service.executar_backup("diario", hoje=date(2026, 11, 10))  # não levanta: o worker segue
    assert c.situacao == "erro" and "disco cheio" in c.erro and c.conteudo is None
    monkeypatch.undo()
    d = service.executar_backup("diario", hoje=date(2026, 11, 10))
    assert d.id == c.id and d.situacao == "ok" and d.erro is None
    assert len(_copias("diario")) == 1


# ------------------------------------------------------------------ retenção
def test_limpeza_libera_o_conteudo_dos_vencidos_e_mantem_os_validos():
    agora = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)
    velho = service.executar_backup("diario", hoje=date(2026, 11, 10))   # vence em 17/11
    novo = service.executar_backup("diario", hoje=date(2026, 11, 19))    # vence em 26/11
    mensal = service.executar_backup("mensal", hoje=date(2026, 11, 1))   # vence só em 2027
    with SessionLocal() as db:
        dao = BackupDao(db)
        for c in (velho, novo):  # datas de validade coerentes com a data de referência
            obj = dao.obter(BackupCopia, c.id)
            obj.expira_em = regras.expira_em("diario", datetime.fromisoformat(
                c.referencia).replace(tzinfo=UTC))
            dao.save_generic(obj)
        dao.commit()
    assert service.limpar_vencidos(agora) == 1
    ativos = {c.referencia for c in _copias()}
    assert ativos == {novo.referencia, mensal.referencia}
    with SessionLocal() as db:  # a linha fica (exclusão lógica), mas o arquivo é liberado
        linha = db.get(BackupCopia, velho.id)
        assert linha.deleted is True and linha.conteudo is None


def test_apos_expirar_a_referencia_pode_ser_gerada_de_novo():
    c = service.executar_backup("diario", hoje=date(2026, 11, 10))
    with SessionLocal() as db:
        obj = BackupDao(db).obter(BackupCopia, c.id)
        obj.expira_em = datetime(2020, 1, 1, tzinfo=UTC)
        BackupDao(db).save_generic(obj)
        BackupDao(db).commit()
    service.limpar_vencidos(datetime(2026, 11, 11, tzinfo=UTC))
    novo = service.executar_backup("diario", hoje=date(2026, 11, 10))
    assert novo.id != c.id and novo.situacao == "ok"


# ------------------------------------------------------------------ exportação
def test_exportar_decifra_e_confere_a_integridade(tmp_path):
    c = service.executar_backup("diario", hoje=date(2026, 11, 10))
    saida = tmp_path / "copia.db"
    service.exportar(c.id, saida)
    con = sqlite3.connect(saida)
    assert con.execute("select count(*) from usuario").fetchone()[0] == 4
    con.close()


def test_exportar_recusa_backup_corrompido(tmp_path):
    c = service.executar_backup("diario", hoje=date(2026, 11, 10))
    with SessionLocal() as db:
        obj = BackupDao(db).obter(BackupCopia, c.id)
        obj.sha256 = "0" * 64
        BackupDao(db).save_generic(obj)
        BackupDao(db).commit()
    with pytest.raises(service.ErroBackup, match="integridade"):
        service.exportar(c.id, tmp_path / "x.db")


def test_exportar_backup_inexistente_ou_expirado(tmp_path):
    with pytest.raises(service.ErroBackup, match="não encontrado"):
        service.exportar(9999, tmp_path / "x.db")


def test_restaurar_no_proprio_banco_exige_confirmacao(monkeypatch):
    monkeypatch.setattr(service, "gerar_dump",
                        lambda url: gerador.Dump(b"dump", "pg_dump_custom"))
    c = service.executar_backup("diario", hoje=date(2026, 11, 10))
    monkeypatch.setattr(service, "_url_do_banco", lambda: "postgresql+psycopg://gda:x@db/gda")
    with pytest.raises(service.ErroBackup, match="sobrescrever"):
        service.restaurar(c.id, "gda")


# ------------------------------------------------------------------ agenda do worker
def test_worker_agenda_diario_mensal_e_limpeza():
    modulo = next(m for m in load_modules() if m.name == "backup")
    crons = {j.id: j.cron for j in modulo.jobs}
    assert crons["diario"] == "0 0 * * *"      # 00:00, todos os dias
    assert crons["mensal"] == "0 0 1 * *"      # 00:00 do dia 1: fecha o mês que terminou
    assert "limpeza" in crons
    assert modulo.router is None                # sem interface por enquanto
