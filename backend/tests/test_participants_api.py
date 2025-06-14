import pytest
import json
from backend.app import app as flask_app  # Renamed to flask_app to avoid conflict
from backend.models import db, User, Role, Race, RaceFormat, Question, QuestionType, QuestionOption, UserRaceRegistration, UserAnswer, UserAnswerMultipleChoiceOption, Segment, RaceSegmentDetail

# --- Global Test Variables ---
TEST_ADMIN_USERNAME = "testadmin"
TEST_ADMIN_EMAIL = "admin@test.com"
TEST_LEAGUE_ADMIN_USERNAME = "testleagueadmin"
TEST_LEAGUE_ADMIN_EMAIL = "leagueadmin@test.com"
TEST_PLAYER_USERNAME = "testplayer"
TEST_PLAYER_EMAIL = "player@test.com"
TEST_PASSWORD = "password123"

# --- Pytest Fixtures ---

@pytest.fixture(scope='module')
def app():
    """Instance of Main Flask App"""
    # Configure app for testing
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # Use in-memory SQLite for tests
        "LOGIN_DISABLED": False, # Ensure login is enabled for testing @login_required
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler form testing in API calls
        "SECRET_KEY": "test_secret_key" # Required for session management
    })
    with flask_app.app_context():
        db.create_all()
        # Seed initial roles and question types for consistency
        seed_initial_roles()
        seed_initial_question_types()
        seed_initial_segments() # If segments are needed for race creation
        seed_initial_race_formats() # If race formats are needed
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='module')
def client(app):
    """A test client for the app."""
    return app.test_client()

def seed_initial_roles():
    roles = [
        {'name': 'Admin', 'code': 'ADMIN', 'description': 'General Administrator'},
        {'name': 'League Admin', 'code': 'LEAGUE_ADMIN', 'description': 'League Administrator'},
        {'name': 'Player', 'code': 'PLAYER', 'description': 'Regular Player/User'}
    ]
    for r_data in roles:
        if not Role.query.filter_by(code=r_data['code']).first():
            role = Role(**r_data)
            db.session.add(role)
    db.session.commit()

def seed_initial_question_types():
    question_types = [
        {'name': 'FREE_TEXT', 'description': 'Open-ended text answer'},
        {'name': 'MULTIPLE_CHOICE', 'description': 'Select one or more from options'},
        {'name': 'ORDERING', 'description': 'Arrange items in a specific order'}
    ]
    for qt_data in question_types:
        if not QuestionType.query.filter_by(name=qt_data['name']).first():
            qt = QuestionType(**qt_data)
            db.session.add(qt)
    db.session.commit()

def seed_initial_segments():
    segments = [
        {"name": "Natación", "description": "Segmento de natación"},
        {"name": "Ciclismo", "description": "Segmento de ciclismo"},
        {"name": "Carrera a Pie", "description": "Segmento de carrera a pie"},
        {"name": "Transición 1 (T1)", "description": "Transición de Natación a Ciclismo"},
        {"name": "Transición 2 (T2)", "description": "Transición de Ciclismo a Carrera a Pie"}
    ]
    for seg_data in segments:
        if not Segment.query.filter_by(name=seg_data["name"]).first():
            segment = Segment(**seg_data)
            db.session.add(segment)
    db.session.commit()

def seed_initial_race_formats():
    formats = [
        {"name": "Standard", "description": "Distancia Olímpica"},
        {"name": "Sprint", "description": "Media Distancia Olímpica"},
        {"name": "Ironman", "description": "Larga Distancia"},
        {"name": "70.3", "description": "Media Distancia Ironman"}
    ]
    for fmt_data in formats:
        if not RaceFormat.query.filter_by(name=fmt_data["name"]).first():
            race_format = RaceFormat(**fmt_data)
            db.session.add(race_format)
    db.session.commit()


@pytest.fixture(scope='function')
def db_session(app):
    """Creates a new database session for a test."""
    connection = db.engine.connect()
    transaction = connection.begin()
    options = dict(bind=connection, binds={})
    session = db.create_scoped_session(options=options)
    db.session = session

    yield session

    transaction.rollback()
    connection.close()
    session.remove()


# --- User Fixtures ---
@pytest.fixture(scope='function')
def admin_role(db_session):
    return Role.query.filter_by(code='ADMIN').first()

@pytest.fixture(scope='function')
def league_admin_role(db_session):
    return Role.query.filter_by(code='LEAGUE_ADMIN').first()

@pytest.fixture(scope='function')
def player_role(db_session):
    return Role.query.filter_by(code='PLAYER').first()

