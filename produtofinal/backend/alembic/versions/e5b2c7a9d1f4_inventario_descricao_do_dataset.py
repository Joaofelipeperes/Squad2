"""inventario: descrição do dataset

Revision ID: e5b2c7a9d1f4
Revises: d4a1e9b7c2f3
Create Date: 2026-10-18 10:00:00.000000

Acrescenta `dataset.descricao` (texto, opcional): o `notes` do CKAN, mostrado no detalhe da tela
Datasets. Datasets já coletados ficam com a coluna vazia até a próxima coleta.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b2c7a9d1f4'
down_revision: Union[str, Sequence[str], None] = 'd4a1e9b7c2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('dataset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('descricao', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('dataset', schema=None) as batch_op:
        batch_op.drop_column('descricao')
