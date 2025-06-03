"""seed_initial_roles

Revision ID: <ID_AUTO_GENERADO_POR_ALEMBIC>
Revises: 0001 # Asegúrate que este es el ID de tu migración anterior (la que creó las tablas)
Create Date: <FECHA_AUTO_GENERADA>

"""
from alembic import op
import sqlalchemy as sa

# Definición de la tabla 'roles' para usarla con op.bulk_insert y op.execute
# Esto es útil porque no importamos los modelos de Flask directamente en las migraciones.
roles_table = sa.table('roles',
    sa.column('name', sa.String)
    # No necesitamos definir 'id' aquí si es autoincremental y no lo especificamos en la inserción.
)

# revision identifiers, used by Alembic.
revision = '0002' # No cambies esto, Alembic lo pone.
down_revision = '0001' # ¡IMPORTANTE! Asegúrate que este es el ID de tu migración anterior (0001_initial_roles_users_setup.py)
branch_labels = None
depends_on = None


def upgrade():
    """Seed initial roles into the roles table."""
    op.bulk_insert(roles_table,
        [
            {'name': 'admin'},
            {'name': 'admin de liga'},
            {'name': 'jugador'}
        ]
    )

def downgrade():
    """Remove the initial roles from the roles table."""
    # Opción 1: Usando el helper de tabla de SQLAlchemy (más portable)
    op.execute(
        roles_table.delete().where(roles_table.c.name.in_([
            'admin',
            'admin de liga',
            'jugador'
        ]))
    )
    # Opción 2: Usando SQL directo (más simple si no te preocupa la portabilidad entre bases de datos para esto)
    # op.execute("DELETE FROM roles WHERE name IN ('admin', 'admin de liga', 'jugador')")
