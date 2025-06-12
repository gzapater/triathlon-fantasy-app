import os
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from backend.app import app, db  # Assuming your Flask app instance is named 'app' and db is initialized
from backend import seed # Import the seed module

# Set environment variables if not already set, especially for DATABASE_URL
# This is crucial if manage.py is run in an environment where these are not pre-configured.
# For production, these should ideally be set in the environment itself.
if 'DATABASE_URL' not in os.environ:
    print("Warning: DATABASE_URL not set in environment. Attempting to use a default or development URL.")
    # Optionally, set a default for development if appropriate, e.g.:
    # os.environ['DATABASE_URL'] = 'sqlite:///../instance/app_dev.db'
    # However, it's better to require it to be set externally.

if 'FLASK_SECRET_KEY' not in os.environ:
    print("Warning: FLASK_SECRET_KEY not set in environment. Using a temporary unsafe key for script execution.")
    os.environ['FLASK_SECRET_KEY'] = 'temp_secret_key_for_cli'


migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand) # Adds database migration commands (init, migrate, upgrade, etc.)

@manager.command
def seed_data():
    """Runs the database seeding scripts."""
    print("Starting database seeding from manage.py...")
    # The seed.py script creates its own app context, so we just call its functions.
    # However, to be consistent with Flask-Script's app context management,
    # it might be better to refactor seed.py functions to not create their own app context
    # and instead rely on the one provided by Flask-Script or the calling context.
    # For now, we will call the main execution block of seed.py if it's designed to be run directly,
    # or call its functions directly if they are importable and callable.

    # Assuming seed.py has functions like create_initial_roles, etc.
    # that expect an app instance.
    # We can use the app instance from flask_script.

    # Ensure seed functions are called within an app context
    with app.app_context():
        seed.create_initial_roles(app)
        seed.create_initial_race_data(app)
        seed.create_initial_question_types(app)
    print("Database seeding from manage.py finished.")

if __name__ == '__main__':
    manager.run()
