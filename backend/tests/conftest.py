import pytest
from backend.app import app as flask_app # Use your actual Flask app import
from backend.models import db as _db, User, Role, RaceFormat, Segment, Race # Added Race
from datetime import datetime

@pytest.fixture(scope='session')
def app():
    """Session-wide test Flask application."""
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", # Use in-memory SQLite for tests
        "LOGIN_DISABLED": False, # Ensure login is enabled for auth tests
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler testing of API endpoints
        "FLASK_SECRET_KEY": "test_secret_key_for_conftest" # Ensure a secret key is set
    })

    # Establish an application context before running the tests.
    with flask_app.app_context():
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

        _db.session.commit()

        yield flask_app # Teardown is handled by pytest-flask or can be added here

        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture()
def db_session(app):
    """
    Provides a database session for tests, ensuring data is clean.
    This version assumes the app context and initial seeding handle setup.
    For test isolation, you might wrap tests in transactions and roll back,
    or ensure clean_db is called more granularly if needed.
    """
    with app.app_context():
        yield _db.session # Provide the session for use in tests
        # Clean up after test, if necessary, though test isolation is key
        # For in-memory, the DB is fresh per session with the app fixture.
        # If using a persistent DB for tests, more aggressive cleanup would be needed here or per test.

@pytest.fixture
def new_user_factory(db_session):
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

@pytest.fixture
def admin_user(new_user_factory):
    return new_user_factory("admin_user", "admin@test.com", "admin_password", "ADMIN")

@pytest.fixture
def league_admin_user(new_user_factory):
    return new_user_factory("league_admin_user", "league_admin@test.com", "league_password", "LEAGUE_ADMIN")

@pytest.fixture
def player_user(new_user_factory):
    return new_user_factory("player_user", "player@test.com", "player_password", "PLAYER")

@pytest.fixture
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
    if not tri_format:
        tri_format = RaceFormat(name="Triatlón"); db_session.add(tri_format); db_session.commit()

    race = Race(
        title="Default Test Race",
        description="A default race for testing purposes.",
        race_format_id=tri_format.id,
        event_date=datetime.strptime("2024-12-01", "%Y-%m-%d"),
        location="Default Test City",
        user_id=admin_user.id, # Owned by admin_user by default
        is_general=False, # Default to local, tests can override if needed or create specific ones
        gender_category="Ambos",
        category="Elite"
    )
    db_session.add(race)
    db_session.commit()
    return race

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
        slider_type = QuestionType(name="SLIDER", description="Slider question type")
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
