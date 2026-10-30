"""ckan_config: perfis de conexão do CKAN (ADR-0024)

Revision ID: f1a2b3c4d5e6
Revises: e7a4c2f9b315
Create Date: 2026-10-30 19:00:00.000000

Tabela dos perfis de conexão do CKAN (tela Configurações CKAN). Um perfil fica `selecionado` e
rege todo o sistema, sobrepondo o `.env`. Trocar o perfil não mexe nos dados já coletados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e7a4c2f9b315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ATIVOS = sa.text("NOT deleted")


def upgrade() -> None:
    op.create_table(
        "ckan_perfil",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("created_id", sa.Integer(), nullable=True),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("changed_id", sa.Integer(), nullable=True),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("auditoria_base_url", sa.String(length=500), nullable=True),
        sa.Column("auditoria_api_token_cifrada", sa.Text(), nullable=True),
        sa.Column("auditoria_api_token_dica", sa.String(length=20), nullable=True),
        sa.Column("selecionado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ckan_perfil")),
    )
    op.create_index("uq_ckan_perfil_nome", "ckan_perfil", ["nome"], unique=True,
                    postgresql_where=ATIVOS, sqlite_where=ATIVOS)


def downgrade() -> None:
    op.drop_index("uq_ckan_perfil_nome", table_name="ckan_perfil")
    op.drop_table("ckan_perfil")
