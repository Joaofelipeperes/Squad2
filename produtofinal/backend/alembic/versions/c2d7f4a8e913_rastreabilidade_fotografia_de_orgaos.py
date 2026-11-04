"""rastreabilidade: fotografia de órgãos e eventos de órgão

Revision ID: c2d7f4a8e913
Revises: b8e4c1f07d25
Create Date: 2026-10-23 10:00:00.000000

A extensão de auditoria não registra alterações no cadastro dos órgãos (descrição, imagem,
campos extras). Esta migração cria `rastreabilidade_orgao_snapshot` (fotografia de cada órgão,
gravada só quando muda) e prepara `rastreabilidade_evento` para eventos de órgão:
`origem` (auditoria_ckan | comparacao_coletas), `orgao_snapshot_id` e `ckan_activity_id`,
`dataset_id` e `dataset_titulo` passam a aceitar vazio. Eventos já gravados ficam com
origem auditoria_ckan. `rastreabilidade_sincronizacao` ganha `orgaos_consultados`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d7f4a8e913'
down_revision: Union[str, Sequence[str], None] = 'b8e4c1f07d25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('rastreabilidade_orgao_snapshot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organizacao_id', sa.String(length=64), nullable=False),
    sa.Column('capturado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('hash_conteudo', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rastreabilidade_orgao_snapshot'))
    )
    with op.batch_alter_table('rastreabilidade_orgao_snapshot', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rastreabilidade_orgao_snapshot_organizacao_id'),
                              ['organizacao_id'], unique=False)

    with op.batch_alter_table('rastreabilidade_evento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('origem', sa.String(length=30), nullable=False,
                                      server_default='auditoria_ckan'))
        batch_op.add_column(sa.Column('orgao_snapshot_id', sa.Integer(), nullable=True))
        batch_op.alter_column('ckan_activity_id', existing_type=sa.VARCHAR(length=64),
                              nullable=True)
        batch_op.alter_column('dataset_id', existing_type=sa.VARCHAR(length=64), nullable=True)
        batch_op.alter_column('dataset_titulo', existing_type=sa.VARCHAR(length=500),
                              nullable=True)
        batch_op.create_unique_constraint(
            batch_op.f('uq_rastreabilidade_evento_orgao_snapshot_id'), ['orgao_snapshot_id'])
        batch_op.create_foreign_key(
            batch_op.f('fk_rastreabilidade_evento_orgao_snapshot_id_rastreabilidade_orgao_snapshot'),
            'rastreabilidade_orgao_snapshot', ['orgao_snapshot_id'], ['id'])

    with op.batch_alter_table('rastreabilidade_sincronizacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('orgaos_consultados', sa.Integer(), nullable=False,
                                      server_default='0'))


def downgrade() -> None:
    # eventos de órgão não cabem no esquema anterior (sem dataset)
    op.execute("DELETE FROM rastreabilidade_evento WHERE origem = 'comparacao_coletas'")
    with op.batch_alter_table('rastreabilidade_sincronizacao', schema=None) as batch_op:
        batch_op.drop_column('orgaos_consultados')

    with op.batch_alter_table('rastreabilidade_evento', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_rastreabilidade_evento_orgao_snapshot_id_rastreabilidade_orgao_snapshot'),
            type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('uq_rastreabilidade_evento_orgao_snapshot_id'),
                                 type_='unique')
        batch_op.alter_column('dataset_titulo', existing_type=sa.VARCHAR(length=500),
                              nullable=False)
        batch_op.alter_column('dataset_id', existing_type=sa.VARCHAR(length=64), nullable=False)
        batch_op.alter_column('ckan_activity_id', existing_type=sa.VARCHAR(length=64),
                              nullable=False)
        batch_op.drop_column('orgao_snapshot_id')
        batch_op.drop_column('origem')

    with op.batch_alter_table('rastreabilidade_orgao_snapshot', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rastreabilidade_orgao_snapshot_organizacao_id'))
    op.drop_table('rastreabilidade_orgao_snapshot')
