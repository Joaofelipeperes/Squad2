"""Verificações das regras do CLAUDE.md que podem ser automatizadas."""
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
