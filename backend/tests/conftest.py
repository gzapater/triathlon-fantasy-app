import pytest
# Removed top-level: from backend.app import app as flask_app
from backend.models import db as _db, User, Role, RaceFormat, Segment, Race, QuestionType, UserRaceRegistration, Question # Added Race, QuestionType, UserRaceRegistration, Question
from datetime import datetime
import os # Ensure os is imported

@pytest.fixture(scope='session')
def app():
    """Session-wide test Flask application."""
    # Set environment variables before importing flask_app to prevent AWS SSM calls during import
    os.environ['FLASK_SECRET_KEY'] = 'test_secret_key_for_conftest_env_v2' # V2 to ensure it's this version
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:' # Test with in-memory SQLite

    from backend.app import app as flask_app_instance # Import app here, use a distinct name
    # from backend.models import QuestionType # Import QuestionType here for the factory # No longer needed here, imported globally

    flask_app_instance.config.update({
        "TESTING": True,
        # SQLALCHEMY_DATABASE_URI is now set via DATABASE_URL env var by app's own logic
        # FLASK_SECRET_KEY is now set via FLASK_SECRET_KEY env var by app's own logic
        "LOGIN_DISABLED": False,
        "WTF_CSRF_ENABLED": False,
    })

    # Establish an application context before running the tests.
    with flask_app_instance.app_context():
        _db.create_all() # Create all tables

        # Seed initial roles if not present
        roles_data = [
            {'code': 'ADMIN', 'description': 'Administrador'},
            {'code': 'LEAGUE_ADMIN', 'description': 'Admin de Liga'},
            {'code': 'PLAYER', 'description': 'Jugador'}
        ]
        for role_info in roles_data:
            if not Role.query.filter_by(code=role_info['code']).first():
                _db.session.add(Role(code=role_info['code'], description=role_info['description']))

        # Seed initial race formats and segments
        race_formats_data = ["Triatlón", "Duatlón", "Acuatlón"]
        segments_data = ["Natación", "Ciclismo", "Carrera a pie", "Transición 1 (T1)", "Transición 2 (T2)"]

        for name in race_formats_data:
            if not RaceFormat.query.filter_by(name=name).first():
                _db.session.add(RaceFormat(name=name))

        for name in segments_data:
            if not Segment.query.filter_by(name=name).first():
                _db.session.add(Segment(name=name))

        # Seed initial question types
        question_types_data = ["FREE_TEXT", "MULTIPLE_CHOICE", "ORDERING", "SLIDER"]
        for qt_name in question_types_data:
            if not QuestionType.query.filter_by(name=qt_name).first():
                _db.session.add(QuestionType(name=qt_name))


        _db.session.commit()

        yield flask_app_instance

        # Removed upgrade() call as it was causing issues with table recreation.
        # _db.create_all() should handle schema based on models.
        # from flask_migrate import upgrade
        # upgrade()

        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(scope="function")
def db_session(app):
    """
    Provides a database session for each test, with per-test transaction rollback.
    Ensures test isolation.
    """
    with app.app_context():
        # Clean and recreate database for each test function
        _db.session.remove()
        _db.drop_all()
        _db.create_all()

        # Seed initial roles
        roles_data = [
            {'code': 'ADMIN', 'description': 'Administrador'},
            {'code': 'LEAGUE_ADMIN', 'description': 'Admin de Liga'},
            {'code': 'PLAYER', 'description': 'Jugador'}
        ]
        for role_info in roles_data:
            if not Role.query.filter_by(code=role_info['code']).first():
                _db.session.add(Role(code=role_info['code'], description=role_info['description']))

        # Seed initial race formats and segments
        race_formats_data = ["Triatlón", "Duatlón", "Acuatlón", "Standard"] # Ensure "Standard" is here
        segments_data = ["Natación", "Ciclismo", "Carrera a pie", "Transición 1 (T1)", "Transición 2 (T2)"]

        for name in race_formats_data:
            if not RaceFormat.query.filter_by(name=name).first():
                _db.session.add(RaceFormat(name=name))

        for name in segments_data:
            if not Segment.query.filter_by(name=name).first():
                _db.session.add(Segment(name=name))

        # Seed initial question types
        question_types_data = ["FREE_TEXT", "MULTIPLE_CHOICE", "ORDERING", "SLIDER"]
        for qt_name in question_types_data:
            if not QuestionType.query.filter_by(name=qt_name).first():
                _db.session.add(QuestionType(name=qt_name))

        _db.session.commit()

        yield _db.session

        _db.session.remove() # Ensure session is removed after test

