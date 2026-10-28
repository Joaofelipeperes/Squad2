"""pda: ID do dataset no CKAN informado na planilha

Revision ID: b9d4e6f2a7c1
Revises: a8e2f5c1d9b4
Create Date: 2026-10-23 10:00:00.000000

Acrescenta `pda_base_prevista.dataset_id_ckan_planilha` (varchar(64), opcional): o ID do dataset
no CKAN lido da planilha do PDA (coluna "ID_UNICO") ou digitado no formulário. Com o dataset no
inventário, a base é vinculada na importação (`dataset_id`); sem ele, o vínculo fica pendente e é
resolvido pelo ID em "Atualizar vínculos". Bases já importadas ficam com a coluna vazia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9d4e6f2a7c1'
down_revision: Union[str, Sequence[str], None] = 'a8e2f5c1d9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('pda_base_prevista', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dataset_id_ckan_planilha', sa.String(length=64),
                                      nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('pda_base_prevista', schema=None) as batch_op:
        batch_op.drop_column('dataset_id_ckan_planilha')
