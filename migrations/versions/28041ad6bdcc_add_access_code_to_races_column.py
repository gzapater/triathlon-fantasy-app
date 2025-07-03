"""add access_code to races column

Revision ID: 28041ad6bdcc
Revises: b247e33d3196
Create Date: 2025-06-25 07:30:22.170254488

"""
from alembic import op
import sqlalchemy as sa
import uuid # Import uuid for the default value if needed for population step (not used here)

# revision identifiers, used by Alembic.
revision = '28041ad6bdcc'
down_revision = '70d10090ed94' # Previous head
branch_labels = None
depends_on = None


def upgrade():
    # For PostgreSQL, which supports gen_random_uuid()
    op.add_column('races', sa.Column('access_code', sa.String(length=36), nullable=False, server_default=sa.text('gen_random_uuid()')))
    op.create_unique_constraint('uq_races_access_code', 'races', ['access_code'])

    # If needing to support SQLite for this migration step (where gen_random_uuid() isn't a server function):
    # 1. Add column as nullable
    # op.add_column('races', sa.Column('access_code', sa.String(length=36), nullable=True))
    # 2. Populate existing rows (this part is tricky with Alembic for default UUIDs without app context)
    #    A common way is to use op.execute() with SQL specific to the DB or a Python loop if models could be imported.
    #    Example placeholder for manual update:
    #    op.execute("UPDATE races SET access_code = '<some_generated_uuid>' WHERE access_code IS NULL")
    #    This would need to be done carefully for each row.
    # 3. Alter column to be non-nullable
    # op.alter_column('races', 'access_code', existing_type=sa.String(length=36), nullable=False)
    # op.create_unique_constraint('uq_races_access_code', 'races', ['access_code'])


def downgrade():
    op.drop_constraint('uq_races_access_code', 'races', type_='unique')
    op.drop_column('races', 'access_code')
