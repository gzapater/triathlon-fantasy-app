import pytest
from flask import jsonify, json # Added json
from datetime import datetime, timedelta

from backend.models import db, User, Role, Race, RaceFormat, Segment, Question, QuestionType, QuestionOption, OfficialAnswer, OfficialAnswerMultipleChoiceOption
# Assuming conftest.py provides these fixtures:
# test_client, init_db, db_session, admin_user, regular_user, create_race_with_questions

# Helper function to create a basic user with a role
def _create_user(username, email, password, role_code, db_session):
    role = Role.query.filter_by(code=role_code).first()
    if not role:
        role = Role(code=role_code, description=f"{role_code} role")
        db_session.add(role)
        db_session.commit()
    user = User(name=username, username=username, email=email, role=role)
    user.set_password(password)
    db_session.add(user)
    db_session.commit()
    return user

# Helper function to create a QuestionType if it doesn't exist
def _get_or_create_question_type(db_session, name):
    qt = QuestionType.query.filter_by(name=name).first()
    if not qt:
        qt = QuestionType(name=name)
        db_session.add(qt)
        db_session.commit()
    return qt

# Helper function to create a RaceFormat if it doesn't exist
def _get_or_create_race_format(db_session, name="Standard Triathlon"):
    rf = RaceFormat.query.filter_by(name=name).first()
    if not rf:
        rf = RaceFormat(name=name)
        db_session.add(rf)
        db_session.commit()
    return rf

# --- Model Tests ---

