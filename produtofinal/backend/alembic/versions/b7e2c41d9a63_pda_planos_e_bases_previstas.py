"""pda: planos (vários PDAs, um vigente) e colunas da planilha nas bases previstas

Revision ID: b7e2c41d9a63
Revises: 9da707016405
Create Date: 2026-10-07 10:00:00.000000

- cria `pda_plano` com o índice único parcial `uq_pda_plano_vigente` (no máximo um vigente);
- `pda_base_prevista` ganha `plano_id` (FK ON DELETE CASCADE, NOT NULL), as colunas lidas da
  planilha do PDA e `organizacao_id`; `orgao_sigla` passa a 100 caracteres e `periodicidade`
  (normalizada) passa a NOT NULL.

Dados: `pda_base_prevista` estava vazia em todos os ambientes (o módulo era só esqueleto). Mesmo
assim, linhas órfãs (sem plano) são APAGADAS antes de `plano_id` virar NOT NULL — uma base
prevista sem o PDA de origem não tem significado. O downgrade também apaga as bases previstas,
pois elas deixam de ter o plano que as identifica.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2c41d9a63'
down_revision: Union[str, Sequence[str], None] = '9da707016405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pda_plano',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('vigencia_inicio', sa.Date(), nullable=True),
    sa.Column('vigencia_fim', sa.Date(), nullable=True),
    sa.Column('vigente', sa.Boolean(), nullable=False),
    sa.Column('arquivo_nome', sa.String(length=300), nullable=True),
    sa.Column('importado_por', sa.String(length=200), nullable=True),
    sa.Column('importado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('total_bases', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pda_plano')),
    sa.UniqueConstraint('nome', name=op.f('uq_pda_plano_nome'))
    )
    with op.batch_alter_table('pda_plano', schema=None) as batch_op:
        batch_op.create_index('uq_pda_plano_vigente', ['vigente'], unique=True,
                              postgresql_where=sa.text('vigente'),
                              sqlite_where=sa.text('vigente'))

    # 1) novas colunas (plano_id ainda anulável)
    with op.batch_alter_table('pda_base_prevista', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plano_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('organizacao_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('descricao', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('unidade_responsavel', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('periodicidade_original', sa.String(length=100),
                                      nullable=True))
        batch_op.add_column(sa.Column('politicas_publicas', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('possui_conteudo_sigiloso', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('dataset_name_planilha', sa.String(length=200),
                                      nullable=True))
        batch_op.add_column(sa.Column('linha_planilha', sa.Integer(), nullable=True))

    # 2) linhas órfãs (sem PDA de origem) são apagadas — a tabela estava vazia (ver docstring)
    op.execute(sa.text('DELETE FROM pda_base_prevista WHERE plano_id IS NULL'))

    # 3) restrições: plano_id NOT NULL + FKs + índices; orgao_sigla 100; periodicidade NOT NULL
    with op.batch_alter_table('pda_base_prevista', schema=None) as batch_op:
        batch_op.alter_column('plano_id', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('orgao_sigla', existing_type=sa.VARCHAR(length=40),
                              type_=sa.String(length=100), existing_nullable=False)
        batch_op.alter_column('periodicidade', existing_type=sa.VARCHAR(length=40),
                              nullable=False)
        batch_op.create_index(batch_op.f('ix_pda_base_prevista_plano_id'), ['plano_id'],
                              unique=False)
        batch_op.create_index(batch_op.f('ix_pda_base_prevista_organizacao_id'),
                              ['organizacao_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_pda_base_prevista_plano_id_pda_plano'),
                                    'pda_plano', ['plano_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key(
            batch_op.f('fk_pda_base_prevista_organizacao_id_organizacao'),
            'organizacao', ['organizacao_id'], ['ckan_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # As bases previstas dependem do plano de origem; sem `pda_plano` elas são descartadas.
    op.execute(sa.text('DELETE FROM pda_base_prevista'))
    with op.batch_alter_table('pda_base_prevista', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_pda_base_prevista_organizacao_id_organizacao'),
                                 type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_pda_base_prevista_plano_id_pda_plano'),
                                 type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_pda_base_prevista_organizacao_id'))
        batch_op.drop_index(batch_op.f('ix_pda_base_prevista_plano_id'))
        batch_op.alter_column('periodicidade', existing_type=sa.VARCHAR(length=40),
                              nullable=True)
        batch_op.alter_column('orgao_sigla', existing_type=sa.String(length=100),
                              type_=sa.VARCHAR(length=40), existing_nullable=False)
        batch_op.drop_column('linha_planilha')
        batch_op.drop_column('dataset_name_planilha')
        batch_op.drop_column('possui_conteudo_sigiloso')
        batch_op.drop_column('politicas_publicas')
        batch_op.drop_column('periodicidade_original')
        batch_op.drop_column('unidade_responsavel')
        batch_op.drop_column('descricao')
        batch_op.drop_column('organizacao_id')
        batch_op.drop_column('plano_id')

    with op.batch_alter_table('pda_plano', schema=None) as batch_op:
        batch_op.drop_index('uq_pda_plano_vigente',
                            postgresql_where=sa.text('vigente'),
                            sqlite_where=sa.text('vigente'))

    op.drop_table('pda_plano')
