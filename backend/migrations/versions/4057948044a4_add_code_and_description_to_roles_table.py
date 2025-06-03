"""add_code_and_description_to_roles_table

Revision ID: <ID_NUEVO_GENERADO_POR_ALEMBIC> # Alembic lo pone, no lo cambies
Revises: '0002' # O el ID correcto de tu migración anterior _seed_initial_roles
Create Date: <FECHA_AUTO_GENERADA>

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '<ID_NUEVO_GENERADO_POR_ALEMBIC>' # Alembic lo pone
down_revision = '0002' # ¡VERIFICA QUE ESTE SEA EL ID DE TU MIGRACIÓN ANTERIOR!
branch_labels = None
depends_on = None


def upgrade():
    # Es posible que Alembic haya intentado autogenerar parte de esto.
    # Compara y ajusta según sea necesario.

    # 1. Renombrar la columna 'name' a 'code'
    # Si Alembic ya generó esto, verifica que sea similar.
    op.alter_column('roles', 'name', new_column_name='code',
                    existing_type=sa.String(length=80),
                    existing_nullable=False)
                    # Alembic podría añadir más existing_... parámetros, lo cual está bien.

    # 2. (Opcional) Actualizar los valores en la nueva columna 'code' para que sean más "códigos"
    # Si quieres que tus códigos sean 'ADMIN', 'LEAGUE_ADMIN', 'PLAYER'
    op.execute("UPDATE roles SET code = 'ADMIN' WHERE code = 'admin'")
    op.execute("UPDATE roles SET code = 'LEAGUE_ADMIN' WHERE code = 'admin de liga'")
    op.execute("UPDATE roles SET code = 'PLAYER' WHERE code = 'jugador'")
    # Si los dejas como 'admin', 'admin de liga', 'jugador', omite estos UPDATEs.

    # 3. Añadir la nueva columna 'description'
    # Si Alembic ya generó esto, verifica que sea similar.
    op.add_column('roles', sa.Column('description', sa.String(length=255), nullable=True)) # Temporalmente nullable

    # 4. Poblar la columna 'description' para los roles existentes
    # Asegúrate de que los WHERE clauses usen los valores FINALES de la columna 'code'
    op.execute("UPDATE roles SET description = 'Administrador General' WHERE code = 'ADMIN'") # o 'admin'
    op.execute("UPDATE roles SET description = 'Admin de Liga' WHERE code = 'LEAGUE_ADMIN'")   # o 'admin de liga'
    op.execute("UPDATE roles SET description = 'Jugador' WHERE code = 'PLAYER'")             # o 'jugador'

    # 5. Hacer la columna 'description' no nullable (si así lo definiste en tu modelo)
    op.alter_column('roles', 'description', existing_type=sa.String(length=255), nullable=False)


def downgrade():
    # Revertir los cambios en orden inverso

    # 1. (Opcional) Hacer la columna 'description' nullable de nuevo si la hiciste non-nullable
    op.alter_column('roles', 'description', existing_type=sa.String(length=255), nullable=True)

    # 2. Eliminar la columna 'description'
    op.drop_column('roles', 'description')

    # 3. (Opcional) Revertir los valores de 'code' a los nombres originales si los cambiaste en el upgrade.
    op.execute("UPDATE roles SET code = 'admin' WHERE code = 'ADMIN'")
    op.execute("UPDATE roles SET code = 'admin de liga' WHERE code = 'LEAGUE_ADMIN'")
    op.execute("UPDATE roles SET code = 'jugador' WHERE code = 'PLAYER'")

    # 4. Renombrar la columna 'code' de nuevo a 'name'
    op.alter_column('roles', 'code', new_column_name='name',
                    existing_type=sa.String(length=80),
                    existing_nullable=False)
