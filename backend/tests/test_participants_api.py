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
# Note: The app, client, and db_session fixtures are now expected to come from conftest.py
# Seeder functions are also expected to be handled by conftest.py's app fixture.

# --- User Fixtures (ensure they use db_session from conftest.py) ---
@pytest.fixture(scope='function')
def admin_role(db_session): # db_session now from conftest
    # Roles should be seeded by conftest app fixture.
    role = Role.query.filter_by(code='ADMIN').first()
    if not role: # Fallback if not seeded, though conftest should handle it
        role = Role(name='Admin', code='ADMIN', description='General Administrator')
        db_session.add(role)
        db_session.commit()
    return role

@pytest.fixture(scope='function')
def league_admin_role(db_session): # db_session now from conftest
    role = Role.query.filter_by(code='LEAGUE_ADMIN').first()
    if not role:
        role = Role(name='League Admin', code='LEAGUE_ADMIN', description='League Administrator')
        db_session.add(role)
        db_session.commit()
    return role

@pytest.fixture(scope='function')
def player_role(db_session): # db_session now from conftest
    role = Role.query.filter_by(code='PLAYER').first()
    if not role:
        role = Role(name='Player', code='PLAYER', description='Regular Player/User')
        db_session.add(role)
        db_session.commit()
    return role

