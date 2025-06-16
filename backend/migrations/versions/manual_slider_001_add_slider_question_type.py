"""add_slider_question_type

Revision ID: manual_slider_001
Revises: 20250613131338
Create Date: YYYY-MM-DD HH:MM:SS.MS # Will be replaced by current timestamp

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer

# revision identifiers, used by Alembic.
revision = 'manual_slider_001'
down_revision = '20250613131338'
branch_labels = None
depends_on = None


def upgrade():
    # Define the table structure for question_types
    question_types_table = table('question_types',
        column('id', Integer),
        column('name', String)
    )

    # Check if 'SLIDER' entry already exists
    conn = op.get_bind()
    existing_slider = conn.execute(
        question_types_table.select().where(question_types_table.c.name == 'SLIDER')
    ).fetchone()

    if not existing_slider:
        op.bulk_insert(question_types_table,
            [
                {'name': 'SLIDER'}
            ]
        )
    # ### end Alembic commands ###


def downgrade():
    # Define the table structure for question_types
    question_types_table = table('question_types',
        column('name', String)
    )

    op.execute(
        question_types_table.delete().where(question_types_table.c.name == 'SLIDER')
    )
    # ### end Alembic commands ###
