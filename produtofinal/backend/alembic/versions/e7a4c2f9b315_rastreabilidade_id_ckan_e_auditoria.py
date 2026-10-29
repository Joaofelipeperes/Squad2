"""rastreabilidade: id_ckan, exclusão lógica e auditoria (junta as duas linhas de migração)

Revision ID: e7a4c2f9b315
Revises: d5e1a9c3b742, b9d4e6f2a7c1
Create Date: 2026-10-28 10:00:00.000000

Ponto de junção entre as migrações da rastreabilidade (ADR-0009) e as da chave primária própria
(ADR-0018) e do DAO (ADR-0019), feitas em paralelo a partir de `e5b2c7a9d1f4`. Leva as tabelas da
rastreabilidade às convenções de ADR-0018/0019:
- referências ao CKAN passam a se chamar `*_id_ckan` (`dataset_id`, `organizacao_id` e
  `recurso_id` do evento; `organizacao_id` da fotografia do órgão), liberando `<entidade>_id`
  para FKs ao `id` próprio;
- `deleted` e a auditoria `created`/`created_id`/`changed`/`changed_id` (registros existentes:
  `created`/`changed` da data própria da tabela, autoria vazia = sistema);
- únicos só entre os ativos (índice parcial `WHERE NOT deleted`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a4c2f9b315'
down_revision: Union[str, Sequence[str], None] = ('d5e1a9c3b742', 'b9d4e6f2a7c1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ATIVOS = sa.text("NOT deleted")

# tabela → coluna de data que vira created/changed
TABELAS = {
    "rastreabilidade_evento": "sincronizado_em",
    "rastreabilidade_sincronizacao": "iniciada_em",
    "rastreabilidade_orgao_snapshot": "capturado_em",
}

# tabela → [(coluna antiga, coluna nova, indexada?)]
RENOMEAR = {
    "rastreabilidade_evento": [("dataset_id", "dataset_id_ckan", True),
                               ("organizacao_id", "organizacao_id_ckan", True),
                               ("recurso_id", "recurso_id_ckan", False)],
    "rastreabilidade_orgao_snapshot": [("organizacao_id", "organizacao_id_ckan", True)],
}

# restrição única antiga → (índice parcial novo, colunas)
UNICOS = {
    "uq_rastreabilidade_evento_ckan_activity_id": (
        "uq_rastreabilidade_evento_ckan_activity_id_sequencia", ["ckan_activity_id", "sequencia"]),
    "uq_rastreabilidade_evento_orgao_snapshot_id": (
        "uq_rastreabilidade_evento_orgao_snapshot_id", ["orgao_snapshot_id"]),
}


def _renomear(tabela: str, de_para: list[tuple[str, str, bool]]) -> None:
    for antiga, _nova, indexada in de_para:
        if indexada:
            op.drop_index(f"ix_{tabela}_{antiga}", table_name=tabela)
    with op.batch_alter_table(tabela, schema=None) as batch_op:
        for antiga, nova, _indexada in de_para:
            batch_op.alter_column(antiga, new_column_name=nova,
                                  existing_type=sa.String(length=64))
    for _antiga, nova, indexada in de_para:
        if indexada:
            op.create_index(f"ix_{tabela}_{nova}", tabela, [nova], unique=False)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) exclusão lógica e auditoria
    for tabela, coluna in TABELAS.items():
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("deleted", sa.Boolean(), nullable=False,
                                          server_default=sa.false()))
            batch_op.add_column(sa.Column("created", sa.DateTime(timezone=True), nullable=False,
                                          server_default=sa.func.current_timestamp()))
            batch_op.add_column(sa.Column("created_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("changed", sa.DateTime(timezone=True), nullable=False,
                                          server_default=sa.func.current_timestamp()))
            batch_op.add_column(sa.Column("changed_id", sa.Integer(), nullable=True))
        bind.execute(sa.text(f"UPDATE {tabela} SET created = {coluna}, changed = {coluna}"))

    # 2) ID do CKAN em `*_id_ckan`
    for tabela, de_para in RENOMEAR.items():
        _renomear(tabela, de_para)

    # 3) únicos só entre os ativos
    with op.batch_alter_table("rastreabilidade_evento", schema=None) as batch_op:
        for antiga in UNICOS:
            batch_op.drop_constraint(antiga, type_="unique")
    for nome, colunas in UNICOS.values():
        op.create_index(nome, "rastreabilidade_evento", colunas, unique=True,
                        postgresql_where=ATIVOS, sqlite_where=ATIVOS)


def downgrade() -> None:
    bind = op.get_bind()
    for tabela in TABELAS:
        if bind.execute(sa.text(f"SELECT COUNT(*) FROM {tabela} WHERE deleted")).scalar():
            raise RuntimeError(f"Downgrade impossível: {tabela} tem registros excluídos "
                               "logicamente (voltariam a existir).")

    for nome, _colunas in UNICOS.values():
        op.drop_index(nome, table_name="rastreabilidade_evento")
    with op.batch_alter_table("rastreabilidade_evento", schema=None) as batch_op:
        for antiga, (_nome, colunas) in UNICOS.items():
            batch_op.create_unique_constraint(antiga, colunas)

    for tabela, de_para in RENOMEAR.items():
        _renomear(tabela, [(nova, antiga, indexada) for antiga, nova, indexada in de_para])

    for tabela in TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            for coluna in ("changed_id", "changed", "created_id", "created", "deleted"):
                batch_op.drop_column(coluna)
