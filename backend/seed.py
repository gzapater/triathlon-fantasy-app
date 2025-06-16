import os
from flask import Flask
from backend.models import db, Role, RaceFormat, Segment, QuestionType

# --- Begin: Functions moved from app.py ---
def create_initial_roles(app):
    with app.app_context():
        roles_data = [
            {'code': 'ADMIN', 'description': 'Administrador'},
            {'code': 'LEAGUE_ADMIN', 'description': 'Admin de Liga'},
            {'code': 'PLAYER', 'description': 'Jugador'}
        ]
        for role_info in roles_data:
            role = Role.query.filter_by(code=role_info['code']).first()
            if not role:
                new_role = Role(code=role_info['code'], description=role_info['description'])
                db.session.add(new_role)
                print(f"Role '{role_info['description']}' with code '{role_info['code']}' created.")
            else:
                print(f"Role '{role_info['description']}' with code '{role_info['code']}' already exists.")
        try:
            db.session.commit()
            print("Initial roles check and creation complete.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing initial roles: {e}")

def create_initial_race_data(app):
    with app.app_context():
        race_formats_data = ["Triatlón", "Duatlón", "Acuatlón"]
        segments_data = ["Natación", "Ciclismo", "Carrera a pie", "Transición 1 (T1)", "Transición 2 (T2)"]

        for name in race_formats_data:
            if not RaceFormat.query.filter_by(name=name).first():
                db.session.add(RaceFormat(name=name))
                print(f"RaceFormat '{name}' created.")
            else:
                print(f"RaceFormat '{name}' already exists.")

        for name in segments_data:
            if not Segment.query.filter_by(name=name).first():
                db.session.add(Segment(name=name))
                print(f"Segment '{name}' created.")
            else:
                print(f"Segment '{name}' already exists.")

        try:
            if db.session.new:
                db.session.commit()
                print("Initial race data seeding complete.")
            else:
                print("Initial race data already exists or no new data was added. No commit needed for race data.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing initial race data: {e}")

def create_initial_question_types(app):
    with app.app_context():
        default_question_types = [
            {"name": "FREE_TEXT"},
            {"name": "MULTIPLE_CHOICE"},
            {"name": "ORDERING"},
            {"name": "SLIDER"} # Added SLIDER type
        ]

        for qt_data in default_question_types:
            qt = QuestionType.query.filter_by(name=qt_data["name"]).first()
            if not qt:
                new_qt = QuestionType(name=qt_data["name"])
                db.session.add(new_qt)
                print(f"Created question type: {new_qt.name}")
            else:
                print(f"QuestionType '{qt_data['name']}' already exists.")

        try:
            if db.session.new:
                db.session.commit()
                print("Initial question types seeding complete.")
            else:
                print("Initial question types already exist or no new data was added. No commit needed for question types.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing initial question types: {e}")
# --- End: Functions moved from app.py ---

if __name__ == '__main__':
    # Create a minimal Flask app instance for the seeding script
    # This is necessary for the db operations to work with application context
    # It should match the configuration of your main app for database URI
    print("Starting database seeding process...")
    temp_app = Flask(__name__)

    # Configuration for the temporary app
    # Ensure these environment variables are set in your execution environment
    db_uri = os.environ.get('DATABASE_URL')
    if not db_uri:
        raise ValueError("DATABASE_URL environment variable not set. Cannot initialize database for seeding.")

    temp_app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    temp_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Optional: silence a warning

    db.init_app(temp_app) # Initialize db with the temporary app

    print("Flask app initialized for seeding.")

    # Execute seeding functions
    create_initial_roles(temp_app)
    create_initial_race_data(temp_app)
    create_initial_question_types(temp_app)

    print("Database seeding process finished.")
