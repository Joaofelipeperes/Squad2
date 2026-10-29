"""inventario: chave primária própria e id_ckan

Revision ID: f6c3a8d2b1e7
Revises: e5b2c7a9d1f4
Create Date: 2026-10-21 10:00:00.000000

ADR-0018: `organizacao`, `dataset` e `recurso` deixam de usar o ID do CKAN como chave primária.
Cada tabela ganha `id` inteiro próprio (autoincremento) e o ID do CKAN passa para `id_ckan`
(único, opcional). Todas as chaves estrangeiras que apontavam para o ID do CKAN passam a apontar
para o `id` próprio; `dataset_snapshot.dataset_id` (referência lógica, sem FK) também.

Os dados são preservados: os ids são numerados na ordem do ID do CKAN e cada referência é
traduzida pelo par (id_ckan → id). Fotografias de dataset que não existe mais no inventário (não
deveria haver: datasets não são apagados) são descartadas, pois não há id para elas.
O downgrade só é possível se todo registro tiver `id_ckan` (registros criados sem CKAN impedem).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6c3a8d2b1e7'
down_revision: Union[str, Sequence[str], None] = 'e5b2c7a9d1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PAIS = ("organizacao", "dataset", "recurso")
# (tabela, coluna, tabela referenciada, nullable, tem FK, tem índice)
FILHOS = (
    ("dataset", "organizacao_id", "organizacao", True, True, True),
    ("recurso", "dataset_id", "dataset", False, True, True),
    ("usuario", "orgao_id", "organizacao", True, True, False),
    ("pda_base_prevista", "organizacao_id", "organizacao", True, True, True),
    ("pda_base_prevista", "dataset_id", "dataset", True, True, True),
    ("lgpd_achado", "recurso_id", "recurso", False, True, True),
    ("lgpd_correcao", "recurso_id", "recurso", False, True, True),
    ("dataset_snapshot", "dataset_id", "dataset", False, False, True),
)


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _trocar_coluna_filha(tabela: str, coluna: str, pai: str, nullable: bool, tem_fk: bool,
                         tem_indice: bool, temporaria: str, tipo_antigo, tipo_novo) -> None:
    """Troca `coluna` pela `temporaria` já preenchida (a FK é recriada depois, em `_criar_fks`).
    Lotes separados: no SQLite, apagar, renomear para o mesmo nome e indexar no mesmo lote falha."""
    with op.batch_alter_table(tabela, schema=None) as batch_op:
        if tem_fk:
            batch_op.drop_constraint(f"fk_{tabela}_{coluna}_{pai}", type_="foreignkey")
        if tem_indice:
            batch_op.drop_index(f"ix_{tabela}_{coluna}")
        batch_op.drop_column(coluna)
    with op.batch_alter_table(tabela, schema=None) as batch_op:
        batch_op.alter_column(temporaria, new_column_name=coluna, existing_type=tipo_novo,
                              nullable=nullable)
    if tem_indice:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.create_index(f"ix_{tabela}_{coluna}", [coluna], unique=False)


def _criar_fks(coluna_pai: str) -> None:
    for tabela, coluna, pai, _nullable, tem_fk, _indice in FILHOS:
        if tem_fk:
            with op.batch_alter_table(tabela, schema=None) as batch_op:
                batch_op.create_foreign_key(f"fk_{tabela}_{coluna}_{pai}", pai, [coluna],
                                            [coluna_pai])


def upgrade() -> None:
    bind = op.get_bind()

    # 1) colunas novas, ainda opcionais
    for pai in PAIS:
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.add_column(sa.Column("id_novo", sa.Integer(), nullable=True))
    for tabela, coluna, *_ in FILHOS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column(f"{coluna}_novo", sa.Integer(), nullable=True))

    # 2) numeração própria e tradução das referências (id_ckan → id)
    for pai in PAIS:
        chaves = bind.execute(sa.text(f"SELECT ckan_id FROM {pai} ORDER BY ckan_id")).scalars()
        valores = [{"n": n, "k": k} for n, k in enumerate(chaves, start=1)]
        if valores:
            bind.execute(sa.text(f"UPDATE {pai} SET id_novo = :n WHERE ckan_id = :k"), valores)
    for tabela, coluna, pai, *_ in FILHOS:
        bind.execute(sa.text(
            f"UPDATE {tabela} SET {coluna}_novo = "
            f"(SELECT p.id_novo FROM {pai} p WHERE p.ckan_id = {tabela}.{coluna})"))
    bind.execute(sa.text("DELETE FROM dataset_snapshot WHERE dataset_id_novo IS NULL"))

    # 3) referências passam a ser inteiras (antes de mexer nas chaves primárias referenciadas)
    for tabela, coluna, pai, nullable, tem_fk, tem_indice in FILHOS:
        _trocar_coluna_filha(tabela, coluna, pai, nullable, tem_fk, tem_indice,
                             f"{coluna}_novo", sa.String(length=64), sa.Integer())

    # 4) chave primária própria; o ID do CKAN vira id_ckan (único, opcional)
    for pai in PAIS:
        # Lotes separados (SQLite): trocar a PK, depois renomear, depois a unicidade
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.alter_column("id_novo", existing_type=sa.Integer(), nullable=False)
            batch_op.drop_constraint(f"pk_{pai}", type_="primary")
            batch_op.create_primary_key(f"pk_{pai}", ["id_novo"])
            batch_op.alter_column("ckan_id", existing_type=sa.String(length=64), nullable=True)
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.alter_column("ckan_id", new_column_name="id_ckan",
                                  existing_type=sa.String(length=64))
            batch_op.alter_column("id_novo", new_column_name="id", existing_type=sa.Integer())
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.create_unique_constraint(f"uq_{pai}_id_ckan", ["id_ckan"])
        if _postgres():  # no SQLite, INTEGER PRIMARY KEY já é autoincremento (rowid)
            op.execute(f"CREATE SEQUENCE {pai}_id_seq OWNED BY {pai}.id")
            op.execute(f"ALTER TABLE {pai} ALTER COLUMN id SET DEFAULT nextval('{pai}_id_seq')")
            op.execute(f"SELECT setval('{pai}_id_seq', COALESCE(MAX(id), 0) + 1, false) "
                       f"FROM {pai}")

    # 5) chaves estrangeiras para o id próprio
    _criar_fks("id")


def downgrade() -> None:
    bind = op.get_bind()
    for pai in PAIS:
        sem_ckan = bind.execute(sa.text(f"SELECT COUNT(*) FROM {pai} WHERE id_ckan IS NULL"))
        if sem_ckan.scalar():
            raise RuntimeError(f"Downgrade impossível: há registros em {pai} sem id_ckan.")

    # 1) referências voltam a guardar o ID do CKAN
    for tabela, coluna, pai, *_ in FILHOS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column(f"{coluna}_ckan", sa.String(length=64), nullable=True))
        bind.execute(sa.text(
            f"UPDATE {tabela} SET {coluna}_ckan = "
            f"(SELECT p.id_ckan FROM {pai} p WHERE p.id = {tabela}.{coluna})"))
    for tabela, coluna, pai, nullable, tem_fk, tem_indice in FILHOS:
        _trocar_coluna_filha(tabela, coluna, pai, nullable, tem_fk, tem_indice,
                             f"{coluna}_ckan", sa.Integer(), sa.String(length=64))

    # 2) o ID do CKAN volta a ser a chave primária
    for pai in PAIS:
        if _postgres():
            op.execute(f"ALTER TABLE {pai} ALTER COLUMN id DROP DEFAULT")
            op.execute(f"DROP SEQUENCE IF EXISTS {pai}_id_seq")
        # Lotes separados (SQLite), como no upgrade
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.drop_constraint(f"uq_{pai}_id_ckan", type_="unique")
            batch_op.alter_column("id_ckan", existing_type=sa.String(length=64), nullable=False)
            batch_op.drop_constraint(f"pk_{pai}", type_="primary")
            batch_op.create_primary_key(f"pk_{pai}", ["id_ckan"])
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.drop_column("id")
        with op.batch_alter_table(pai, schema=None) as batch_op:
            batch_op.alter_column("id_ckan", new_column_name="ckan_id",
                                  existing_type=sa.String(length=64))

    _criar_fks("ckan_id")
