"""add google_sub to users

Revision ID: b1d5e4a7c2f1
Revises: 3e3e685925e0
Create Date: 2026-03-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1d5e4a7c2f1'
down_revision = '3e3e685925e0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.create_unique_constraint('uq_users_google_sub', 'users', ['google_sub'])


def downgrade():
    op.drop_constraint('uq_users_google_sub', 'users', type_='unique')
    op.drop_column('users', 'google_sub')
