import pytest
# Removed top-level: from backend.app import app as flask_app
from backend.models import db as _db, User, Role, RaceFormat, Segment, Race # Added Race
from datetime import datetime
import os # Ensure os is imported

@pytest.fixture(scope='session')
def app():
    """Session-wide test Flask application."""
    # Set environment variables before importing flask_app to prevent AWS SSM calls during import
    os.environ['FLASK_SECRET_KEY'] = 'test_secret_key_for_conftest_env_v2' # V2 to ensure it's this version
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:' # Test with in-memory SQLite

    from backend.app import app as flask_app_instance # Import app here, use a distinct name

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

        _db.session.commit()

        yield flask_app_instance

        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(scope="session")
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

@pytest.fixture(scope="session")
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

@pytest.fixture(scope="session")
def admin_user(new_user_factory):
    return new_user_factory("admin_user", "admin@test.com", "adminpassword", "ADMIN")

@pytest.fixture(scope="session")
def league_admin_user(new_user_factory):
    return new_user_factory("league_admin_user", "league_admin@test.com", "league_password", "LEAGUE_ADMIN")

@pytest.fixture(scope="session")
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
    db.session.commit()
    return question

# Fixtures for Race Participation Wizard Tests
from backend.models import UserRaceRegistration, Question, QuestionType, QuestionOption, UserAnswer

@pytest.fixture
def sample_race_with_registration(db_session, sample_race, player_user):
    """A sample race with a player_user already registered."""
    registration = UserRaceRegistration.query.filter_by(user_id=player_user.id, race_id=sample_race.id).first()
    if not registration:
        registration = UserRaceRegistration(user_id=player_user.id, race_id=sample_race.id)
        db_session.add(registration)
        db_session.commit()
    # Return an object or dict that gives access to race, user, and registration if needed
    class TestContext:
        def __init__(self, race, user, registration):
            self.race = race
            self.user = user
            self.registration = registration
    return TestContext(sample_race, player_user, registration)


@pytest.fixture
def free_text_question_type(db_session):
    qt = QuestionType.query.filter_by(name="FREE_TEXT").first()
    if not qt:
        qt = QuestionType(name="FREE_TEXT")
        db_session.add(qt)
        db_session.commit()
    return qt

@pytest.fixture
def mc_question_type(db_session):
    qt = QuestionType.query.filter_by(name="MULTIPLE_CHOICE").first()
    if not qt:
        qt = QuestionType(name="MULTIPLE_CHOICE")
        db_session.add(qt)
        db_session.commit()
    return qt

@pytest.fixture
def slider_question_type(db_session): # Renamed from sample_slider_question_type to avoid confusion
    qt = QuestionType.query.filter_by(name="SLIDER").first()
    if not qt:
        qt = QuestionType(name="SLIDER")
        db_session.add(qt)
        db_session.commit()
    return qt


@pytest.fixture
def sample_race_with_registration_and_question(db_session, sample_race_with_registration, free_text_question_type):
    """Sample race, user registered, and one FREE_TEXT question."""
    race = sample_race_with_registration.race
    question = Question.query.filter_by(race_id=race.id, text="Test Free Text Question 1").first()
    if not question:
        question = Question(
            race_id=race.id,
            question_type_id=free_text_question_type.id,
            text="Test Free Text Question 1",
            is_active=True,
            max_score_free_text=10
        )
        db_session.add(question)
        db_session.commit()

    class TestContextWithQuestion(type(sample_race_with_registration)): # Inherit from the previous context class structure
        def __init__(self, race, user, registration, question):
            super().__init__(race, user, registration)
            self.question = question
    return TestContextWithQuestion(race, sample_race_with_registration.user, sample_race_with_registration.registration, question)


