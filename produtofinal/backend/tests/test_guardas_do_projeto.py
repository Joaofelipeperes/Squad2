"""Verificações das regras do AGENTS.md que podem ser automatizadas."""
import re
import subprocess
import sys
from pathlib import Path

from app.core.permissoes import P
from app.modules import INSTALLED_MODULES

RAIZ = Path(__file__).resolve().parents[2]
TELAS = RAIZ / "frontend/src/modules"


def _manifestos():
    for idx in sorted(TELAS.glob("*/index.ts")):
        yield idx.parent.name, idx.read_text(encoding="utf-8")


def test_todo_modulo_backend_tem_doc():
    faltando = [m for m in INSTALLED_MODULES if not (RAIZ / f"docs/modulos/{m}.md").exists()]
    assert not faltando, f"Crie docs/modulos/<modulo>.md para: {faltando}"


def test_toda_tela_declara_modulo_existente_e_permissao_valida():
    validas = {str(p) for p in P}
    for pasta, ts in _manifestos():
        modulo = re.search(r'modulo:\s*"([a-z_]+)"', ts)
        assert modulo, f"{pasta}/index.ts sem campo modulo"
        assert modulo.group(1) in INSTALLED_MODULES, f"{pasta}: módulo {modulo.group(1)} inexistente"
        perm = re.search(r'permissao:\s*"([a-z_.]+)"', ts)
        assert perm and perm.group(1) in validas, f"{pasta}: permissão ausente ou fora do catálogo"


def test_permissoes_ts_sincronizado():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts/gerar_permissoes_ts.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def _rodar(script: str, *args: str):
    return subprocess.run([sys.executable, str(RAIZ / "scripts" / script), *args],
                          capture_output=True, text=True)


def test_mer_sincronizado_com_os_modelos():
    r = _rodar("gerar_mer.py", "--check")
    assert r.returncode == 0 and "Aviso" not in r.stdout, r.stdout


def test_todo_modelo_tem_docstring():
    from app.core.db import Base
    sem = [m.local_table.name for m in Base.registry.mappers if not (m.class_.__doc__ or "").strip()]
    assert not sem, f"Docstring obrigatória (vira a descrição no MER): {sem}"


def test_adrs_estruturadas_e_na_linha_do_tempo():
    r = _rodar("checar_decisoes.py")
    assert r.returncode == 0, r.stdout


# ---------------------------------------------------------- acesso ao banco (ADR-0019)
APP = RAIZ / "backend/app"
_METODOS_DA_SESSAO = ("execute", "scalar", "scalars", "get", "add", "add_all", "delete", "merge",
                      "flush", "commit", "rollback", "refresh", "expire_all", "query")
# `db.<método>(` / `session.<método>(` fora de um DAO = acesso direto ao banco
_ACESSO_DIRETO = re.compile(r"\b(?:db|session|sessao)\.(?:%s)\(" % "|".join(_METODOS_DA_SESSAO))


def test_banco_so_e_acessado_pelos_daos():
    """Só `core/dao.py` e os `dao.py` dos módulos falam com a sessão; o resto chama o DAO."""
    permitidos = {APP / "core/dao.py", APP / "core/db.py"}
    violacoes = []
    for arq in sorted(APP.rglob("*.py")):
        if arq in permitidos or arq.name == "dao.py":
            continue
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), start=1):
            if _ACESSO_DIRETO.search(linha.split("#", 1)[0]):
                violacoes.append(f"{arq.relative_to(APP)}:{n}: {linha.strip()}")
    assert not violacoes, "Acesso direto ao banco fora do DAO:\n" + "\n".join(violacoes)


def test_toda_tabela_tem_id_e_auditoria():
    from app.core.db import Base
    exigidas = ("id", "deleted", "created", "created_id", "changed", "changed_id")
    for tabela in Base.metadata.sorted_tables:
        faltando = [c for c in exigidas if c not in tabela.c]
        assert not faltando, f"{tabela.name} sem {faltando}"
        assert [c.name for c in tabela.primary_key.columns] == ["id"], f"{tabela.name}: PK ≠ id"
