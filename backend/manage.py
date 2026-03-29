import os
import click
from flask.cli import FlaskGroup
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables from .flaskenv in the parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.flaskenv')
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from {dotenv_path}")
    load_dotenv(dotenv_path)

from backend.app import app, db
from backend import seed

# Set environment variables if not already set
if 'DATABASE_URL' not in os.environ:
    print("Warning: DATABASE_URL not set in environment. Attempting to use a default or development URL.")
    # For development, you might set a default here, e.g:
    # os.environ['DATABASE_URL'] = 'sqlite:///../instance/app_dev.db'
    # However, it's better to require it to be set externally.

if 'FLASK_SECRET_KEY' not in os.environ:
    print("Warning: FLASK_SECRET_KEY not set in environment. Using a temporary unsafe key for script execution.")
    os.environ['FLASK_SECRET_KEY'] = 'temp_secret_key_for_cli'

migrate = Migrate(app, db)

@click.group(cls=FlaskGroup, create_app=lambda: app)
def cli():
    """Main entry point for the Flask CLI."""
    pass

@cli.command('seed_data')
# Removed: @click.pass_app_context
def seed_data():
    """Runs the database seeding scripts."""
    print("Starting database seeding...")
    seed.create_initial_roles(app)
    seed.create_initial_race_data(app)
    seed.create_initial_question_types(app)
    print("Database seeding finished.")

if __name__ == '__main__':
    cli()
