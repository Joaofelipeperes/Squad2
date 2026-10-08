#!/usr/bin/env python3
"""Gera docs/banco/mer.md (Modelo Entidade-Relacionamento) a partir dos modelos SQLAlchemy.

    python scripts/gerar_mer.py           # (re)gera o arquivo
    python scripts/gerar_mer.py --check   # falha se estiver desatualizado (hook / testes)

O MER é DERIVADO do código: não edite docs/banco/mer.md à mão. Para mudar o texto de uma tabela,
altere a docstring do modelo; para mudar a estrutura, altere o modelo e crie a migração.
Requer as dependências do backend (rode com o Python do ambiente virtual do backend).
"""
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "docs/banco/mer.md"
sys.path.insert(0, str(RAIZ / "backend"))

try:
    from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String, Text

    import app.integrations.ai  # noqa: F401
    from app.core.db import Base
    from app.modules import INSTALLED_MODULES, import_all_models
except ImportError as exc:  # sem o ambiente virtual do backend
    if "--check" in sys.argv:
        print(f"Aviso: MER não verificado ({exc.name} ausente). Use o Python de backend/.venv; "
              "os testes do backend também verificam o MER.")
        sys.exit(0)
    raise

import_all_models()

# Referências sem chave estrangeira, mantidas de propósito (ver docs/banco/convencoes.md).
# O gerador valida que tabela e coluna existem: renomear sem atualizar aqui quebra o --check.
REFERENCIAS_LOGICAS = [
    ("dataset_snapshot", "dataset_id", "dataset", "ckan_id", True,
     "Fotografia histórica: sem FK para não depender do estado atual do dataset."),
    ("ia_uso", "perfil_id", "ia_perfil_provedor", "id", True,
     "Registro de uso sobrevive à exclusão do perfil (o nome fica em perfil_nome)."),
    ("coleta", "solicitada_por", "usuario", "email", False, "Autoria congelada como e-mail."),
    ("lgpd_decisao", "usuario", "usuario", "email", False, "Autoria congelada como e-mail."),
    ("lgpd_correcao", "aprovado_por", "usuario", "email", False, "Autoria congelada como e-mail."),
    ("ia_vinculo_tarefa", "alterado_por", "usuario", "email", False, "Autoria congelada como e-mail."),
    ("parametro", "alterado_por", "usuario", "email", False, "Autoria congelada como e-mail."),
]
# (origem, coluna, destino, coluna destino, desenhar no diagrama?, observação)

_TIPOS = [(Boolean, "bool"), (DateTime, "datetime"), (Date, "date"), (Float, "float"),
          (Integer, "int"), (Text, "text"), (String, "varchar"), (JSON, "json")]

NOME_MODULO = {
    "acesso": "Acesso (usuários e papéis)", "inventario": "Inventário CKAN", "pda": "PDA",
    "lgpd": "LGPD", "ia": "Modelos de IA", "parametros": "Parâmetros",
}


def tipo(col) -> tuple[str, str]:
    """(tipo curto para o diagrama, tipo detalhado para o dicionário)."""
    for cls, nome in _TIPOS:
        if isinstance(col.type, cls):
            tam = getattr(col.type, "length", None)
            return nome, f"{nome}({tam})" if tam else nome
    return "other", str(col.type)


def modulo_da_tabela() -> dict[str, str]:
    mapa = {m.local_table.name: m.class_.__module__.split(".")[2] for m in Base.registry.mappers}
    for nome in Base.metadata.tables:  # tabelas de associação (sem classe)
        if nome not in mapa:
            mapa[nome] = next((m for m in INSTALLED_MODULES if nome.startswith(m + "_")), "outros")
    return mapa


def descricao(tabela) -> str:
    for m in Base.registry.mappers:
        if m.local_table is tabela:
            return " ".join((m.class_.__doc__ or "").split()) or "—"
    # ordem das colunas (tabela.foreign_keys é um set: ordem varia entre execuções)
    fks = [fk.column.table.name for c in tabela.columns for fk in c.foreign_keys]
    if len(fks) == 2 and all(c.primary_key for c in tabela.columns):
        return f"Associação N:N entre `{fks[0]}` e `{fks[1]}`."
    return "—"


def chaves(col, tabela) -> list[str]:
    k = []
    if col.primary_key:
        k.append("PK")
    if col.foreign_keys:
        k.append("FK")
    if col.unique or any(len(c.columns) == 1 and col.name in c.columns.keys()
                         for c in tabela.constraints if c.__class__.__name__ == "UniqueConstraint"):
        k.append("UK")
    return k


