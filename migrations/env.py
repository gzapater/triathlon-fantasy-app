# --- INICIO DEL FICHERO env.py CORREGIDO ---

import os
import sys
import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context

# 1. ARREGLAR LA RUTA DE BÚSQUEDA PRIMERO
# ==========================================
# Añade el directorio raíz del proyecto al sys.path para que Python encuentre 'backend'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# 2. AHORA SÍ, IMPORTAR LA APP Y LOS MODELOS
# ============================================
from backend.app import app
from backend.models import db


# 3. CONFIGURACIÓN DE ALEMBIC
# ==============================
# Obtener el objeto de configuración de Alembic
config = context.config

# Configurar el logging desde el fichero .ini
# alembic.ini is in the project root, env.py is in migrations/
# So, the path to alembic.ini from env.py is '../alembic.ini'
alembic_ini_actual_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'alembic.ini'))

if os.path.exists(alembic_ini_actual_path):
    fileConfig(alembic_ini_actual_path)
else:
    # This case should ideally not happen if alembic.ini is present at the project root.
    print(f"Error: alembic.ini not found at the expected path: {alembic_ini_actual_path}. Logging will not be configured from .ini.")
    # Fallback to use config.config_file_name if provided, but this was problematic.
    # if config.config_file_name:
    #     try:
    #         fileConfig(config.config_file_name)
    #     except FileNotFoundError:
    #         print(f"Error: Also failed to load alembic.ini from config.config_file_name: {config.config_file_name}")
    #         pass
logger = logging.getLogger('alembic.env')

# Establecer el target_metadata para que autogenerate detecte los cambios
target_metadata = db.metadata


# 4. FUNCIONES HELPER (Tus funciones originales, ahora funcionarán cuando se llamen desde un app_context)
# ====================================================================================================
def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine

def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')

def get_metadata():
    if hasattr(db, 'metadatas'):
        return db.metadatas[None]
    return db.metadata


# 5. FUNCIONES DE EJECUCIÓN DE MIGRACIÓN (Tu código original, ahora funcionará)
# =================================================================================
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Para el modo offline, configuramos la URL directamente desde el alembic.ini
    # o desde la configuración de la app, que es más seguro.
    with app.app_context():
        url = config.get_main_option("sqlalchemy.url", app.config.get('SQLALCHEMY_DATABASE_URI'))
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    with app.app_context():
        # db.create_all() # REMOVED: This was causing conflicts with migrations.

        def process_revision_directives(context, revision, directives):
            if getattr(config.cmd_opts, 'autogenerate', False):
                script = directives[0]
                if script.upgrade_ops.is_empty():
                    directives[:] = []
                    logger.info('No changes in schema detected.')

        conf_args = current_app.extensions['migrate'].configure_args
        if conf_args.get("process_revision_directives") is None:
            conf_args["process_revision_directives"] = process_revision_directives

        connectable = get_engine()

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=get_metadata(),
                **conf_args
            )
            with context.begin_transaction():
                context.run_migrations()

# 6. BLOQUE DE EJECUCIÓN FINAL
# ===============================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# --- FIN DEL FICHERO ---
