"""add empresas table

Revision ID: 804be1084c09
Revises: 
Create Date: 2025-06-12 13:49:02.473805

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '804be1084c09'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela empresas (se essa parte estiver no mesmo arquivo)
    op.create_table(
        'empresas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cnpj', sa.String(length=18), unique=True, nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('caminho_banco', sa.String(length=255), nullable=False),
        sa.Column('data_cadastro', sa.DateTime(), nullable=True),
        sa.Column('ativa', sa.Boolean(), nullable=True, default=True)
    )

    # Atualizar coluna 'tipo' da tabela categorias para não aceitar NULL
    with op.batch_alter_table('categorias', schema=None) as batch_op:
        # Passo 1: Atualizar valores NULL para valor padrão (ex: 'default')
        categorias = table('categorias',
            column('tipo', String)
        )
        batch_op.execute(
            categorias.update().where(categorias.c.tipo == None).values(tipo='default')
        )
        # Passo 2: Alterar coluna para NOT NULL
        batch_op.alter_column('tipo',
            existing_type=sa.String(length=50),
            nullable=False
        )

def downgrade():
    with op.batch_alter_table('categorias', schema=None) as batch_op:
        batch_op.alter_column('tipo',
            existing_type=sa.String(length=50),
            nullable=True
        )
    op.drop_table('empresas')