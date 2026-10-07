#!/usr/bin/env python3
"""Garante a regra de decisões do CLAUDE.md (ADR-0015).

    python scripts/checar_decisoes.py              # valida a estrutura das ADRs e a linha do tempo
    python scripts/checar_decisoes.py --staged     # + exige ADR quando dependência/infra muda (hook)
    python scripts/checar_decisoes.py --base main  # idem, comparando com outro ramo (PR/CI)

Sem dependências externas: roda com python3 puro.
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ADR = RAIZ / "docs/adr"

# Mudança nestes arquivos é decisão técnica: exige ADR nova ou linha em "Revisões" no mesmo commit.
EXIGEM_DECISAO = [
    "backend/pyproject.toml",
    "frontend/package.json",
    "docker-compose.yml",
    "backend/Dockerfile",
    "frontend/Dockerfile",
    "frontend/nginx.conf",
    "backend/alembic/env.py",
    "backend/app/core/db.py",
    "backend/app/core/security.py",
    "backend/app/core/crypto.py",
]

CAMPOS = ["Status", "Tipo", "Data da decisão", "Data do registro", "Decisores", "Apoio de IA",
          "Origem"]
SECOES = ["Contexto", "Opções consideradas", "Decisão", "Consequências", "Revisões"]
_ARQ = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")


def validar_estrutura() -> list[str]:
    erros: list[str] = []
    indice = (ADR / "README.md").read_text(encoding="utf-8")
    numeros: dict[str, str] = {}
    for arq in sorted(ADR.glob("*.md")):
        if arq.name in ("README.md", "_MODELO.md"):
            continue
        m = _ARQ.match(arq.name)
        if not m:
            erros.append(f"{arq.name}: nome fora do padrão NNNN-titulo-curto.md")
            continue
        num = m.group(1)
        if num in numeros:
            erros.append(f"{arq.name}: número {num} repetido ({numeros[num]})")
        numeros[num] = arq.name
        texto = arq.read_text(encoding="utf-8")
        if not texto.startswith(f"# ADR-{num} — "):
            erros.append(f"{arq.name}: o título deve começar com '# ADR-{num} — '")
        for campo in CAMPOS:
            if not re.search(rf"^\| \*\*{re.escape(campo)}\*\* \| *\S", texto, re.M):
                erros.append(f"{arq.name}: campo '{campo}' ausente ou vazio")
        for secao in SECOES:
            if not re.search(rf"^## {re.escape(secao)}", texto, re.M):
                erros.append(f"{arq.name}: seção '## {secao}' ausente")
        if texto.count("**Prós:**") < 2:
            erros.append(f"{arq.name}: registre ao menos duas opções com prós e contras")
        if f"({arq.name})" not in indice:
            erros.append(f"{arq.name}: falta na linha do tempo (docs/adr/README.md)")
    return erros


def arquivos_alterados(argv: list[str]) -> list[str]:
    if "--base" in argv:
        cmd = ["git", "diff", "--name-only", f"{argv[argv.index('--base') + 1]}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
    saida = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    return [linha for linha in saida.splitlines() if linha]


def main() -> int:
    erros = validar_estrutura()
    if "--staged" in sys.argv or "--base" in sys.argv:
        alterados = arquivos_alterados(sys.argv[1:])
        sensiveis = [a for a in alterados if a in EXIGEM_DECISAO]
        adr_mudou = any(a.startswith("docs/adr/") and a.endswith(".md") for a in alterados)
        if sensiveis and not adr_mudou:
            erros.append("Dependência ou infraestrutura alterada sem registro de decisão: "
                         + ", ".join(sensiveis)
                         + ". Crie uma ADR (docs/adr/_MODELO.md) ou acrescente uma linha em "
                           "'Revisões' da ADR relacionada, e atualize docs/adr/README.md.")
    if erros:
        print("Registro de decisões incompleto (regra do CLAUDE.md, ADR-0015):")
        for e in erros:
            print(f"  - {e}")
        print("\nPara pular conscientemente: git commit --no-verify")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
