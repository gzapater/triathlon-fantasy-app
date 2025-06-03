"""initial_roles_users_setup

Revision ID: 0001
Revises:
Create Date: YYYY-MM-DD HH:MM:SS.ssssss # Will be replaced by current date/time

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime # For default values

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None # This is the first migration
branch_labels = None
depends_on = None


def upgrade():
    # Create 'roles' table
    op.create_table('roles',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=80), nullable=False, unique=True)
    )

    # Create 'users' table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False, unique=True),
        sa.Column('email', sa.String(length=120), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name='fk_users_role_id')
    )
    # Note: The old 'role' enum column is not created, effectively dropping it by defining the new schema.

def downgrade():
    # Drop 'users' table first due to foreign key constraint
    op.drop_table('users')
    # Drop 'roles' table
    op.drop_table('roles')
