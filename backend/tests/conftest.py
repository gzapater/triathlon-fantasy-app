import pytest
from backend.app import app as flask_app # Use your actual Flask app import
from backend.models import db as _db, User, Role, RaceFormat, Segment
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
