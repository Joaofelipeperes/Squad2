"""rastreabilidade: marca das atividades nativas lidas

Revision ID: d5e1a9c3b742
Revises: c2d7f4a8e913
Create Date: 2026-10-23 12:00:00.000000

Ações que não passam pela edição auditada pela extensão (Make public/Make private/Delete em lote
na página da organização, package_patch) só deixam a atividade nativa do CKAN. A sincronização
passa a lê-las e grava como evento as que não têm registro correspondente da extensão
(origem `atividade_nativa`, sem coluna nova em `rastreabilidade_evento`).
`rastreabilidade_sincronizacao.atividades_nativas_ate` marca até quando elas já foram lidas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e1a9c3b742'
down_revision: Union[str, Sequence[str], None] = 'c2d7f4a8e913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('rastreabilidade_sincronizacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('atividades_nativas_ate', sa.DateTime(timezone=True),
                                      nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM rastreabilidade_evento WHERE origem = 'atividade_nativa'")
    with op.batch_alter_table('rastreabilidade_sincronizacao', schema=None) as batch_op:
        batch_op.drop_column('atividades_nativas_ate')
