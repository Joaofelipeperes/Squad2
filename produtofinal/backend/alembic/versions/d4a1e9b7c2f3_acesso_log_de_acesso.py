"""acesso: log de acesso

Revision ID: d4a1e9b7c2f3
Revises: c3f8a2d15e70
Create Date: 2026-10-14 10:00:00.000000

Cria `acesso_log`: uma linha por requisição à API, gravada pelo middleware de `app/main.py`
(ADR-0016). Tabela somente inserção; `usuario` é o e-mail congelado, sem FK.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a1e9b7c2f3'
down_revision: Union[str, Sequence[str], None] = 'c3f8a2d15e70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('acesso_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ocorrido_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('usuario', sa.String(length=200), nullable=True),
    sa.Column('metodo', sa.String(length=10), nullable=False),
    sa.Column('caminho', sa.String(length=500), nullable=False),
    sa.Column('rota', sa.String(length=200), nullable=True),
    sa.Column('acao', sa.String(length=100), nullable=True),
    sa.Column('status_http', sa.Integer(), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_acesso_log'))
    )
    with op.batch_alter_table('acesso_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_acesso_log_ocorrido_em'), ['ocorrido_em'], unique=False)
        batch_op.create_index(batch_op.f('ix_acesso_log_usuario'), ['usuario'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('acesso_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_acesso_log_usuario'))
        batch_op.drop_index(batch_op.f('ix_acesso_log_ocorrido_em'))
    op.drop_table('acesso_log')
