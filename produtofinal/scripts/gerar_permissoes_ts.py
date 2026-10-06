#!/usr/bin/env python3
"""Gera frontend/src/shared/acesso/permissoes.gen.ts a partir de backend/app/core/permissoes.py.

    python scripts/gerar_permissoes_ts.py           # (re)gera o arquivo
    python scripts/gerar_permissoes_ts.py --check   # falha se estiver desatualizado (CI/testes)
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "frontend/src/shared/acesso/permissoes.gen.ts"
sys.path.insert(0, str(RAIZ / "backend"))

from app.core.permissoes import META, P  # noqa: E402


def gerar() -> str:
    codigos = [str(p) for p in P]
    rotulos = {str(p): META[p].rotulo for p in P}
    linhas = [
        "// ARQUIVO GERADO por scripts/gerar_permissoes_ts.py a partir de",
        "// backend/app/core/permissoes.py — NÃO EDITAR À MÃO.",
        "",
        f"export const PERMISSOES = {json.dumps(codigos, ensure_ascii=False, indent=2)} as const;",
        "",
        "export type Permissao = (typeof PERMISSOES)[number];",
        "",
        "export const ROTULOS_PERMISSAO: Record<Permissao, string> = "
        f"{json.dumps(rotulos, ensure_ascii=False, indent=2)};",
        "",
    ]
    return "\n".join(linhas)


def main() -> int:
    sem_meta = [str(p) for p in P if p not in META]
    if sem_meta:
        print(f"Permissões sem entrada em META (app/core/permissoes.py): {', '.join(sem_meta)}")
        return 1
    conteudo = gerar()
    if "--check" in sys.argv:
        atual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if atual != conteudo:
            print("permissoes.gen.ts desatualizado. Rode: python scripts/gerar_permissoes_ts.py")
            return 1
        return 0
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(conteudo, encoding="utf-8")
    print(f"Gerado {DESTINO.relative_to(RAIZ)} ({len(P)} permissões).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
