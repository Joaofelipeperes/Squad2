"""rastreabilidade: eventos da auditoria do CKAN

Revision ID: 56cbf1b07f2c
Revises: e5b2c7a9d1f4
Create Date: 2026-10-21 20:12:04.061610

Cria `rastreabilidade_evento` (uma linha por atividade da auditoria do CKAN, extensão
ckanext-dsaudit — ADR-0009) e `rastreabilidade_sincronizacao` (cada leitura da auditoria).
Tabelas somente inserção; `dataset_id` e `organizacao_id` sem FK (histórico).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56cbf1b07f2c'
down_revision: Union[str, Sequence[str], None] = 'e5b2c7a9d1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('rastreabilidade_evento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ckan_activity_id', sa.String(length=64), nullable=False),
    sa.Column('ocorrido_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tipo', sa.String(length=30), nullable=False),
    sa.Column('activity_type', sa.String(length=40), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('dataset_titulo', sa.String(length=500), nullable=False),
    sa.Column('organizacao_id', sa.String(length=64), nullable=True),
    sa.Column('recurso_id', sa.String(length=64), nullable=True),
    sa.Column('recurso_nome', sa.String(length=500), nullable=True),
    sa.Column('usuario', sa.String(length=200), nullable=True),
    sa.Column('resumo', sa.Text(), nullable=False),
    sa.Column('detalhes', sa.JSON(), nullable=False),
    sa.Column('sincronizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rastreabilidade_evento')),
    sa.UniqueConstraint('ckan_activity_id', name=op.f('uq_rastreabilidade_evento_ckan_activity_id'))
    )
    with op.batch_alter_table('rastreabilidade_evento', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rastreabilidade_evento_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_rastreabilidade_evento_ocorrido_em'), ['ocorrido_em'], unique=False)
        batch_op.create_index(batch_op.f('ix_rastreabilidade_evento_organizacao_id'), ['organizacao_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_rastreabilidade_evento_tipo'), ['tipo'], unique=False)

    op.create_table('rastreabilidade_sincronizacao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('iniciada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finalizada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('datasets_consultados', sa.Integer(), nullable=False),
    sa.Column('datasets_sem_permissao', sa.Integer(), nullable=False),
    sa.Column('datasets_nao_encontrados', sa.Integer(), nullable=False),
    sa.Column('eventos_novos', sa.Integer(), nullable=False),
    sa.Column('erro', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rastreabilidade_sincronizacao'))
    )


def downgrade() -> None:
    op.drop_table('rastreabilidade_sincronizacao')
    with op.batch_alter_table('rastreabilidade_evento', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rastreabilidade_evento_tipo'))
        batch_op.drop_index(batch_op.f('ix_rastreabilidade_evento_organizacao_id'))
        batch_op.drop_index(batch_op.f('ix_rastreabilidade_evento_ocorrido_em'))
        batch_op.drop_index(batch_op.f('ix_rastreabilidade_evento_dataset_id'))

    op.drop_table('rastreabilidade_evento')