@pytest.fixture(scope="function") # Uses function-scoped db_session
def new_user_factory(db_session): # db_session here will be the function-scoped one
    """Factory to create new users with specific roles."""
    def create_user(username, email, password, role_code):
        role = Role.query.filter_by(code=role_code).first()
        if not role:
            raise ValueError(f"Role with code '{role_code}' not found. Ensure it's seeded.")

        user = User(username=username, email=email, role_id=role.id, name=username.capitalize())
        user.set_password(password)
        db_session.add(user)
        db_session.commit()
        return user
    return create_user

@pytest.fixture(scope="function") # Changed from session to function
def admin_user(new_user_factory):
    return new_user_factory("admin_user", "admin@test.com", "admin_password", "ADMIN")

@pytest.fixture(scope="function") # Changed from session to function
def league_admin_user(new_user_factory):
    return new_user_factory("league_admin_user", "league_admin@test.com", "league_password", "LEAGUE_ADMIN")

@pytest.fixture(scope="function") # Changed from session to function
def player_user(new_user_factory):
    return new_user_factory("player_user", "player@test.com", "player_password", "PLAYER")

@pytest.fixture # Already function-scoped, depends on new_user_factory which is now function-scoped
def authenticated_client(client, new_user_factory):
    """Factory for creating an authenticated client with a specific role."""
    def _authenticated_client(role_code):
        username = f"{role_code.lower()}_test_user"
        email = f"{username}@example.com"
        password = "testpassword"

        # Ensure user exists (or create them)
        user = User.query.filter_by(username=username).first()
        if not user:
            user = new_user_factory(username, email, password, role_code)

        # Log in the user
        response = client.post('/api/login', json={
            'username': username,
            'password': password
        })
        if response.status_code != 200:
            raise RuntimeError(f"Failed to log in user {username}. Status: {response.status_code}, Data: {response.get_data(as_text=True)}")
        return client, user # Return both client and user object for convenience
    return _authenticated_client

@pytest.fixture
def race_creation_payload_factory(db_session):
    """Factory to generate race creation payloads."""
    def _factory(title, race_format_name, event_date_str, gender_category, segments_data, is_general_val, description=None, location=None, promo_image_url=None):
        race_format = RaceFormat.query.filter_by(name=race_format_name).first()
        if not race_format:
            # Create if not exists for test robustness, or raise error
            race_format = RaceFormat(name=race_format_name)
            db_session.add(race_format)
            db_session.commit()

        processed_segments = []
        for seg_info in segments_data: # e.g., [{"name": "Natación", "distance_km": 1.5}]
            segment = Segment.query.filter_by(name=seg_info["name"]).first()
            if not segment:
                segment = Segment(name=seg_info["name"])
                db_session.add(segment)
                db_session.commit()
            processed_segments.append({"segment_id": segment.id, "distance_km": seg_info["distance_km"]})

        payload = {
            "title": title,
            "race_format_id": race_format.id,
            "event_date": event_date_str, # Expects "YYYY-MM-DD"
            "gender_category": gender_category,
            "segments": processed_segments,
            "is_general": is_general_val
        }
        if description is not None: payload["description"] = description
        if location is not None: payload["location"] = location
        if promo_image_url is not None: payload["promo_image_url"] = promo_image_url
        return payload
    return _factory

