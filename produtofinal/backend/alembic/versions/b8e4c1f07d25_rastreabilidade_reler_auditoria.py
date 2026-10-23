"""rastreabilidade: reler a auditoria com as novas regras

Revision ID: b8e4c1f07d25
Revises: 7a3d9e2b4c61
Create Date: 2026-10-22 19:40:00.000000

Migração de dados. Os eventos gravados antes de 7a3d9e2b4c61 juntavam privação e outras
mudanças num só evento e não tinham a marca de diff. Como a fonte é a auditoria do próprio CKAN
(ADR-0009), os eventos são apagados e relidos por inteiro na próxima sincronização (fim da
próxima coleta). O histórico das sincronizações é mantido.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8e4c1f07d25'
down_revision: Union[str, Sequence[str], None] = '7a3d9e2b4c61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM rastreabilidade_evento")


def downgrade() -> None:
    # nada a desfazer: a próxima sincronização relê a auditoria do CKAN
    pass
