"""rastreabilidade: eventos por parte da atividade e marca de diff

Revision ID: 7a3d9e2b4c61
Revises: 56cbf1b07f2c
Create Date: 2026-10-22 19:34:03.003556

Uma atividade da auditoria pode gerar mais de um evento (privação + alteração de título viram
Privação e Alteração): `sequencia` numera as partes e a unicidade passa a ser
(`ckan_activity_id`, `sequencia`). `tem_diff` marca eventos com diff linha a linha no CKAN,
buscado pela tela sob demanda. Estrutura apenas; a releitura dos eventos está na migração
seguinte (b8e4c1f07d25).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a3d9e2b4c61'
down_revision: Union[str, Sequence[str], None] = '56cbf1b07f2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('rastreabilidade_evento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sequencia', sa.Integer(), nullable=False,
                                      server_default='0'))
        batch_op.add_column(sa.Column('tem_diff', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.drop_constraint(batch_op.f('uq_rastreabilidade_evento_ckan_activity_id'),
                                 type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_rastreabilidade_evento_ckan_activity_id'),
                                          ['ckan_activity_id', 'sequencia'])


def downgrade() -> None:
    # a unicidade antiga só cabe com uma parte por atividade
    op.execute("DELETE FROM rastreabilidade_evento WHERE sequencia > 0")
    with op.batch_alter_table('rastreabilidade_evento', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_rastreabilidade_evento_ckan_activity_id'),
                                 type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_rastreabilidade_evento_ckan_activity_id'),
                                          ['ckan_activity_id'])
        batch_op.drop_column('tem_diff')
        batch_op.drop_column('sequencia')
