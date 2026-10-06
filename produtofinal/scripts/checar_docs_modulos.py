#!/usr/bin/env python3
"""Garante a regra do CLAUDE.md: alterou um módulo → atualize docs/modulos/<modulo>.md.

    python scripts/checar_docs_modulos.py --staged        # usado pelo hook de pre-commit
    python scripts/checar_docs_modulos.py --base main     # usado em PR / CI

Mapeamento de arquivos para módulos:
  backend/app/modules/<id>/...        → <id>
  frontend/src/modules/<pasta>/...    → valor de `modulo:` no index.ts da pasta
  backend/app/core/permissoes.py      → acesso (o catálogo é documentado no MODULO.md de acesso)
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_MODULO_TS = re.compile(r'modulo:\s*"([a-z_]+)"')


def modulo_da_tela(pasta: str) -> str | None:
    idx = RAIZ / "frontend/src/modules" / pasta / "index.ts"
    if not idx.exists():
        return None
    m = _MODULO_TS.search(idx.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def modulo_do_arquivo(caminho: str) -> str | None:
    partes = Path(caminho).parts
    if partes[:3] == ("backend", "app", "modules") and len(partes) > 4:
        # módulo removido ou renomeado (pasta não existe mais) não exige documentação
        return partes[3] if (RAIZ / "backend/app/modules" / partes[3]).is_dir() else None
    if partes[:3] == ("frontend", "src", "modules") and len(partes) > 4:
        return modulo_da_tela(partes[3])
    if caminho == "backend/app/core/permissoes.py":
        return "acesso"
    return None


def arquivos_alterados(argv: list[str]) -> list[str]:
    if "--base" in argv:
        base = argv[argv.index("--base") + 1]
        cmd = ["git", "diff", "--name-only", f"{base}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
    saida = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    return [linha for linha in saida.splitlines() if linha]


def main() -> int:
    alterados = arquivos_alterados(sys.argv[1:])
    docs = {Path(a).stem for a in alterados if a.startswith("docs/modulos/") and a.endswith(".md")}
    modulos = {m for a in alterados if (m := modulo_do_arquivo(a))}
    faltando = sorted(modulos - docs)
    if faltando:
        print("Módulos alterados sem atualização da documentação:")
        for m in faltando:
            print(f"  - {m}: atualize docs/modulos/{m}.md (inclua uma linha no Histórico)")
        print("\nRegra definida no CLAUDE.md. Para pular conscientemente: git commit --no-verify")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
