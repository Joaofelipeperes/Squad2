"""pda: nome do PDA único sem diferenciar maiúsculas

Revision ID: c3f8a2d15e70
Revises: b7e2c41d9a63
Create Date: 2026-10-08 08:00:00.000000

Cria o índice único `uq_pda_plano_nome_ci` em `lower(nome)`. O serviço já recusava nomes
repetidos sem diferenciar maiúsculas, mas só por uma consulta prévia: duas importações
simultâneas ("PDA 2026" e "pda 2026") passavam as duas. Com o índice, a segunda vira 409.

Dados: os PDAs já cadastrados não têm nomes repetidos sem diferenciar maiúsculas (a consulta
prévia do serviço impedia); nada é alterado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a2d15e70'
down_revision: Union[str, Sequence[str], None] = 'b7e2c41d9a63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('pda_plano', schema=None) as batch_op:
        batch_op.create_index('uq_pda_plano_nome_ci', [sa.text('lower(nome)')], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('pda_plano', schema=None) as batch_op:
        batch_op.drop_index('uq_pda_plano_nome_ci')
