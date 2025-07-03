"""create_league_and_league_races_tables

Revision ID: 43904c745596  # Este ID será el que te genere Alembic
Revises: a1b2c3d4e5f6      # Este ID será el de tu migración anterior
Create Date: 2025-07-01 20:27:48.003479

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43904c745596'  # Reemplaza con el tuyo
down_revision = 'a1b2c3d4e5f6' # Reemplaza con el tuyo
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Comandos para la actualización ###

    # 1. Crear la tabla 'leagues'
    op.create_table('leagues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_leagues_id'), 'leagues', ['id'], unique=False)
    op.create_index(op.f('ix_leagues_name'), 'leagues', ['name'], unique=False)

    # 2. Crear la tabla de unión 'league_races'
    op.create_table('league_races',
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('race_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ),
        sa.ForeignKeyConstraint(['race_id'], ['races.id'], ),
        sa.PrimaryKeyConstraint('league_id', 'race_id')
    )

    # ### Fin de los comandos ###


def downgrade() -> None:
    # ### Comandos para la reversión (en orden inverso) ###

    # 1. Eliminar la tabla de unión 'league_races'
    op.drop_table('league_races')

    # 2. Eliminar la tabla 'leagues'
    op.drop_index(op.f('ix_leagues_name'), table_name='leagues')
    op.drop_index(op.f('ix_leagues_id'), table_name='leagues')
    op.drop_table('leagues')

    # ### Fin de los comandos ###