@pytest.fixture(scope='function')
def test_admin(db_session, admin_role): # db_session and admin_role now from conftest or this file relying on conftest
    user = User.query.filter_by(username=TEST_ADMIN_USERNAME).first()
    if not user:
        user = User(name="Test Admin User", username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL, role_id=admin_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_league_admin(db_session, league_admin_role): # db_session and league_admin_role
    user = User.query.filter_by(username=TEST_LEAGUE_ADMIN_USERNAME).first()
    if not user:
        user = User(name="Test League Admin User", username=TEST_LEAGUE_ADMIN_USERNAME, email=TEST_LEAGUE_ADMIN_EMAIL, role_id=league_admin_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_player(db_session, player_role): # db_session and player_role
    user = User.query.filter_by(username=TEST_PLAYER_USERNAME).first()
    if not user:
        user = User(name="Test Player User", username=TEST_PLAYER_USERNAME, email=TEST_PLAYER_EMAIL, role_id=player_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_player2(db_session, player_role): # db_session and player_role
    user = User.query.filter_by(username="testplayer2").first()
    if not user:
        user = User(name="Test Player User 2", username="testplayer2", email="player2@test.com", role_id=player_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

@pytest.fixture(scope='function')
def test_player3(db_session, player_role): # db_session and player_role
    user = User.query.filter_by(username="testplayer3").first()
    if not user:
        user = User(name="Test Player User 3", username="testplayer3", email="player3@test.com", role_id=player_role.id)
        user.set_password(TEST_PASSWORD)
        db_session.add(user)
        db_session.commit()
    return user

# --- Helper function to log in a user ---
def login(client, username, password): # client will be from conftest
    return client.post('/api/login', data=json.dumps({
        'username': username,
        'password': password
    }), content_type='application/json')

# --- Race and Question Fixtures (ensure they use db_session from conftest.py) ---
# Local sample_race and sample_questions fixtures removed. Tests should use fixtures from conftest.py

# --- Registration and Answer Fixtures/Helpers ---

@pytest.fixture(scope='function')
def register_user_for_race(db_session): # db_session from conftest
    def _register(user, race):
        registration = UserRaceRegistration(user_id=user.id, race_id=race.id)
        db_session.add(registration)
        db_session.commit()
        return registration
    return _register

def submit_user_answers(db_session, user, race, questions_details_list, answers_map): # db_session from conftest
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
                user_answer.answer_text = ", ".join(raw_answer_data) if isinstance(raw_answer_data, list) else raw_answer_data
            elif q_detail["question_type_name"] == 'MULTIPLE_CHOICE':
                if q_detail["is_mc_multiple_correct"]:
                    if isinstance(raw_answer_data, list):
                        for option_id in raw_answer_data:
                            valid_option = any(opt['id'] == option_id for opt in q_detail['options'])
                            if valid_option:
                                mc_choice = UserAnswerMultipleChoiceOption(question_option_id=option_id)
                                user_answer.selected_mc_options.append(mc_choice)
                            else:
                                print(f"Warning: Invalid option_id {option_id} for multi-choice question {q_id}")
                    else:
                        print(f"Warning: Invalid answer data format for multi-choice question {q_id}. Expected list of option IDs.")
                else:
                    if isinstance(raw_answer_data, int):
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
# Tests will now use client and db_session fixtures from conftest.py

def test_get_participants_unauthenticated(client, sample_race): # client, sample_race from conftest
    response = client.get(f'/api/races/{sample_race.id}/participants')
    assert response.status_code == 401

def test_get_participants_forbidden_player(client, sample_race, test_player): # client, sample_race, test_player from conftest
    login(client, TEST_PLAYER_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants')
    assert response.status_code == 403

def test_get_participants_race_not_found(client, test_admin): # client, test_admin from conftest
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get('/api/races/9999/participants')
    assert response.status_code == 404
    assert response.json['message'] == "Race not found"

def test_get_participants_success_admin_league_admin(client, db_session, test_admin, test_league_admin,
                                                    test_player, test_player2, test_player3,
                                                    sample_race, sample_questions, register_user_for_race):
    # All fixtures are now from conftest or defined locally using conftest fixtures.
    register_user_for_race(test_player, sample_race)
    register_user_for_race(test_player2, sample_race)

    q_free_text_id = next(q['id'] for q in sample_questions if q['type'] == 'FREE_TEXT')
    submit_user_answers(db_session, test_player, sample_race, sample_questions, {
        q_free_text_id: "Player1's answer"
    })

    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response_admin = client.get(f'/api/races/{sample_race.id}/participants')
    assert response_admin.status_code == 200
    data_admin = response_admin.json
    assert len(data_admin) == 2

    participant_data_p1_admin = next((p for p in data_admin if p['user_id'] == test_player.id), None)
    participant_data_p2_admin = next((p for p in data_admin if p['user_id'] == test_player2.id), None)
    assert participant_data_p1_admin is not None and participant_data_p1_admin['has_answered'] is True
    assert participant_data_p2_admin is not None and participant_data_p2_admin['has_answered'] is False
    assert next((p for p in data_admin if p['user_id'] == test_player3.id), None) is None

    client.post('/api/logout')
    login(client, TEST_LEAGUE_ADMIN_USERNAME, TEST_PASSWORD)
    response_league = client.get(f'/api/races/{sample_race.id}/participants')
    assert response_league.status_code == 200
    data_league = response_league.json
    assert len(data_league) == 2
    participant_data_p1_league = next((p for p in data_league if p['user_id'] == test_player.id), None)
    assert participant_data_p1_league is not None and participant_data_p1_league['has_answered'] is True


def test_get_participants_no_participants(client, sample_race, test_admin): # Fixtures from conftest
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants')
    assert response.status_code == 200
    assert response.json == []

# --- Tests for /api/races/<race_id>/participants/<user_id>/answers ---

def test_get_participant_answers_unauthenticated(client, sample_race, test_player): # Fixtures from conftest
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 401

def test_get_participant_answers_forbidden_player(client, sample_race, test_player, register_user_for_race): # Fixtures from conftest
    register_user_for_race(test_player, sample_race)
    login(client, test_player.username, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 403

def test_get_participant_answers_race_not_found(client, test_admin, test_player): # Fixtures from conftest
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/9999/participants/{test_player.id}/answers')
    assert response.status_code == 404
    assert response.json['message'] == "Race not found"

def test_get_participant_answers_participant_not_found(client, sample_race, test_admin): # Fixtures from conftest
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/9999/answers')
    assert response.status_code == 404
    assert response.json['message'] == "Participant not found"

def test_get_participant_answers_participant_not_registered(client, sample_race, test_admin, test_player2): # Fixtures from conftest
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player2.id}/answers')
    assert response.status_code == 404
    assert f"User {test_player2.username} is not registered for race {sample_race.title}" in response.json['message']


def test_get_participant_answers_success(client, db_session, test_admin, sample_race, test_player, sample_questions, register_user_for_race):
    # Fixtures from conftest or local using conftest fixtures
    register_user_for_race(test_player, sample_race)

    answers_to_submit = {}
    q_ft = next(q for q in sample_questions if q['type'] == 'FREE_TEXT')
    answers_to_submit[q_ft['id']] = "My detailed free text answer."
    q_mc_single = next(q for q in sample_questions if q['type'] == 'MULTIPLE_CHOICE_SINGLE')
    answers_to_submit[q_mc_single['id']] = q_mc_single['options'][0]['id']
    q_mc_multi = next(q for q in sample_questions if q['type'] == 'MULTIPLE_CHOICE_MULTI')
    answers_to_submit[q_mc_multi['id']] = [q_mc_multi['options'][0]['id'], q_mc_multi['options'][2]['id']]
    q_ordering = next(q for q in sample_questions if q['type'] == 'ORDERING')
    user_ordered_texts = [
        q_ordering['correctly_ordered_option_objects'][0].option_text,
        q_ordering['correctly_ordered_option_objects'][1].option_text,
        q_ordering['correctly_ordered_option_objects'][2].option_text
    ]
    answers_to_submit[q_ordering['id']] = ", ".join(user_ordered_texts)

    submit_user_answers(db_session, test_player, sample_race, sample_questions, answers_to_submit)

    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 200
    data = response.json
    assert len(data) == len(sample_questions)

    for item in data:
        q_id = item['question_id']
        original_q_detail = next(q for q in sample_questions if q['id'] == q_id)
        assert item['question_text'] == original_q_detail['text']
        assert item['question_type'] == original_q_detail['question_type_name']
        assert item['is_mc_multiple_correct'] == original_q_detail['is_mc_multiple_correct']
        assert len(item['options']) == len(original_q_detail['options'])
        for i, opt_resp in enumerate(item['options']):
            assert opt_resp['id'] == original_q_detail['options'][i]['id']
            assert opt_resp['option_text'] == original_q_detail['options'][i]['option_text']

        if q_id == q_ft['id']:
            assert item['participant_answer'] == "My detailed free text answer."
        elif q_id == q_mc_single['id']:
            assert item['participant_answer']['id'] == q_mc_single['options'][0]['id']
        elif q_id == q_mc_multi['id']:
            selected_texts = sorted([opt['text'] for opt in item['participant_answer']])
            expected_texts = sorted([q_mc_multi['options'][0]['option_text'], q_mc_multi['options'][2]['option_text']])
            assert selected_texts == expected_texts
        elif q_id == q_ordering['id']:
            assert item['participant_answer'] == ", ".join(user_ordered_texts)


def test_get_participant_answers_no_answers_submitted(client, sample_race, test_admin, test_player, sample_questions, register_user_for_race):
    # Fixtures from conftest
    register_user_for_race(test_player, sample_race)
    login(client, TEST_ADMIN_USERNAME, TEST_PASSWORD)
    response = client.get(f'/api/races/{sample_race.id}/participants/{test_player.id}/answers')
    assert response.status_code == 200
    data = response.json
    assert len(data) == len(sample_questions)
    for item in data:
        assert item['participant_answer'] is None

# More to come...