def relacao(fk_col, tabela) -> tuple[str, str, str]:
    """(lado do pai, lado do filho) na notação Mermaid e a cardinalidade em texto.

    Pai: `||` = exatamente um (FK obrigatória) · `|o` = zero ou um (FK opcional).
    Filho: `o{` = zero ou muitos · `o|` = zero ou um (FK única → relação 1:1).
    """
    unico = fk_col.unique or (fk_col.primary_key and len(tabela.primary_key.columns) == 1)
    pai = "|o" if fk_col.nullable else "||"
    filho = "o|" if unico else "o{"
    texto = ("0..1" if fk_col.nullable else "1") + " : " + ("0..1" if unico else "N")
    return pai, filho, texto


def validar_logicas():
    for origem, col, destino, col_dest, *_ in REFERENCIAS_LOGICAS:
        t, d = Base.metadata.tables.get(origem), Base.metadata.tables.get(destino)
        if t is None or col not in t.c or d is None or col_dest not in d.c:
            raise SystemExit(f"Referência lógica inválida: {origem}.{col} → {destino}.{col_dest}")


def gerar() -> str:
    validar_logicas()
    mapa = modulo_da_tabela()
    tabelas = sorted(Base.metadata.tables.values(),
                     key=lambda t: (INSTALLED_MODULES.index(mapa[t.name])
                                    if mapa[t.name] in INSTALLED_MODULES else 99, t.name))
    out = [
        "# MER — Modelo Entidade-Relacionamento",
        "",
        "> **Arquivo gerado** por `scripts/gerar_mer.py` a partir dos modelos SQLAlchemy.",
        "> Não edite à mão: altere o modelo (ou sua docstring), crie a migração e rode o script.",
        "> Convenções de modelagem: [convencoes.md](convencoes.md) · Decisão: "
        "[ADR-0013](../adr/0013-banco-de-dados-e-convencoes.md).",
        "",
        f"{len(tabelas)} tabelas · linhas contínuas = chave estrangeira · linhas tracejadas = "
        "referência lógica sem FK (ver tabela ao final).",
        "",
        "## Diagrama",
        "",
        "```mermaid",
        "erDiagram",
    ]
    for t in tabelas:
        out.append(f"    {t.name} {{")
        for c in t.columns:
            curto, _ = tipo(c)
            k = chaves(c, t)
            out.append(f"        {curto} {c.name}" + (f" {', '.join(k)}" if k else ""))
        out.append("    }")
    rels = []
    for t in tabelas:
        for c in t.columns:
            for fk in sorted(c.foreign_keys, key=lambda f: f.target_fullname):
                pai, filho, texto = relacao(c, t)
                rels.append((t.name, c.name, fk.column.table.name, fk.column.name, texto, "FK", ""))
                out.append(f'    {fk.column.table.name} {pai}--{filho} {t.name} : "{c.name}"')
    for origem, col, destino, col_dest, desenhar, obs in REFERENCIAS_LOGICAS:
        rels.append((origem, col, destino, col_dest, "—", "referência lógica", obs))
        if desenhar:
            out.append(f'    {destino} |o..o{{ {origem} : "{col} (lógica)"')
    out += ["```", ""]

    out += ["## Relacionamentos", "",
            "| Origem | Destino | Cardinalidade (pai : filhos) | Tipo | Observação |",
            "|---|---|---|---|---|"]
    for origem, col, destino, col_dest, card, tipo_rel, obs in rels:
        out.append(f"| `{origem}.{col}` | `{destino}.{col_dest}` | {card} | {tipo_rel} | {obs} |")
    out.append("")

    out += ["## Dicionário de dados", ""]
    por_modulo = defaultdict(list)
    for t in tabelas:
        por_modulo[mapa[t.name]].append(t)
    for mod, ts in por_modulo.items():
        out += [f"### Módulo `{mod}` — {NOME_MODULO.get(mod, mod)}",
                f"Documentação do módulo: [docs/modulos/{mod}.md](../modulos/{mod}.md)", ""]
        for t in ts:
            out += [f"#### `{t.name}`", "", descricao(t), "",
                    "| Coluna | Tipo | Nulo | Chave | Referência | Padrão |",
                    "|---|---|:-:|---|---|---|"]
            for c in t.columns:
                _, longo = tipo(c)
                ref = ", ".join(f"`{fk.target_fullname}`" for fk in c.foreign_keys)
                padrao = ""
                if c.default is not None:
                    arg = c.default.arg
                    padrao = ("função" if callable(arg) else
                              f"`{arg!r}`" if not isinstance(arg, dict) else "`{}`")
                out.append(f"| `{c.name}` | {longo} | {'sim' if c.nullable else 'não'} | "
                           f"{', '.join(chaves(c, t))} | {ref} | {padrao} |")
            idx = sorted(i.name for i in t.indexes)
            if idx:
                out += ["", "Índices: " + ", ".join(f"`{i}`" for i in idx)]
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    conteudo = gerar()
    if "--check" in sys.argv:
        atual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if atual != conteudo:
            print("docs/banco/mer.md desatualizado. Rode: python scripts/gerar_mer.py")
            return 1
        return 0
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(conteudo, encoding="utf-8")
    print(f"Gerado {DESTINO.relative_to(RAIZ)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
