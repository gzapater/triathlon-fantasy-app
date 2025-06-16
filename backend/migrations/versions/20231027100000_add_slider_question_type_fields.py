"""Add slider question type fields

Revision ID: 20231027100000
Revises: ad6f31c3c99f
Create Date: 2023-10-27 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20231027100000'
down_revision = 'ad6f31c3c99f' # Set to the latest known revision
branch_labels = None
depends_on = None

def upgrade():
    # Add columns to Question table
    op.add_column('questions', sa.Column('slider_unit', sa.String(length=50), nullable=True))
    op.add_column('questions', sa.Column('slider_min_value', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('slider_max_value', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('slider_step', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('slider_points_exact', sa.Integer(), nullable=True))
    op.add_column('questions', sa.Column('slider_threshold_partial', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('slider_points_partial', sa.Integer(), nullable=True))

    # Add column to OfficialAnswer table
    op.add_column('official_answers', sa.Column('correct_slider_value', sa.Float(), nullable=True))

    # Add column to UserAnswer table
    op.add_column('user_answers', sa.Column('slider_answer_value', sa.Float(), nullable=True))

def downgrade():
    # Drop columns from UserAnswer table
    op.drop_column('user_answers', 'slider_answer_value')

    # Drop column from OfficialAnswer table
    op.drop_column('official_answers', 'correct_slider_value')

    # Drop columns from Question table
    op.drop_column('questions', 'slider_points_partial')
    op.drop_column('questions', 'slider_threshold_partial')
    op.drop_column('questions', 'slider_points_exact')
    op.drop_column('questions', 'slider_step')
    op.drop_column('questions', 'slider_max_value')
    op.drop_column('questions', 'slider_min_value')
    op.drop_column('questions', 'slider_unit')
