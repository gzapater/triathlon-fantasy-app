"""add_code_and_description_to_roles_table

Revision ID: <ID_NUEVO_GENERADO_POR_ALEMBIC> # Alembic lo pone, no lo cambies
Revises: '0002' # O el ID correcto de tu migración anterior _seed_initial_roles
Create Date: <FECHA_AUTO_GENERADA>

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4057948044a4' # Alembic lo pone
down_revision = '0002' # ¡VERIFICA QUE ESTE SEA EL ID DE TU MIGRACIÓN ANTERIOR!
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Rename 'name' to 'code'
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column('name', new_column_name='code',
                              existing_type=sa.String(length=80),
                              existing_nullable=False,
                              existing_unique=True) # name was unique

    # Step 2: Update values in the new 'code' column (original values were 'admin', 'admin de liga', 'jugador')
    op.execute("UPDATE roles SET code = 'ADMIN' WHERE code = 'admin'")
    op.execute("UPDATE roles SET code = 'LEAGUE_ADMIN' WHERE code = 'admin de liga'")
    op.execute("UPDATE roles SET code = 'PLAYER' WHERE code = 'jugador'")

    # Step 3: Add 'description' column (temporarily nullable)
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(length=255), nullable=True))

    # Step 4: Populate 'description' column (using final 'code' values)
    op.execute("UPDATE roles SET description = 'Administrador General' WHERE code = 'ADMIN'")
    op.execute("UPDATE roles SET description = 'Admin de Liga' WHERE code = 'LEAGUE_ADMIN'")
    op.execute("UPDATE roles SET description = 'Jugador' WHERE code = 'PLAYER'")

    # Step 5: Make 'description' non-nullable
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column('description', existing_type=sa.String(length=255), nullable=False)


def downgrade():
    # Step 1: Make 'description' nullable again
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column('description', existing_type=sa.String(length=255), nullable=True)

    # Step 2: Remove 'description' column
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_column('description')

    # Step 3: Revert 'code' values if they were changed (assuming they were ADMIN, LEAGUE_ADMIN, PLAYER)
    op.execute("UPDATE roles SET code = 'admin' WHERE code = 'ADMIN'")
    op.execute("UPDATE roles SET code = 'admin de liga' WHERE code = 'LEAGUE_ADMIN'")
    op.execute("UPDATE roles SET code = 'jugador' WHERE code = 'PLAYER'")

    # Step 4: Rename 'code' back to 'name'
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column('code', new_column_name='name',
                              existing_type=sa.String(length=80),
                              existing_nullable=False,
                              existing_unique=True) # name should be unique again