@pytest.fixture
def sample_race_with_registration_and_questions(db_session, sample_race_with_registration, free_text_question_type):
    """Sample race, user registered, and two FREE_TEXT questions."""
    race = sample_race_with_registration.race
    q1_text = "Test Free Text Question A"
    q2_text = "Test Free Text Question B"

    q1 = Question.query.filter_by(race_id=race.id, text=q1_text).first()
    if not q1:
        q1 = Question(race_id=race.id, question_type_id=free_text_question_type.id, text=q1_text, is_active=True, max_score_free_text=5)
        db_session.add(q1)

    q2 = Question.query.filter_by(race_id=race.id, text=q2_text).first()
    if not q2:
        q2 = Question(race_id=race.id, question_type_id=free_text_question_type.id, text=q2_text, is_active=True, max_score_free_text=5)
        db_session.add(q2)
    db_session.commit()

    questions = sorted([q1, q2], key=lambda q: q.id) # Ensure order by ID

    class TestContextWithQuestions(type(sample_race_with_registration)):
        def __init__(self, race, user, registration, questions):
            super().__init__(race, user, registration)
            self.questions = questions # List of questions
    return TestContextWithQuestions(race, sample_race_with_registration.user, sample_race_with_registration.registration, questions)


@pytest.fixture
def sample_race_with_registration_and_mc_question(db_session, sample_race_with_registration, mc_question_type):
    """Sample race, user registered, and one MC-Single question with options."""
    race = sample_race_with_registration.race
    q_text = "Test MC Single Question"
    question = Question.query.filter_by(race_id=race.id, text=q_text).first()
    if not question:
        question = Question(
            race_id=race.id, question_type_id=mc_question_type.id, text=q_text,
            is_active=True, is_mc_multiple_correct=False, total_score_mc_single=10
        )
        db_session.add(question)
        db_session.flush() # Get ID for options
        opt1 = QuestionOption(question_id=question.id, option_text="Option 1 MC Single")
        opt2 = QuestionOption(question_id=question.id, option_text="Option 2 MC Single")
        db_session.add_all([opt1, opt2])
        db_session.commit()

    class TestContextWithMCQuestion(type(sample_race_with_registration)):
        def __init__(self, race, user, registration, question):
            super().__init__(race, user, registration)
            self.question = question
    return TestContextWithMCQuestion(race, sample_race_with_registration.user, sample_race_with_registration.registration, question)

@pytest.fixture
def sample_race_with_registration_and_mc_multi_question(db_session, sample_race_with_registration, mc_question_type):
    """Sample race, user registered, and one MC-Multi question with options."""
    race = sample_race_with_registration.race
    q_text = "Test MC Multi Question"
    question = Question.query.filter_by(race_id=race.id, text=q_text).first()
    if not question:
        question = Question(
            race_id=race.id, question_type_id=mc_question_type.id, text=q_text,
            is_active=True, is_mc_multiple_correct=True, points_per_correct_mc=5
        )
        db_session.add(question)
        db_session.flush()
        opt1 = QuestionOption(question_id=question.id, option_text="Option A MC Multi")
        opt2 = QuestionOption(question_id=question.id, option_text="Option B MC Multi")
        opt3 = QuestionOption(question_id=question.id, option_text="Option C MC Multi")
        db_session.add_all([opt1, opt2, opt3])
        db_session.commit()

    class TestContextWithMCMultiQuestion(type(sample_race_with_registration)):
        def __init__(self, race, user, registration, question):
            super().__init__(race, user, registration)
            self.question = question
    return TestContextWithMCMultiQuestion(race, sample_race_with_registration.user, sample_race_with_registration.registration, question)

@pytest.fixture
def sample_race_with_registration_and_slider_question(db_session, sample_race_with_registration, slider_question_type):
    """Sample race, user registered, and one Slider question."""
    race = sample_race_with_registration.race
    q_text = "Test Slider Question"
    question = Question.query.filter_by(race_id=race.id, text=q_text).first()
    if not question:
        question = Question(
            race_id=race.id, question_type_id=slider_question_type.id, text=q_text,
            is_active=True, slider_min_value=0, slider_max_value=100, slider_step=1, slider_points_exact=20
        )
        db_session.add(question)
        db_session.commit()

    class TestContextWithSliderQuestion(type(sample_race_with_registration)):
        def __init__(self, race, user, registration, question):
            super().__init__(race, user, registration)
            self.question = question
    return TestContextWithSliderQuestion(race, sample_race_with_registration.user, sample_race_with_registration.registration, question)