@pytest.fixture
def sample_race(db_session, admin_user):
    """A sample race created in the DB for tests that need an existing race."""
    tri_format = RaceFormat.query.filter_by(name="Triatlón").first()
    # The db_session fixture now handles seeding, so tri_format should exist.
    # If it might not (e.g. if a test deletes it), add it back:
    if not tri_format:
        tri_format = RaceFormat(name="Triatlón")
        db_session.add(tri_format)
        # We might not want to commit here if other fixtures also commit;
        # rely on the main commit at the end of this fixture or test.

    from backend.models import RaceStatus # Import RaceStatus enum

    race = Race(
        title="Default Test Race",
        description="A default race for testing purposes.",
        race_format_id=tri_format.id,
        event_date=datetime(2024, 12, 1), # Use datetime object
        location="Default Test City",
        user_id=admin_user.id,
        is_general=False,
        gender_category="Ambos",
        category="Elite",
        quiniela_close_date=datetime(2024, 11, 15, 23, 59, 59), # Use datetime object
        is_deleted=False,
        status=RaceStatus.PLANNED # Use Enum member
    )
    db_session.add(race)
    db_session.commit()
    return race

@pytest.fixture
def question_type_factory(db_session): # Moved from test_answers.py
    def _factory(name):
        qt = QuestionType.query.filter_by(name=name).first()
        if not qt:
            qt = QuestionType(name=name) # Ensure QuestionType is imported in conftest or models
            db_session.add(qt)
            db_session.commit()
        return qt
    return _factory

@pytest.fixture(scope='function')
def new_admin_user(admin_user): # Alias admin_user to new_admin_user
    return admin_user

@pytest.fixture(scope='function')
def new_user(player_user): # Alias player_user to new_user
    return player_user

@pytest.fixture(scope='function')
def new_race_format(db_session): # Changed from test_client to db_session for direct db access
    race_format = RaceFormat.query.filter_by(name='Test Triathlon').first()
    if not race_format:
        race_format = RaceFormat(name='Test Triathlon')
        db_session.add(race_format)
        db_session.commit()
    return race_format

@pytest.fixture
def sample_slider_question(db_session, sample_race, admin_user):
    """A sample slider question created in the DB for tests."""
    from backend.models import Question, QuestionType # Local import

    slider_type = QuestionType.query.filter_by(name="SLIDER").first()
    if not slider_type:
        slider_type = QuestionType(name="SLIDER") # Removed description
        db_session.add(slider_type)
        db_session.commit()

    question = Question(
        race_id=sample_race.id,
        question_type_id=slider_type.id,
        text="Rate your experience from 1 to 10.",
        is_active=True,
        slider_unit="stars",
        slider_min_value=1.0,
        slider_max_value=10.0,
        slider_step=1.0,
        slider_points_exact=50,
        slider_threshold_partial=2.0, # e.g., within 2 units
        slider_points_partial=20
    )
    db_session.add(question)
    db_session.commit()
    return question

@pytest.fixture
def sample_free_text_question(db_session, sample_race, question_type_factory): # Added question_type_factory
    """A sample free text question."""
    ft_type = question_type_factory("FREE_TEXT")
    question = Question(
        race_id=sample_race.id,
        question_type_id=ft_type.id,
        text="Sample Free Text Question",
        is_active=True,
        max_score_free_text=10
    )
    db_session.add(question)
    db_session.commit()
    return question

@pytest.fixture
def sample_race_registration(db_session, player_user, sample_race): # Moved from test_answers.py
    """Registers player_user for sample_race."""
    registration = UserRaceRegistration.query.filter_by(user_id=player_user.id, race_id=sample_race.id).first()
    if not registration:
        registration = UserRaceRegistration(user_id=player_user.id, race_id=sample_race.id)
        db_session.add(registration)
        db_session.commit()
    return registration
