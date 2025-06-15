"""Add quiniela_close_date to races table

Revision ID: ad6f31c3c99f
Revises: a1b2c3d4e5f6
Create Date: 2025-06-15 22:56:38.887120
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ad6f31c3c99f'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('races', sa.Column('quiniela_close_date', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('races', 'quiniela_close_date')
