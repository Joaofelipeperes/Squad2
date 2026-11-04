"""lgpd: varredura, explicação do achado e fluxo de anonimização (US11/US12, US26)

Cria `lgpd_varredura` (já no padrão da ADR-0019: id, exclusão lógica e auditoria), acrescenta a
trilha do score em `lgpd_achado.explicacao` e amplia `lgpd_correcao` para prévia, aprovação,
publicação e reversão. Nada de valor de dado pessoal é gravado (PBI-35).

Revision ID: 9d583e5bd118
Revises: a8e2f5c1d9b4
Create Date: 2026-10-27 15:00:06.316155

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9d583e5bd118'
down_revision: str | Sequence[str] | None = 'a8e2f5c1d9b4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lgpd_varredura',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recurso_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('origem', sa.String(length=20), nullable=False),
    sa.Column('solicitada_por', sa.String(length=200), nullable=True),
    sa.Column('solicitada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('iniciada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finalizada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('linhas_analisadas', sa.Integer(), nullable=False),
    sa.Column('chamadas_ia', sa.Integer(), nullable=False),
    sa.Column('achados', sa.Integer(), nullable=False),
    sa.Column('modelo', sa.String(length=300), nullable=True),
    sa.Column('aviso', sa.Text(), nullable=True),
    sa.Column('erro', sa.Text(), nullable=True),
    sa.Column('deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
    sa.Column('created_id', sa.Integer(), nullable=True),
    sa.Column('changed', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
    sa.Column('changed_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['recurso_id'], ['recurso.id'], name=op.f('fk_lgpd_varredura_recurso_id_recurso')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lgpd_varredura'))
    )
    with op.batch_alter_table('lgpd_varredura', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lgpd_varredura_recurso_id'), ['recurso_id'], unique=False)

    with op.batch_alter_table('lgpd_achado', schema=None) as batch_op:
        batch_op.add_column(sa.Column('explicacao', sa.Text(), nullable=True))

    with op.batch_alter_table('lgpd_correcao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('solicitada_por', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('itens', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('celulas_alteradas', sa.Integer(), nullable=False,
                                      server_default='0'))
        batch_op.add_column(sa.Column('nome_arquivo', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('formato', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('hash_original', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('caminho_previa', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('justificativa', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('publicada_em', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('revertida_por', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('revertida_em', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('motivo_reversao', sa.Text(), nullable=True))
        batch_op.alter_column('caminho_backup',
               existing_type=sa.VARCHAR(length=500),
               nullable=True)
        batch_op.alter_column('aprovado_por',
               existing_type=sa.VARCHAR(length=200),
               nullable=True)
        batch_op.alter_column('aprovado_em',
               existing_type=sa.DateTime(timezone=True),
               nullable=True)



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('lgpd_correcao', schema=None) as batch_op:
        batch_op.alter_column('aprovado_em',
               existing_type=sa.DateTime(timezone=True),
               nullable=False)
        batch_op.alter_column('aprovado_por',
               existing_type=sa.VARCHAR(length=200),
               nullable=False)
        batch_op.alter_column('caminho_backup',
               existing_type=sa.VARCHAR(length=500),
               nullable=False)
        batch_op.drop_column('motivo_reversao')
        batch_op.drop_column('revertida_em')
        batch_op.drop_column('revertida_por')
        batch_op.drop_column('publicada_em')
        batch_op.drop_column('justificativa')
        batch_op.drop_column('caminho_previa')
        batch_op.drop_column('hash_original')
        batch_op.drop_column('formato')
        batch_op.drop_column('nome_arquivo')
        batch_op.drop_column('celulas_alteradas')
        batch_op.drop_column('itens')
        batch_op.drop_column('solicitada_por')

    with op.batch_alter_table('lgpd_achado', schema=None) as batch_op:
        batch_op.drop_column('explicacao')

    with op.batch_alter_table('lgpd_varredura', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lgpd_varredura_recurso_id'))

    op.drop_table('lgpd_varredura')