def test_create_official_answer_free_text(db_session, admin_user):
    race_format = _get_or_create_race_format(db_session)
    race = Race(title="Test Race OA", race_format_id=race_format.id, event_date=datetime.utcnow() - timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    db_session.add(race)
    db_session.commit()

    qt_free_text = _get_or_create_question_type(db_session, "FREE_TEXT")
    question = Question(race_id=race.id, question_type_id=qt_free_text.id, text="What is the capital of France?")
    db_session.add(question)
    db_session.commit()

    official_answer = OfficialAnswer(
        question_id=question.id,
        answer_text="Paris",
        created_by_id=admin_user.id
    )
    db_session.add(official_answer)
    db_session.commit()

    assert official_answer.id is not None
    assert official_answer.question_id == question.id
    assert official_answer.answer_text == "Paris"
    assert official_answer.created_by_id == admin_user.id
    assert official_answer.selected_option_id is None

def test_create_official_answer_mc_single(db_session, admin_user):
    race_format = _get_or_create_race_format(db_session)
    race = Race(title="Test Race MC Single OA", race_format_id=race_format.id, event_date=datetime.utcnow() - timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    db_session.add(race)
    db_session.commit()

    qt_mc = _get_or_create_question_type(db_session, "MULTIPLE_CHOICE")
    question = Question(race_id=race.id, question_type_id=qt_mc.id, text="Correct option?", is_mc_multiple_correct=False)
    db_session.add(question)
    db_session.commit()

    option1 = QuestionOption(question_id=question.id, option_text="Opt A")
    option2 = QuestionOption(question_id=question.id, option_text="Opt B (Correct)")
    db_session.add_all([option1, option2])
    db_session.commit()

    official_answer = OfficialAnswer(
        question_id=question.id,
        selected_option_id=option2.id,
        created_by_id=admin_user.id
    )
    db_session.add(official_answer)
    db_session.commit()

    assert official_answer.id is not None
    assert official_answer.selected_option_id == option2.id
    assert official_answer.answer_text is None

def test_create_official_answer_mc_multiple(db_session, admin_user):
    race_format = _get_or_create_race_format(db_session)
    race = Race(title="Test Race MC Multi OA", race_format_id=race_format.id, event_date=datetime.utcnow() - timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    db_session.add(race)
    db_session.commit()

    qt_mc = _get_or_create_question_type(db_session, "MULTIPLE_CHOICE")
    question = Question(race_id=race.id, question_type_id=qt_mc.id, text="Select correct options", is_mc_multiple_correct=True)
    db_session.add(question)
    db_session.commit()

    opt_a = QuestionOption(question_id=question.id, option_text="Opt A (Correct)")
    opt_b = QuestionOption(question_id=question.id, option_text="Opt B (Incorrect)")
    opt_c = QuestionOption(question_id=question.id, option_text="Opt C (Correct)")
    db_session.add_all([opt_a, opt_b, opt_c])
    db_session.commit()

    official_answer = OfficialAnswer(question_id=question.id, created_by_id=admin_user.id)
    db_session.add(official_answer)
    db_session.commit() # Commit to get official_answer.id

    oamc1 = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=opt_a.id)
    oamc2 = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=opt_c.id)
    db_session.add_all([oamc1, oamc2])
    db_session.commit()

    assert official_answer.id is not None
    assert len(official_answer.selected_mc_options) == 2
    selected_ids_from_db = sorted([item.question_option_id for item in official_answer.selected_mc_options])
    assert selected_ids_from_db == sorted([opt_a.id, opt_c.id])
    assert official_answer.answer_text is None
    assert official_answer.selected_option_id is None


def test_official_answer_question_id_unique(db_session, admin_user):
    race_format = _get_or_create_race_format(db_session)
    race = Race(title="Test Race UniqueQ OA", race_format_id=race_format.id, event_date=datetime.utcnow() - timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    db_session.add(race)
    db_session.commit()
    qt_text = _get_or_create_question_type(db_session, "FREE_TEXT")
    question = Question(race_id=race.id, question_type_id=qt_text.id, text="Unique Q Test")
    db_session.add(question)
    db_session.commit()

    oa1 = OfficialAnswer(question_id=question.id, answer_text="Ans1", created_by_id=admin_user.id)
    db_session.add(oa1)
    db_session.commit()

    oa2 = OfficialAnswer(question_id=question.id, answer_text="Ans2", created_by_id=admin_user.id)
    db_session.add(oa2)
    with pytest.raises(Exception) as excinfo: # Using generic Exception, ideally IntegrityError from sqlalchemy.exc
        db_session.commit()
    assert "UNIQUE constraint failed: official_answers.question_id" in str(excinfo.value) # Check for SQLite specific message
    db_session.rollback()


def test_official_answer_cascade_delete_mc_options(db_session, admin_user):
    race_format = _get_or_create_race_format(db_session)
    race = Race(title="Test Race Cascade OA", race_format_id=race_format.id, event_date=datetime.utcnow() - timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    qt_mc = _get_or_create_question_type(db_session, "MULTIPLE_CHOICE")
    question = Question(race_id=race.id, question_type_id=qt_mc.id, text="Cascade Test", is_mc_multiple_correct=True)
    opt = QuestionOption(question_id=question.id, option_text="Opt for cascade")
    db_session.add_all([race, question, opt])
    db_session.commit()

    official_answer = OfficialAnswer(question_id=question.id, created_by_id=admin_user.id)
    db_session.add(official_answer)
    db_session.commit() # Commit to get official_answer.id

    oamc = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=opt.id)
    db_session.add(oamc)
    db_session.commit()
    oamc_id = oamc.id

    assert OfficialAnswerMultipleChoiceOption.query.get(oamc_id) is not None

    db_session.delete(official_answer)
    db_session.commit()

    assert OfficialAnswer.query.get(official_answer.id) is None
    assert OfficialAnswerMultipleChoiceOption.query.get(oamc_id) is None


# --- API Tests (POST /api/races/<race_id>/official_answers) ---

@pytest.fixture
def setup_race_for_official_answers(db_session, admin_user):
    race_format = _get_or_create_race_format(db_session)
    race1 = Race(title="Race Concluded OA", race_format_id=race_format.id, event_date=datetime.utcnow() - timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    race2 = Race(title="Race Future OA", race_format_id=race_format.id, event_date=datetime.utcnow() + timedelta(days=1), user_id=admin_user.id, gender_category="MIXED")
    db_session.add_all([race1, race2])
    db_session.commit()

    qt_ft = _get_or_create_question_type(db_session, "FREE_TEXT")
    qt_mc = _get_or_create_question_type(db_session, "MULTIPLE_CHOICE")
    qt_ord = _get_or_create_question_type(db_session, "ORDERING")

    # Questions for Race1 (concluded)
    q1_ft = Question(race_id=race1.id, question_type_id=qt_ft.id, text="FT Q1")
    q1_mc_single = Question(race_id=race1.id, question_type_id=qt_mc.id, text="MC Single Q1", is_mc_multiple_correct=False)
    q1_mc_multi = Question(race_id=race1.id, question_type_id=qt_mc.id, text="MC Multi Q1", is_mc_multiple_correct=True)
    q1_ord = Question(race_id=race1.id, question_type_id=qt_ord.id, text="Ordering Q1")
    db_session.add_all([q1_ft, q1_mc_single, q1_mc_multi, q1_ord])
    db_session.commit()

    # Options for MC Single Q1
    q1_mc_s_opt1 = QuestionOption(question_id=q1_mc_single.id, option_text="MCS Opt1")
    q1_mc_s_opt2 = QuestionOption(question_id=q1_mc_single.id, option_text="MCS Opt2")
    db_session.add_all([q1_mc_s_opt1, q1_mc_s_opt2])

    # Options for MC Multi Q1
    q1_mc_m_opt1 = QuestionOption(question_id=q1_mc_multi.id, option_text="MCM Opt1")
    q1_mc_m_opt2 = QuestionOption(question_id=q1_mc_multi.id, option_text="MCM Opt2")
    q1_mc_m_opt3 = QuestionOption(question_id=q1_mc_multi.id, option_text="MCM Opt3")
    db_session.add_all([q1_mc_m_opt1, q1_mc_m_opt2, q1_mc_m_opt3])

    # Options for Ordering Q1
    q1_ord_opt1 = QuestionOption(question_id=q1_ord.id, option_text="ORD OptA", correct_order_index=0)
    q1_ord_opt2 = QuestionOption(question_id=q1_ord.id, option_text="ORD OptB", correct_order_index=1)
    db_session.add_all([q1_ord_opt1, q1_ord_opt2])
    db_session.commit()

    return {
        "race_concluded": race1,
        "race_future": race2,
        "q_ft": q1_ft,
        "q_mc_single": q1_mc_single, "q_mc_s_opt1": q1_mc_s_opt1, "q_mc_s_opt2": q1_mc_s_opt2,
        "q_mc_multi": q1_mc_multi, "q_mc_m_opt1": q1_mc_m_opt1, "q_mc_m_opt2": q1_mc_m_opt2, "q_mc_m_opt3": q1_mc_m_opt3,
        "q_ord": q1_ord
    }


def test_post_official_answers_permission_denied(test_client, regular_user, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_concluded"]
    # Login as regular_user (assuming test_client can do this or uses a fixture)
    test_client.post('/api/login', json={'username': regular_user.username, 'password': 'password'})

    response = test_client.post(f'/api/races/{race.id}/official_answers', json={})
    assert response.status_code == 403
    test_client.post('/api/logout') # Logout

def test_post_official_answers_race_not_found(test_client, admin_user):
    test_client.post('/api/login', json={'username': admin_user.username, 'password': 'password'})
    response = test_client.post('/api/races/9999/official_answers', json={})
    assert response.status_code == 404
    test_client.post('/api/logout')

def test_post_official_answers_race_not_concluded(test_client, admin_user, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_future"]
    test_client.post('/api/login', json={'username': admin_user.username, 'password': 'password'})
    response = test_client.post(f'/api/races/{race.id}/official_answers', json={})
    assert response.status_code == 403
    test_client.post('/api/logout')

def test_post_official_answers_empty_payload(test_client, admin_user, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_concluded"]
    test_client.post('/api/login', json={'username': admin_user.username, 'password': 'password'})
    response = test_client.post(f'/api/races/{race.id}/official_answers', json={})
    assert response.status_code == 400 # Or as per API spec for empty payload
    test_client.post('/api/logout')

def test_post_official_answers_create_and_update(test_client, db_session, admin_user, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_concluded"]
    q_ft = setup_race_for_official_answers["q_ft"]
    q_mc_single = setup_race_for_official_answers["q_mc_single"]
    q_mc_s_opt1 = setup_race_for_official_answers["q_mc_s_opt1"]
    q_mc_s_opt2 = setup_race_for_official_answers["q_mc_s_opt2"]
    q_mc_multi = setup_race_for_official_answers["q_mc_multi"]
    q_mc_m_opt1 = setup_race_for_official_answers["q_mc_m_opt1"]
    q_mc_m_opt2 = setup_race_for_official_answers["q_mc_m_opt2"]
    q_mc_m_opt3 = setup_race_for_official_answers["q_mc_m_opt3"]

    test_client.post('/api/login', json={'username': admin_user.username, 'password': 'password'})

    # 1. Create initial answers
    payload1 = {
        str(q_ft.id): {"answer_text": "Initial FT Answer"},
        str(q_mc_single.id): {"selected_option_id": q_mc_s_opt1.id},
        str(q_mc_multi.id): {"selected_option_ids": [q_mc_m_opt1.id, q_mc_m_opt3.id]}
    }
    response1 = test_client.post(f'/api/races/{race.id}/official_answers', json=payload1)
    assert response1.status_code == 200 # Or 201 if we distinguish create/update

    # Verify DB state after creation
    oa_ft = OfficialAnswer.query.filter_by(question_id=q_ft.id).first()
    assert oa_ft is not None
    assert oa_ft.answer_text == "Initial FT Answer"

    oa_mc_single = OfficialAnswer.query.filter_by(question_id=q_mc_single.id).first()
    assert oa_mc_single is not None
    assert oa_mc_single.selected_option_id == q_mc_s_opt1.id

    oa_mc_multi = OfficialAnswer.query.filter_by(question_id=q_mc_multi.id).first()
    assert oa_mc_multi is not None
    assert len(oa_mc_multi.selected_mc_options) == 2
    selected_ids = sorted([opt.question_option_id for opt in oa_mc_multi.selected_mc_options])
    assert selected_ids == sorted([q_mc_m_opt1.id, q_mc_m_opt3.id])

    # 2. Update answers (and clear previous types)
    payload2 = {
        str(q_ft.id): {"selected_option_id": q_mc_s_opt1.id}, # Change q_ft to be MC single (hypothetically, API should clear answer_text)
        str(q_mc_single.id): {"answer_text": "Updated MC Single to FT Answer"}, # Change q_mc_single to be FT
        str(q_mc_multi.id): {"selected_option_ids": [q_mc_m_opt2.id]} # Change selected options for multi
    }
    # To make this test realistic, we'd need to change question types in DB for q_ft and q_mc_single.
    # For now, we test if the API correctly clears OLD data based on NEW payload type for the SAME question.
    # The API logic clears based on the *question's actual type* in the DB, not what the payload implies.
    # So, for q_ft (which is FREE_TEXT type), sending selected_option_id will be ignored by current API logic.
    # Let's adjust payload2 to be more realistic for the API's behavior.

    # Corrected Payload 2: Update values, respecting original question types
    payload2_corrected = {
        str(q_ft.id): {"answer_text": "Updated FT Answer"}, # Update FT
        str(q_mc_single.id): {"selected_option_id": q_mc_s_opt2.id}, # Update MC-Single to a different option
        str(q_mc_multi.id): {"selected_option_ids": [q_mc_m_opt2.id]} # Update MC-Multi to a single different option
    }

    response2 = test_client.post(f'/api/races/{race.id}/official_answers', json=payload2_corrected)
    assert response2.status_code == 200

    # Verify DB state after update
    db_session.refresh(oa_ft) # Refresh from DB
    assert oa_ft.answer_text == "Updated FT Answer"
    assert oa_ft.selected_option_id is None # Should be cleared if it was FT

    db_session.refresh(oa_mc_single)
    assert oa_mc_single.selected_option_id == q_mc_s_opt2.id # Updated
    assert oa_mc_single.answer_text is None # Should be cleared

    db_session.refresh(oa_mc_multi)
    assert len(oa_mc_multi.selected_mc_options) == 1
    assert oa_mc_multi.selected_mc_options[0].question_option_id == q_mc_m_opt2.id # Updated

    test_client.post('/api/logout')


# --- API Tests (GET /api/races/<race_id>/official_answers) ---

def test_get_official_answers_race_not_concluded(test_client, regular_user, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_future"]
    test_client.post('/api/login', json={'username': regular_user.username, 'password': 'password'})
    response = test_client.get(f'/api/races/{race.id}/official_answers')
    assert response.status_code == 403
    test_client.post('/api/logout')

def test_get_official_answers_no_answers_set(test_client, regular_user, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_concluded"] # This race has questions but no official answers set yet by default
    test_client.post('/api/login', json={'username': regular_user.username, 'password': 'password'})

    response = test_client.get(f'/api/races/{race.id}/official_answers')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == {} # Expect empty JSON if no official answers are set
    test_client.post('/api/logout')


def test_get_official_answers_with_data(test_client, regular_user, admin_user, db_session, setup_race_for_official_answers):
    race = setup_race_for_official_answers["race_concluded"]
    q_ft = setup_race_for_official_answers["q_ft"]
    q_mc_single = setup_race_for_official_answers["q_mc_single"]
    q_mc_s_opt2 = setup_race_for_official_answers["q_mc_s_opt2"] # Assume this is the correct one
    q_mc_multi = setup_race_for_official_answers["q_mc_multi"]
    q_mc_m_opt1 = setup_race_for_official_answers["q_mc_m_opt1"]
    q_mc_m_opt3 = setup_race_for_official_answers["q_mc_m_opt3"]

    # First, admin sets some official answers
    test_client.post('/api/login', json={'username': admin_user.username, 'password': 'password'})
    post_payload = {
        str(q_ft.id): {"answer_text": "Official FT Text"},
        str(q_mc_single.id): {"selected_option_id": q_mc_s_opt2.id},
        str(q_mc_multi.id): {"selected_option_ids": [q_mc_m_opt1.id, q_mc_m_opt3.id]}
    }
    post_response = test_client.post(f'/api/races/{race.id}/official_answers', json=post_payload)
    assert post_response.status_code == 200
    test_client.post('/api/logout')

    # Now, regular user tries to fetch them
    test_client.post('/api/login', json={'username': regular_user.username, 'password': 'password'})
    response = test_client.get(f'/api/races/{race.id}/official_answers')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert str(q_ft.id) in data
    assert data[str(q_ft.id)]["question_type"] == "FREE_TEXT"
    assert data[str(q_ft.id)]["answer_text"] == "Official FT Text"

    assert str(q_mc_single.id) in data
    assert data[str(q_mc_single.id)]["question_type"] == "MULTIPLE_CHOICE"
    assert data[str(q_mc_single.id)]["selected_option_id"] == q_mc_s_opt2.id
    assert data[str(q_mc_single.id)]["selected_option_text"] == q_mc_s_opt2.option_text

    assert str(q_mc_multi.id) in data
    assert data[str(q_mc_multi.id)]["question_type"] == "MULTIPLE_CHOICE"
    returned_selected_options = data[str(q_mc_multi.id)]["selected_options"]
    assert len(returned_selected_options) == 2

    expected_mc_multi_options = [
        {"option_id": q_mc_m_opt1.id, "option_text": q_mc_m_opt1.option_text},
        {"option_id": q_mc_m_opt3.id, "option_text": q_mc_m_opt3.option_text}
    ]
    # Sort by option_id for comparison as order doesn't matter
    assert sorted(returned_selected_options, key=lambda x: x['option_id']) == sorted(expected_mc_multi_options, key=lambda x: x['option_id'])

    test_client.post('/api/logout')

# TODO: Add more tests for POST endpoint:
# - Invalid question_id in payload (not int, not existing)
# - question_id not belonging to the race
# - Malformed answer_data for each type (e.g. answer_text missing for FREE_TEXT)
# - Test clearing of old data thoroughly (e.g. if an MC-single was set, then is changed to FT, selected_option_id should be null) - this depends on API behavior for type changes.
#   The current API POST logic clears based on the *question's actual type in DB*, not what the payload might imply for a different type.
#   So, if a question is FREE_TEXT, sending selected_option_id for it will be ignored, and answer_text will be set.
#   If it's MULTIPLE_CHOICE single, sending answer_text will be ignored, and selected_option_id will be set.
#   This behavior seems correct.
# - Test unique constraint on OfficialAnswerMultipleChoiceOption (official_answer_id, question_option_id) - though this is harder to test at API level without direct model manipulation.
#   The API logic (delete all then add) should prevent duplicates from API calls.