@pytest.fixture(scope='function')
def test_admin(db_session, admin_role):
    user = User.query.filter_by(username=TEST_ADMIN_USERNAME).first()
    if not user:
        user = User(name="Test Admin User", username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL, role_id=admin_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_league_admin(db_session, league_admin_role):
    user = User.query.filter_by(username=TEST_LEAGUE_ADMIN_USERNAME).first()
    if not user:
        user = User(name="Test League Admin User", username=TEST_LEAGUE_ADMIN_USERNAME, email=TEST_LEAGUE_ADMIN_EMAIL, role_id=league_admin_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_player(db_session, player_role):
    user = User.query.filter_by(username=TEST_PLAYER_USERNAME).first()
    if not user:
        user = User(name="Test Player User", username=TEST_PLAYER_USERNAME, email=TEST_PLAYER_EMAIL, role_id=player_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_player2(db_session, player_role):
    user = User.query.filter_by(username="testplayer2").first()
    if not user:
        user = User(name="Test Player User 2", username="testplayer2", email="player2@test.com", role_id=player_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_player3(db_session, player_role):
    user = User.query.filter_by(username="testplayer3").first()
    if not user:
        user = User(name="Test Player User 3", username="testplayer3", email="player3@test.com", role_id=player_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

# --- Helper function to log in a user ---
def login(client, username, password):
    return client.post('/api/login', data=json.dumps({
        'username': username,
        'password': password
    }), content_type='application/json')

# --- Race and Question Fixtures ---
@pytest.fixture(scope='function')
def sample_race(db_session, test_league_admin):
    race_format = RaceFormat.query.first()
    if not race_format: # Should have been seeded
        race_format = RaceFormat(name="TestFormat", description="Test Desc")
        db_session.add(race_format)
        db_session.commit()

    race = Race(
        title="Test Race for Participants API",
        description="A race to test participant API endpoints.",
        race_format_id=race_format.id,
        event_date="2024-08-01",
        location="Test Location",
        gender_category="MIXED",
        user_id=test_league_admin.id, # Assuming league admin creates it
        is_general=False
    )
    db_session.add(race)
    db_session.commit()
    return race

@pytest.fixture(scope='function')
def sample_questions(db_session, sample_race):
    qt_free_text = QuestionType.query.filter_by(name='FREE_TEXT').first()
    qt_mc = QuestionType.query.filter_by(name='MULTIPLE_CHOICE').first()
    qt_ordering = QuestionType.query.filter_by(name='ORDERING').first()

    questions_data = []

    # Free Text Question
    q1 = Question(race_id=sample_race.id, question_type_id=qt_free_text.id, text="Who will win the race?", max_score_free_text=10)
    db_session.add(q1)
    questions_data.append({"obj": q1, "type": "FREE_TEXT", "options": []})

    # Multiple Choice - Single Correct
    q2 = Question(race_id=sample_race.id, question_type_id=qt_mc.id, text="What is the capital of France?", is_mc_multiple_correct=False, total_score_mc_single=5)
    db_session.add(q2)
    db_session.flush() # Get q2.id
    opt2_1 = QuestionOption(question_id=q2.id, option_text="Paris")
    opt2_2 = QuestionOption(question_id=q2.id, option_text="London")
    db_session.add_all([opt2_1, opt2_2])
    questions_data.append({"obj": q2, "type": "MULTIPLE_CHOICE_SINGLE", "options": [opt2_1, opt2_2], "correct_single_option_id": opt2_1.id})

    # Multiple Choice - Multi Correct
    q3 = Question(race_id=sample_race.id, question_type_id=qt_mc.id, text="Which are primary colors?", is_mc_multiple_correct=True, points_per_correct_mc=5, points_per_incorrect_mc=-2)
    db_session.add(q3)
    db_session.flush() # Get q3.id
    opt3_1 = QuestionOption(question_id=q3.id, option_text="Red")
    opt3_2 = QuestionOption(question_id=q3.id, option_text="Green") # Part of RGB, but traditionally Red, Yellow, Blue
    opt3_3 = QuestionOption(question_id=q3.id, option_text="Blue")
    opt3_4 = QuestionOption(question_id=q3.id, option_text="Purple")
    db_session.add_all([opt3_1, opt3_2, opt3_3, opt3_4])
    questions_data.append({"obj": q3, "type": "MULTIPLE_CHOICE_MULTI", "options": [opt3_1, opt3_2, opt3_3, opt3_4], "correct_multi_option_ids": [opt3_1.id, opt3_3.id]}) # Assuming Red and Blue for simplicity

    # Ordering Question
    q4 = Question(race_id=sample_race.id, question_type_id=qt_ordering.id, text="Order these numbers: 2, 1, 3", points_per_correct_order=3, bonus_for_full_order=2)
    db_session.add(q4)
    db_session.flush() # Get q4.id
    opt4_1 = QuestionOption(question_id=q4.id, option_text="Item for 2", correct_order_index=1) # Correct order: 1, 2, 3
    opt4_2 = QuestionOption(question_id=q4.id, option_text="Item for 1", correct_order_index=0)
    opt4_3 = QuestionOption(question_id=q4.id, option_text="Item for 3", correct_order_index=2)
    db_session.add_all([opt4_1, opt4_2, opt4_3])
    # Store original options in the order they are defined for test reference if needed
    questions_data.append({"obj": q4, "type": "ORDERING", "options_in_defined_order": [opt4_1, opt4_2, opt4_3], "options_in_correct_order": [opt4_2, opt4_1, opt4_3]})


    db_session.commit()
    # Re-fetch questions with their options after commit to ensure relationships are loaded
    final_questions_details = []
    for q_data_item in questions_data:
        q_obj = Question.query.get(q_data_item["obj"].id)
        # Ensure options are loaded and ordered for consistent test data
        # The .options relationship on Question model should be configured with order_by=QuestionOption.id
        # or QuestionOption.correct_order_index depending on desired default order.
        # For tests, explicitly ordering here is safer.
        options_list = [{"id": opt.id, "option_text": opt.option_text, "correct_order_index": opt.correct_order_index}
                        for opt in q_obj.options.order_by(QuestionOption.id).all()]

        final_q_data = {
            "obj": q_obj, # The SQLAlchemy object
            "id": q_obj.id,
            "text": q_obj.text,
            "type": q_data_item["type"], # Custom type identifier used in test logic
            "question_type_name": q_obj.question_type.name, # Actual type name from DB
            "is_mc_multiple_correct": q_obj.is_mc_multiple_correct,
            "options": options_list
        }
        if "correct_single_option_id" in q_data_item: # Store the ID of the correct option for single MC
             final_q_data["correct_single_option_id"] = q_data_item["correct_single_option_id"]
        if "correct_multi_option_ids" in q_data_item: # Store list of IDs of correct options for multi MC
            final_q_data["correct_multi_option_ids"] = q_data_item["correct_multi_option_ids"]
        if "options_in_correct_order" in q_data_item: # For ordering, store the list of option objects in their correct order
            final_q_data["correctly_ordered_option_objects"] = q_data_item["options_in_correct_order"]
            # Also store their texts in correct order for easier assertion against string answers
            final_q_data["correctly_ordered_texts"] = [opt.option_text for opt in q_data_item["options_in_correct_order"]]


        final_questions_details.append(final_q_data)
    return final_questions_details

# --- Registration and Answer Fixtures/Helpers ---

@pytest.fixture(scope='function')
def register_user_for_race(db_session):
    def _register(user, race):
        registration = UserRaceRegistration(user_id=user.id, race_id=race.id)
        db_session.add(registration)
        db_session.commit()
        return registration
    return _register

def submit_user_answers(db_session, user, race, questions_details_list, answers_map):
    """
    Helper to submit answers for a user.
    answers_map is a dictionary like: {question_id: answer_data}
    answer_data depends on question type:
        - FREE_TEXT: "user's text answer"
        - MULTIPLE_CHOICE_SINGLE: option_id (int) of the selected option
        - MULTIPLE_CHOICE_MULTI: [option_id1, option_id2] list of selected option ids
        - ORDERING: ["text of opt1 in user order", "text of opt2 in user order", ...]
    """
    for q_detail in questions_details_list:
        q_id = q_detail["id"]
        if q_id in answers_map:
            raw_answer_data = answers_map[q_id]

            user_answer = UserAnswer(user_id=user.id, race_id=race.id, question_id=q_id)

            if q_detail["question_type_name"] == 'FREE_TEXT':
                user_answer.answer_text = raw_answer_data
            elif q_detail["question_type_name"] == 'ORDERING':
                # For ordering, the answer_text stores the user's sequence of option texts, comma-separated
                user_answer.answer_text = ", ".join(raw_answer_data) if isinstance(raw_answer_data, list) else raw_answer_data
            elif q_detail["question_type_name"] == 'MULTIPLE_CHOICE':
                if q_detail["is_mc_multiple_correct"]: # Multi-select
                    if isinstance(raw_answer_data, list): # Expecting a list of option IDs
                        for option_id in raw_answer_data:
                            # Ensure option_id is valid for the question
                            valid_option = any(opt['id'] == option_id for opt in q_detail['options'])
                            if valid_option:
                                mc_choice = UserAnswerMultipleChoiceOption(question_option_id=option_id)
                                user_answer.selected_mc_options.append(mc_choice)
                            else:
                                print(f"Warning: Invalid option_id {option_id} for multi-choice question {q_id}")
                    else:
                        print(f"Warning: Invalid answer data format for multi-choice question {q_id}. Expected list of option IDs.")
                else: # Single-select
                    if isinstance(raw_answer_data, int): # Expecting a single option ID
                        valid_option = any(opt['id'] == raw_answer_data for opt in q_detail['options'])
                        if valid_option:
                            user_answer.selected_option_id = raw_answer_data
                        else:
                            print(f"Warning: Invalid option_id {raw_answer_data} for single-choice question {q_id}")
                    else:
                         print(f"Warning: Invalid answer data format for single-choice question {q_id}. Expected option ID.")

            db_session.add(user_answer)
    db_session.commit()


# --- Tests for /api/races/<race_id>/participants ---

def test_get_participants_unauthenticated(client, sample_race):
    response = client.get(f'/api/races/{sample_race.id}/participants')
    assert response.status_code == 401 # Expect redirect to login, then Flask-Login handles it as 401

def test_get_participants_forbidden_player(client, sample_race, test_player):
    login(client, TEST_PLAYER_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants')
    assert response.status_code == 403

def test_get_participants_race_not_found(client, test_admin):
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get('/api/races/9999/participants') # Non-existent race
    assert response.status_code == 404
    assert response.json['message'] == "Race not found"

def test_get_participants_success_admin_league_admin(client, db_session, test_admin, test_league_admin,
                                                    test_player, test_player2, test_player3,
                                                    sample_race, sample_questions, register_user_for_race):
    # Register player1 and player2 for the race
    register_user_for_race(test_player, sample_race)
    register_user_for_race(test_player2, sample_race)
    # player3 is not registered

    # player1 answers one question
    q_free_text_id = next(q['id'] for q in sample_questions if q['type'] == 'FREE_TEXT')
    submit_user_answers(db_session, test_player, sample_race, sample_questions, {
        q_free_text_id: "Player1's answer"
    })
    # player2 does not answer any questions

    # Log in as ADMIN
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response_admin = client.get(f'/api/races/{sample_race.id}/participants')
    assert response_admin.status_code == 200
    data_admin = response_admin.json

    assert len(data_admin) == 2

    participant_data_p1_admin = next((p for p in data_admin if p['user_id'] == test_player.id), None)
    participant_data_p2_admin = next((p for p in data_admin if p['user_id'] == test_player2.id), None)
    participant_data_p3_admin = next((p for p in data_admin if p['user_id'] == test_player3.id), None)

    assert participant_data_p1_admin is not None
    assert participant_data_p1_admin['username'] == test_player.username
    assert participant_data_p1_admin['has_answered'] is True

    assert participant_data_p2_admin is not None
    assert participant_data_p2_admin['username'] == test_player2.username
    assert participant_data_p2_admin['has_answered'] is False

    assert participant_data_p3_admin is None # Player3 should not be in the list

    # Log out admin, Log in as LEAGUE_ADMIN (creator of the race)
    client.post('/api/logout') # Logout
    login(client, TEST_LEAGUE_ADMIN_USERNAME, TEST_PASSWORD)
    response_league = client.get(f'/api/races/{sample_race.id}/participants')
    assert response_league.status_code == 200
    data_league = response_league.json
    assert len(data_league) == 2 # Same assertions should hold

    participant_data_p1_league = next((p for p in data_league if p['user_id'] == test_player.id), None)
    assert participant_data_p1_league is not None
    assert participant_data_p1_league['has_answered'] is True


def test_get_participants_no_participants(client, sample_race, test_admin):
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    # sample_race is newly created for this test function by its fixture, so no participants yet.
    response = client.get(f'/api/races/{sample_race.id}/participants')
    assert response.status_code == 200
    assert response.json == []

# --- Tests for /api/races/<race_id>/participants/<user_id>/answers ---

def test_get_participant_answers_unauthenticated(client, sample_race, test_player):
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 401

def test_get_participant_answers_forbidden_player(client, sample_race, test_player, register_user_for_race):
    register_user_for_race(test_player, sample_race) # Player needs to be registered to even be a valid target
    login(client, test_player.username, TEST_PASSWORD) # Logged in as the player themselves

    # A player trying to access this admin-level detailed view of their own answers (or others)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 403

def test_get_participant_answers_race_not_found(client, test_admin, test_player):
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/9999/participants/{test_player.id}/answers')
    assert response.status_code == 404
    assert response.json['message'] == "Race not found"

def test_get_participant_answers_participant_not_found(client, sample_race, test_admin):
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/9999/answers')
    assert response.status_code == 404
    assert response.json['message'] == "Participant not found"

def test_get_participant_answers_participant_not_registered(client, sample_race, test_admin, test_player2):
    # test_player2 exists but is not registered for sample_race in this test's context
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player2.id}/answers')
    assert response.status_code == 404 # As per current endpoint implementation
    assert f"User {test_player2.username} is not registered for race {sample_race.title}" in response.json['message']


def test_get_participant_answers_success(client, db_session, test_admin, sample_race, test_player, sample_questions, register_user_for_race):
    register_user_for_race(test_player, sample_race)

    # Prepare answers for the test_player
    answers_to_submit = {}
    # Answer Free Text
    q_ft = next(q for q in sample_questions if q['type'] == 'FREE_TEXT')
    answers_to_submit[q_ft['id']] = "My detailed free text answer."

    # Answer MC Single - select the first option (which we marked as correct in fixture)
    q_mc_single = next(q for q in sample_questions if q['type'] == 'MULTIPLE_CHOICE_SINGLE')
    answers_to_submit[q_mc_single['id']] = q_mc_single['options'][0]['id'] # Select first option

    # Answer MC Multi - select two options
    q_mc_multi = next(q for q in sample_questions if q['type'] == 'MULTIPLE_CHOICE_MULTI')
    answers_to_submit[q_mc_multi['id']] = [q_mc_multi['options'][0]['id'], q_mc_multi['options'][2]['id']]


    # Answer Ordering - provide an ordered list of texts
    q_ordering = next(q for q in sample_questions if q['type'] == 'ORDERING')
    # User submits: Correctly ordered texts: Item for 1, Item for 2, Item for 3
    user_ordered_texts = [
        q_ordering['options_in_correct_order'][0].option_text,
        q_ordering['options_in_correct_order'][1].option_text,
        q_ordering['options_in_correct_order'][2].option_text
    ]
    answers_to_submit[q_ordering['id']] = ", ".join(user_ordered_texts) # API expects comma-separated string for ordering

    submit_user_answers(db_session, test_player, sample_race, sample_questions, answers_to_submit)

    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 200
    data = response.json

    assert len(data) == len(sample_questions) # Should have an entry for each question

    for item in data:
        q_id = item['question_id']
        original_q_detail = next(q for q in sample_questions if q['id'] == q_id)

        assert item['question_text'] == original_q_detail['text']
        assert item['question_type'] == original_q_detail['question_type_name']
        assert item['is_mc_multiple_correct'] == original_q_detail['is_mc_multiple_correct']

        # Verify options structure
        assert len(item['options']) == len(original_q_detail['options'])
        for i, opt_resp in enumerate(item['options']):
            assert opt_resp['id'] == original_q_detail['options'][i]['id']
            assert opt_resp['option_text'] == original_q_detail['options'][i]['option_text']

        # Verify participant's answer
        if q_id == q_ft['id']:
            assert item['participant_answer'] == "My detailed free text answer."
        elif q_id == q_mc_single['id']:
            assert item['participant_answer'] is not None
            assert item['participant_answer']['id'] == q_mc_single['options'][0]['id']
            assert item['participant_answer']['text'] == q_mc_single['options'][0]['option_text']
        elif q_id == q_mc_multi['id']:
            assert item['participant_answer'] is not None
            assert len(item['participant_answer']) == 2
            selected_texts = sorted([opt['text'] for opt in item['participant_answer']])
            expected_texts = sorted([q_mc_multi['options'][0]['option_text'], q_mc_multi['options'][2]['option_text']])
            assert selected_texts == expected_texts
        elif q_id == q_ordering['id']:
            assert item['participant_answer'] == ", ".join(user_ordered_texts)


def test_get_participant_answers_no_answers_submitted(client, sample_race, test_admin, test_player, sample_questions, register_user_for_race):
    register_user_for_race(test_player, sample_race)
    # No answers submitted for test_player

    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 200
    data = response.json

    assert len(data) == len(sample_questions)
    for item in data:
        assert item['participant_answer'] is None

# More to come...
