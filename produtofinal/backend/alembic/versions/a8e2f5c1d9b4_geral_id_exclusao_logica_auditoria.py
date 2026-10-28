"""geral: id em todas as tabelas, exclusão lógica e auditoria

Revision ID: a8e2f5c1d9b4
Revises: f6c3a8d2b1e7
Create Date: 2026-10-22 10:00:00.000000

ADR-0019. Em TODAS as tabelas:
- `deleted` (exclusão lógica; false nos registros existentes) e a auditoria `created`/`created_id`
  e `changed`/`changed_id`. `created`/`changed` vêm de `created_at`/`updated_at` (removidas) ou,
  sem elas, do registro de data da própria tabela (log, coleta, uso de IA, decisão) ou do momento
  da migração. `created_id`/`changed_id` ficam nulos (autoria anterior desconhecida = sistema).
- chave primária `id` inteira: `parametro` (era `chave`), `ia_vinculo_tarefa` (era `tarefa`),
  `acesso_usuario_papel` e `acesso_papel_permissao` (eram chaves compostas). A chave antiga vira
  índice único.
- todo campo único passa a ser único só entre os registros ativos (índice parcial
  `WHERE NOT deleted`): e-mail, código do papel, nome do perfil de IA, nome do PDA (também sem
  diferenciar maiúsculas), PDA vigente, id_ckan, chave do parâmetro, tarefa de IA, associações.

`recurso.created` (data de criação do recurso no CKAN) passa a se chamar `created_ckan`, pois
`created` agora é a auditoria.

O downgrade é recusado se houver registro excluído logicamente (ele voltaria a existir).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8e2f5c1d9b4'
down_revision: Union[str, Sequence[str], None] = 'f6c3a8d2b1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ATIVOS = sa.text("NOT deleted")

# tabela → coluna de data que vira created/changed (None = momento da migração)
TABELAS = {
    "acesso_log": "ocorrido_em", "acesso_papel": "created_at", "acesso_papel_permissao": None,
    "acesso_usuario_papel": None, "coleta": "iniciada_em", "dataset": None,
    "dataset_snapshot": None, "ia_perfil_provedor": "created_at", "ia_uso": "momento",
    "ia_vinculo_tarefa": "created_at", "lgpd_achado": "created_at", "lgpd_correcao": "created_at",
    "lgpd_decisao": "momento", "organizacao": None, "parametro": "created_at",
    "pda_base_prevista": "created_at", "pda_plano": "created_at", "recurso": None,
    "usuario": "created_at",
}
COM_TIMESTAMP = [t for t, c in TABELAS.items() if c == "created_at"]

# tabela → (colunas da chave antiga, que viram índice único; índices das FKs)
NOVO_ID = {
    "parametro": (["chave"], []),
    "ia_vinculo_tarefa": (["tarefa"], []),
    "acesso_usuario_papel": (["usuario_id", "papel_id"], ["usuario_id", "papel_id"]),
    "acesso_papel_permissao": (["papel_id", "permissao"], ["papel_id"]),
}

# índice parcial → (tabela, colunas, restrição/índice antigo a remover, tipo do antigo)
UNICOS = {
    "uq_acesso_papel_codigo": ("acesso_papel", ["codigo"], "constraint"),
    "uq_ia_perfil_provedor_nome": ("ia_perfil_provedor", ["nome"], "constraint"),
    "uq_organizacao_id_ckan": ("organizacao", ["id_ckan"], "constraint"),
    "uq_dataset_id_ckan": ("dataset", ["id_ckan"], "constraint"),
    "uq_recurso_id_ckan": ("recurso", ["id_ckan"], "constraint"),
    "uq_pda_plano_nome": ("pda_plano", ["nome"], "constraint"),
}


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _indice_parcial(nome: str, tabela: str, colunas, where=ATIVOS) -> None:
    op.create_index(nome, tabela, colunas, unique=True, postgresql_where=where,
                    sqlite_where=where)


def _sequencia(tabela: str) -> None:
    """No PostgreSQL a coluna `id` nova precisa de sequência (no SQLite, INTEGER PRIMARY KEY já é
    autoincremento)."""
    if _postgres():
        op.execute(f"CREATE SEQUENCE {tabela}_id_seq OWNED BY {tabela}.id")
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN id SET DEFAULT nextval('{tabela}_id_seq')")
        op.execute(f"SELECT setval('{tabela}_id_seq', COALESCE(MAX(id), 0) + 1, false) "
                   f"FROM {tabela}")


def upgrade() -> None:
    bind = op.get_bind()

    # 0) Índices de pda_plano que o SQLite perde ao recriar a tabela em lote (expressão/parcial):
    #    saem agora e voltam, já só entre os ativos, no fim
    op.execute("DROP INDEX IF EXISTS uq_pda_plano_nome_ci")
    op.execute("DROP INDEX IF EXISTS uq_pda_plano_vigente")
    # recurso.created (data de criação do recurso no CKAN) vira created_ckan: `created` passa a
    # ser a auditoria
    with op.batch_alter_table("recurso", schema=None) as batch_op:
        batch_op.alter_column("created", new_column_name="created_ckan",
                              existing_type=sa.DateTime(timezone=True), existing_nullable=True)

    # 1) exclusão lógica e auditoria em todas as tabelas
    for tabela in TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("deleted", sa.Boolean(), nullable=False,
                                          server_default=sa.false()))
            batch_op.add_column(sa.Column("created", sa.DateTime(timezone=True), nullable=False,
                                          server_default=sa.func.current_timestamp()))
            batch_op.add_column(sa.Column("created_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("changed", sa.DateTime(timezone=True), nullable=False,
                                          server_default=sa.func.current_timestamp()))
            batch_op.add_column(sa.Column("changed_id", sa.Integer(), nullable=True))
    for tabela, coluna in TABELAS.items():
        if coluna == "created_at":
            bind.execute(sa.text(f"UPDATE {tabela} SET created = created_at, changed = updated_at"))
        elif coluna:
            bind.execute(sa.text(f"UPDATE {tabela} SET created = {coluna}, changed = {coluna}"))
    for tabela in COM_TIMESTAMP:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_column("created_at")
            batch_op.drop_column("updated_at")

    # 2) chave primária `id` onde a chave era outra (lotes separados: exigência do SQLite)
    for tabela, (chave, indices_fk) in NOVO_ID.items():
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("id_novo", sa.Integer(), nullable=True))
        linhas = bind.execute(sa.text(
            f"SELECT {', '.join(chave)} FROM {tabela} ORDER BY {', '.join(chave)}")).all()
        if linhas:
            cond = " AND ".join(f"{c} = :{c}" for c in chave)
            bind.execute(sa.text(f"UPDATE {tabela} SET id_novo = :n WHERE {cond}"),
                         [{"n": n, **dict(zip(chave, linha))}
                          for n, linha in enumerate(linhas, start=1)])
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.alter_column("id_novo", existing_type=sa.Integer(), nullable=False)
            batch_op.drop_constraint(f"pk_{tabela}", type_="primary")
            batch_op.create_primary_key(f"pk_{tabela}", ["id_novo"])
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.alter_column("id_novo", new_column_name="id", existing_type=sa.Integer())
        _sequencia(tabela)
        _indice_parcial(f"uq_{tabela}_{'_'.join(chave)}", tabela, chave)
        for coluna in indices_fk:
            op.create_index(f"ix_{tabela}_{coluna}", tabela, [coluna], unique=False)

    # 3) campos únicos passam a valer só entre os ativos
    for nome, (tabela, colunas, _tipo) in UNICOS.items():
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_constraint(nome, type_="unique")
        _indice_parcial(nome, tabela, colunas)
    op.drop_index("ix_usuario_email", table_name="usuario")
    _indice_parcial("uq_usuario_email", "usuario", ["email"])
    # Por último: as recriações de pda_plano em lote (SQLite) descartariam estes índices
    _indice_parcial("uq_pda_plano_nome_ci", "pda_plano", [sa.text("lower(nome)")])
    _indice_parcial("uq_pda_plano_vigente", "pda_plano", ["vigente"],
                    where=sa.text("vigente AND NOT deleted"))


def downgrade() -> None:
    bind = op.get_bind()
    for tabela in TABELAS:
        if bind.execute(sa.text(f"SELECT COUNT(*) FROM {tabela} WHERE deleted")).scalar():
            raise RuntimeError(f"Downgrade impossível: {tabela} tem registros excluídos "
                               "logicamente (voltariam a existir).")

    # 3) únicos voltam a valer para todos (os de pda_plano são recriados no fim, como no upgrade)
    op.execute("DROP INDEX IF EXISTS uq_pda_plano_vigente")
    op.execute("DROP INDEX IF EXISTS uq_pda_plano_nome_ci")
    op.drop_index("uq_usuario_email", table_name="usuario")
    op.create_index("ix_usuario_email", "usuario", ["email"], unique=True)
    for nome, (tabela, colunas, _tipo) in UNICOS.items():
        op.drop_index(nome, table_name=tabela)
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.create_unique_constraint(nome, colunas)

    # 2) chave antiga volta a ser a primária
    for tabela, (chave, indices_fk) in NOVO_ID.items():
        for coluna in indices_fk:
            op.drop_index(f"ix_{tabela}_{coluna}", table_name=tabela)
        op.drop_index(f"uq_{tabela}_{'_'.join(chave)}", table_name=tabela)
        if _postgres():
            op.execute(f"ALTER TABLE {tabela} ALTER COLUMN id DROP DEFAULT")
            op.execute(f"DROP SEQUENCE IF EXISTS {tabela}_id_seq")
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_constraint(f"pk_{tabela}", type_="primary")
            batch_op.create_primary_key(f"pk_{tabela}", chave)
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_column("id")

    # 1) sem auditoria; created_at/updated_at voltam onde existiam
    for tabela in COM_TIMESTAMP:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        bind.execute(sa.text(f"UPDATE {tabela} SET created_at = created, updated_at = changed"))
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.alter_column("created_at", existing_type=sa.DateTime(timezone=True),
                                  nullable=False)
            batch_op.alter_column("updated_at", existing_type=sa.DateTime(timezone=True),
                                  nullable=False)
    for tabela in TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            for coluna in ("changed_id", "changed", "created_id", "created", "deleted"):
                batch_op.drop_column(coluna)
    with op.batch_alter_table("recurso", schema=None) as batch_op:
        batch_op.alter_column("created_ckan", new_column_name="created",
                              existing_type=sa.DateTime(timezone=True), existing_nullable=True)
    op.create_index("uq_pda_plano_vigente", "pda_plano", ["vigente"], unique=True,
                    postgresql_where=sa.text("vigente"), sqlite_where=sa.text("vigente"))
    op.create_index("uq_pda_plano_nome_ci", "pda_plano", [sa.text("lower(nome)")], unique=True)
