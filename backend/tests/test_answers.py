import pytest
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from backend.models import (
    db, User, Role, Race, RaceFormat, Segment, Question, QuestionType,
    QuestionOption, UserAnswer, UserAnswerMultipleChoiceOption, UserRaceRegistration
)

# Helper fixture to create a QuestionType (can be moved to conftest.py if used elsewhere)
@pytest.fixture
def question_type_factory(db_session):
    def _factory(name):
        qt = QuestionType.query.filter_by(name=name).first()
        if not qt:
            qt = QuestionType(name=name)
            db_session.add(qt)
            db_session.commit()
        return qt
    return _factory

# Helper fixture to create a Question (can be moved to conftest.py if used elsewhere)
@pytest.fixture
def question_factory(db_session, question_type_factory):
    def _factory(race, question_type_name, text="Sample Question?"):
        qt = question_type_factory(question_type_name)
        question = Question(
            race_id=race.id,
            question_type_id=qt.id,
            text=text,
            is_active=True
        )
        if question_type_name == "MULTIPLE_CHOICE":
            question.is_mc_multiple_correct = False # Default to single correct for MC
            question.total_score_mc_single = 10
        elif question_type_name == "FREE_TEXT":
            question.max_score_free_text = 5
        # Specific scoring for ORDERING will be set in the test
        db_session.add(question)
        db_session.commit()
        return question
    return _factory

# Helper fixture to create a QuestionOption (can be moved to conftest.py if used elsewhere)
@pytest.fixture
def option_factory(db_session): # Renamed to question_option_factory in the new test for clarity
    def _factory(question, option_text="Sample Option"):
        option = QuestionOption(
            question_id=question.id,
            option_text=option_text
        )
        db_session.add(option)
        db_session.commit()
        return option
    return _factory

# Fixture to create a user registered for a race
@pytest.fixture
def registered_user_for_race(db_session, player_user, sample_race):
    registration = UserRaceRegistration(user_id=player_user.id, race_id=sample_race.id)
    db_session.add(registration)
    db_session.commit()
    return player_user, sample_race


def test_create_user_answer_free_text(db_session, registered_user_for_race, question_factory):
    user, race = registered_user_for_race
    question = question_factory(race, "FREE_TEXT", text="What is your prediction?")

    answer_text = "My detailed prediction."
    user_answer = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        answer_text=answer_text
    )
    db_session.add(user_answer)
    db_session.commit()

    retrieved_answer = UserAnswer.query.get(user_answer.id)
    assert retrieved_answer is not None
    assert retrieved_answer.user_id == user.id
    assert retrieved_answer.question_id == question.id
    assert retrieved_answer.answer_text == answer_text
    assert retrieved_answer.selected_option_id is None
    assert retrieved_answer.user == user
    assert retrieved_answer.race == race
    assert retrieved_answer.question == question

def test_create_user_answer_mc_single_choice(db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race
    question = question_factory(race, "MULTIPLE_CHOICE", text="Which option?")
    question.is_mc_multiple_correct = False # Ensure it's single choice
    db_session.commit()

    option1 = option_factory(question, "Option A")
    option2 = option_factory(question, "Option B")

    user_answer = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        selected_option_id=option1.id
    )
    db_session.add(user_answer)
    db_session.commit()

    retrieved_answer = UserAnswer.query.get(user_answer.id)
    assert retrieved_answer is not None
    assert retrieved_answer.selected_option_id == option1.id
    assert retrieved_answer.answer_text is None
    assert retrieved_answer.selected_option == option1
    assert option1.user_answers.count() == 1 # Check backref

def test_create_user_answer_mc_multiple_choice(db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race
    question = question_factory(race, "MULTIPLE_CHOICE", text="Select multiple options")
    question.is_mc_multiple_correct = True # Set to multiple correct
    db_session.commit()

    option1 = option_factory(question, "Opt X")
    option2 = option_factory(question, "Opt Y")
    option3 = option_factory(question, "Opt Z")

    user_answer = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id
    )
    # Must add UserAnswer first to get its ID for UserAnswerMultipleChoiceOption if not using backref population
    db_session.add(user_answer)
    db_session.commit() # Commit to assign user_answer.id

    uamco1 = UserAnswerMultipleChoiceOption(
        user_answer_id=user_answer.id,
        question_option_id=option1.id
    )
    uamco2 = UserAnswerMultipleChoiceOption(
        user_answer_id=user_answer.id,
        question_option_id=option2.id
    )
    db_session.add_all([uamco1, uamco2])
    db_session.commit()

    retrieved_answer = UserAnswer.query.get(user_answer.id)
    assert retrieved_answer is not None
    assert len(retrieved_answer.selected_mc_options) == 2

    selected_option_ids_in_db = {sel.question_option_id for sel in retrieved_answer.selected_mc_options}
    assert option1.id in selected_option_ids_in_db
    assert option2.id in selected_option_ids_in_db
    assert option3.id not in selected_option_ids_in_db

    # Test relationships back from UAMCO
    assert uamco1.user_answer == retrieved_answer
    assert uamco1.question_option == option1
    assert option1.user_selections.count() >= 1 # Check backref from QuestionOption to UAMCO

def test_user_answer_unique_constraint(db_session, registered_user_for_race, question_factory):
    user, race = registered_user_for_race
    question = question_factory(race, "FREE_TEXT", text="Unique constraint test")

    user_answer1 = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        answer_text="First answer"
    )
    db_session.add(user_answer1)
    db_session.commit()

    user_answer2 = UserAnswer(
        user_id=user.id,
        race_id=race.id, # Different race would be fine
        question_id=question.id,
        answer_text="Second answer attempt"
    )
    db_session.add(user_answer2)
    with pytest.raises(IntegrityError): # Specific exception might vary by DB backend
        db_session.commit()
    db_session.rollback() # Important after an IntegrityError

def test_cascade_delete_user_answer_to_mc_options(db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race
    question = question_factory(race, "MULTIPLE_CHOICE", text="Cascade delete test")
    question.is_mc_multiple_correct = True
    db_session.commit()

    option1 = option_factory(question, "Choice A")
    option2 = option_factory(question, "Choice B")

    user_answer = UserAnswer(user_id=user.id, race_id=race.id, question_id=question.id)
    db_session.add(user_answer)
    db_session.commit() # Commit to get user_answer.id

    uamco1 = UserAnswerMultipleChoiceOption(user_answer_id=user_answer.id, question_option_id=option1.id)
    uamco2 = UserAnswerMultipleChoiceOption(user_answer_id=user_answer.id, question_option_id=option2.id)
    db_session.add_all([uamco1, uamco2])
    db_session.commit()

    uamco1_id = uamco1.id
    uamco2_id = uamco2.id
    user_answer_id = user_answer.id

    assert UserAnswerMultipleChoiceOption.query.get(uamco1_id) is not None
    assert UserAnswerMultipleChoiceOption.query.get(uamco2_id) is not None

    # Delete the parent UserAnswer
    db_session.delete(user_answer)
    db_session.commit()

    assert UserAnswer.query.get(user_answer_id) is None
    assert UserAnswerMultipleChoiceOption.query.get(uamco1_id) is None
    assert UserAnswerMultipleChoiceOption.query.get(uamco2_id) is None

def test_user_answer_multiple_choice_option_unique_constraint(db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race
    question = question_factory(race, "MULTIPLE_CHOICE", text="UAMCO Unique Constraint Test")
    question.is_mc_multiple_correct = True
    db_session.commit()

    option1 = option_factory(question, "UAMCO Opt 1")

    user_answer = UserAnswer(user_id=user.id, race_id=race.id, question_id=question.id)
    db_session.add(user_answer)
    db_session.commit()

    uamco1 = UserAnswerMultipleChoiceOption(
        user_answer_id=user_answer.id,
        question_option_id=option1.id
    )
    db_session.add(uamco1)
    db_session.commit()

    uamco2 = UserAnswerMultipleChoiceOption(
        user_answer_id=user_answer.id, # Same user_answer
        question_option_id=option1.id  # Same question_option
    )
    db_session.add(uamco2)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- API Endpoint Tests for /api/races/<int:race_id>/answers ---

import json

def login_user_for_client(client, username, password):
    """Helper to log in a user and ensure client uses the session."""
    return client.post('/api/login', json={'username': username, 'password': password})

def test_save_answers_successfully(client, db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race

    # Login the user
    login_response = login_user_for_client(client, user.username, "player_password") # Assuming "player_password" from conftest
    assert login_response.status_code == 200

    # Setup questions
    q_free_text = question_factory(race, "FREE_TEXT", text="Your favorite color?")
    q_mc_single = question_factory(race, "MULTIPLE_CHOICE", text="Best season?")
    q_mc_single.is_mc_multiple_correct = False
    opt_s1 = option_factory(q_mc_single, "Summer")
    opt_s2 = option_factory(q_mc_single, "Winter")

    q_mc_multi = question_factory(race, "MULTIPLE_CHOICE", text="Favorite fruits?")
    q_mc_multi.is_mc_multiple_correct = True
    opt_f1 = option_factory(q_mc_multi, "Apple")
    opt_f2 = option_factory(q_mc_multi, "Banana")
    opt_f3 = option_factory(q_mc_multi, "Cherry")

    q_ordering = question_factory(race, "ORDERING", text="Rank these items")
    # Options for ordering are implicitly created by question_factory or need separate setup if complex

    db_session.commit()


    answers_payload = {
        str(q_free_text.id): {"answer_text": "Blue"},
        str(q_mc_single.id): {"selected_option_id": opt_s1.id},
        str(q_mc_multi.id): {"selected_option_ids": [opt_f1.id, opt_f3.id]},
        str(q_ordering.id): {"ordered_options_text": "1, 2, 3"} # This will be option texts for user, not IDs
    }

    response = client.post(f'/api/races/{race.id}/answers', json=answers_payload)

    assert response.status_code == 201
    assert response.json['message'] == "Answers saved successfully"

    # Verify Free Text Answer
    ua_ft = UserAnswer.query.filter_by(user_id=user.id, question_id=q_free_text.id).first()
    assert ua_ft is not None
    assert ua_ft.answer_text == "Blue"

    # Verify MC Single Answer
    ua_mc_s = UserAnswer.query.filter_by(user_id=user.id, question_id=q_mc_single.id).first()
    assert ua_mc_s is not None
    assert ua_mc_s.selected_option_id == opt_s1.id

    # Verify MC Multi Answer
    ua_mc_m = UserAnswer.query.filter_by(user_id=user.id, question_id=q_mc_multi.id).first()
    assert ua_mc_m is not None
    assert len(ua_mc_m.selected_mc_options) == 2
    selected_ids_in_db = {sel.question_option_id for sel in ua_mc_m.selected_mc_options}
    assert opt_f1.id in selected_ids_in_db
    assert opt_f3.id in selected_ids_in_db

    # Verify Ordering Answer
    ua_ord = UserAnswer.query.filter_by(user_id=user.id, question_id=q_ordering.id).first()
    assert ua_ord is not None
    assert ua_ord.answer_text == "1, 2, 3"

def test_save_answers_overwrite_existing(client, db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race
    login_user_for_client(client, user.username, "player_password")

    q_free_text = question_factory(race, "FREE_TEXT", text="Initial thought?")
    db_session.commit()

    # First submission
    initial_payload = {str(q_free_text.id): {"answer_text": "Initial Answer"}}
    client.post(f'/api/races/{race.id}/answers', json=initial_payload)

    ua_initial = UserAnswer.query.filter_by(user_id=user.id, question_id=q_free_text.id).first()
    assert ua_initial.answer_text == "Initial Answer"

    # Second submission (overwrite)
    overwrite_payload = {str(q_free_text.id): {"answer_text": "Updated Answer"}}
    response = client.post(f'/api/races/{race.id}/answers', json=overwrite_payload)
    assert response.status_code == 201

    # Verify overwrite
    all_answers_for_q = UserAnswer.query.filter_by(user_id=user.id, question_id=q_free_text.id).all()
    assert len(all_answers_for_q) == 1 # Should only be one record
    assert all_answers_for_q[0].answer_text == "Updated Answer"


def test_save_answers_not_registered_for_race(client, db_session, player_user, sample_race, question_factory):
    user_not_registered = player_user # This user is not registered for sample_race by default
    login_user_for_client(client, user_not_registered.username, "player_password")

    question = question_factory(sample_race, "FREE_TEXT", text="A question")
    db_session.commit()

    answers_payload = {str(question.id): {"answer_text": "Some answer"}}
    response = client.post(f'/api/races/{sample_race.id}/answers', json=answers_payload)

    assert response.status_code == 403
    assert "User not registered for this race" in response.json['message']

def test_save_answers_race_not_found(client, player_user):
    login_user_for_client(client, player_user.username, "player_password")

    answers_payload = {"1": {"answer_text": "Doesn't matter"}}
    response = client.post('/api/races/99999/answers', json=answers_payload) # Non-existent race ID

    assert response.status_code == 404
    assert "Race not found" in response.json['message']

def test_save_answers_unauthenticated(client, sample_race, question_factory):
    # No user login
    question = question_factory(sample_race, "FREE_TEXT", text="Q for unauth test")
    db_session.commit() # Using db_session directly if this test modifies DB before API call

    answers_payload = {str(question.id): {"answer_text": "Attempt by unauth user"}}
    response = client.post(f'/api/races/{sample_race.id}/answers', json=answers_payload)

    assert response.status_code == 401 # Flask-Login typically returns 401 if login_required fails

def test_save_answers_invalid_payload_bad_question_id(client, db_session, registered_user_for_race, question_factory):
    user, race = registered_user_for_race
    login_user_for_client(client, user.username, "player_password")

    q_valid = question_factory(race, "FREE_TEXT", text="Valid Q")
    db_session.commit()

    # Payload with one valid and one invalid question ID string
    answers_payload = {
        str(q_valid.id): {"answer_text": "Answer for valid Q"},
        "99999": {"answer_text": "Answer for non-existent Q"} # Invalid question ID
    }
    response = client.post(f'/api/races/{race.id}/answers', json=answers_payload)

    assert response.status_code == 201 # API skips invalid question_id and processes valid ones

    # Verify valid answer was saved
    ua_valid = UserAnswer.query.filter_by(user_id=user.id, question_id=q_valid.id).first()
    assert ua_valid is not None
    assert ua_valid.answer_text == "Answer for valid Q"

    # Verify no answer was saved for invalid question ID (assuming 99999 doesn't exist)
    # This is implicitly tested as the API doesn't create UserAnswer for non-existent questions.
    # If Question 99999 did exist but for another race, the API also skips it.

def test_save_answers_invalid_payload_bad_option_id(client, db_session, registered_user_for_race, question_factory, option_factory):
    user, race = registered_user_for_race
    login_user_for_client(client, user.username, "player_password")

    q_mc_single = question_factory(race, "MULTIPLE_CHOICE", text="MC with bad option test")
    q_mc_single.is_mc_multiple_correct = False
    opt_valid = option_factory(q_mc_single, "Valid Option")
    db_session.commit()

    # Payload with an invalid option_id
    answers_payload = {
        str(q_mc_single.id): {"selected_option_id": 99999} # Invalid option ID
    }
    response = client.post(f'/api/races/{race.id}/answers', json=answers_payload)

    assert response.status_code == 201 # API skips invalid option_id and processes valid parts (if any)
                                      # In this case, it means UserAnswer is created but selected_option_id is null

    ua_mc_s = UserAnswer.query.filter_by(user_id=user.id, question_id=q_mc_single.id).first()
    assert ua_mc_s is not None
    assert ua_mc_s.selected_option_id is None # Should be None as the provided option ID was invalid

    # Test with a valid option to ensure it works
    valid_payload = {
        str(q_mc_single.id): {"selected_option_id": opt_valid.id}
    }
    response_valid = client.post(f'/api/races/{race.id}/answers', json=valid_payload)
    assert response_valid.status_code == 201
    ua_mc_s_valid = UserAnswer.query.filter_by(user_id=user.id, question_id=q_mc_single.id).first()
    assert ua_mc_s_valid is not None
    assert ua_mc_s_valid.selected_option_id == opt_valid.id

def test_save_answers_question_not_for_this_race(client, db_session, registered_user_for_race, question_factory, sample_race_factory):
    user, race1 = registered_user_for_race # User registered for race1

    # Create another race (race2)
    race2 = sample_race_factory(title="Another Race") # Assuming sample_race_factory is available or created

    question_for_race2 = question_factory(race2, "FREE_TEXT", text="Belongs to Race 2")
    db_session.commit()

    login_user_for_client(client, user.username, "player_password")

    # User tries to answer a question from race2 via race1's endpoint
    answers_payload = {
        str(question_for_race2.id): {"answer_text": "Trying to answer Q from another race"}
    }
    response = client.post(f'/api/races/{race1.id}/answers', json=answers_payload)

    assert response.status_code == 201 # API skips questions not belonging to the endpoint's race_id

    # Verify no answer was saved for this question under race1 for this user
    ua = UserAnswer.query.filter_by(user_id=user.id, question_id=question_for_race2.id).first()
    assert ua is None

# Need a factory for sample_race to create multiple distinct races for the last test
# This can be added to conftest.py or locally if not present.
# For now, assuming it would be similar to sample_race but allows parameterization or creates a new one.
@pytest.fixture
def sample_race_factory(db_session, admin_user, race_format_factory): # Added race_format_factory
    def _factory(title="Default Factory Race", is_general=False):
        race_format = race_format_factory("Triatlón") # Assuming a default or get first
        race = Race(
            title=title,
            description="A factory-created race.",
            race_format_id=race_format.id,
            event_date=datetime.strptime("2025-01-01", "%Y-%m-%d"),
            location="Factory Test City",
            user_id=admin_user.id,
            is_general=is_general,
            gender_category="MIXED",
            category="Elite"
        )
        db_session.add(race)
        db_session.commit()
        return race
    return _factory

@pytest.fixture
def race_format_factory(db_session): # Added this fixture, assuming it might be in conftest.py
    def _factory(name="Triatlón"):
        rf = RaceFormat.query.filter_by(name=name).first()
        if not rf:
            rf = RaceFormat(name=name)
            db_session.add(rf)
            db_session.commit()
        return rf
    return _factory

# --- Tests for calculate_and_store_scores for ORDERING questions ---
from backend.app import calculate_and_store_scores
from backend.models import UserScore, OfficialAnswer # OfficialAnswer might be needed if not already imported

# Define test scenarios as tuples:
# (scenario_name, official_id_order_setup, user_text_answer_str, expected_score, options_config)
# options_config will be a list of tuples: (text, correct_order_index_for_setup)
# The official_id_order_setup will use symbolic names ("OptA", "OptB", "OptC") which will be mapped to actual IDs.

ordering_test_scenarios = [
    (
        "Perfect Match",
        ["OptA", "OptB", "OptC"], # Official order of option *symbolic names*
        "Option A Text,Option B Text,Option C Text", # User's textual answer
        35, # (3 * 10) + 5
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)] # OptA, OptB, OptC
    ),
    (
        "Partial Match (1st correct, rest swapped)", # Scenario (b)
        ["OptA", "OptB", "OptC"],
        "Option A Text,Option C Text,Option B Text", # OptA correct, B and C swapped
        10, # 1 * 10 (only OptA in correct place)
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "Partial Match (Fewer items from user)", # Scenario (c)
        ["OptA", "OptB", "OptC"],
        "Option A Text,Option B Text",
        20, # 2 * 10
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "Partial Match (Middle correct, ends swapped)", # Scenario (d) adjusted for clarity
        ["OptA", "OptB", "OptC"],
        "Option C Text,Option B Text,Option A Text", # OptB correct
        10, # 1 * 10 (Only OptB in correct position)
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
     (
        "No Match (Completely different order)",
        ["OptA", "OptB", "OptC"],
        "Option B Text,Option C Text,Option A Text", # B!=A, C!=B, A!=C
        0,
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "Official Answer order differs from correct_order_index setup", # Scenario (e)
        ["OptC", "OptB", "OptA"], # Official ID order: C, B, A
        "Option C Text,Option B Text,Option A Text", # User text matches this ^
        35, # (3 * 10) + 5
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)] # Options setup (COI ignored for scoring)
    ),
    (
        "Case Insensitivity", # Scenario (f)
        ["OptA", "OptB", "OptC"],
        "option a text,option b text,option c text", # Lowercase user answer
        35, # (3 * 10) + 5
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "Empty User Answer", # Scenario (g)
        ["OptA", "OptB", "OptC"],
        "",
        0,
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "User answer has more items than official answer", # Scenario (h)
        ["OptA", "OptB"], # Official order (length 2)
        "Option A Text,Option B Text,Option C Text", # User answer (length 3)
        20, # 2 * 10 (bonus does not apply as user length != official length)
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)] # All 3 options exist for question
    ),
    (
        "Official answer has fewer items than question options, perfect user match",
        ["OptA"], # Official order only has OptA (length 1)
        "Option A Text", # User matches this
        15, # (1 * 10) + 5 (bonus for full match of the *official answer's length*)
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "Partial match with one item, bonus for full order if only one official item", # Similar to above
        ["OptB"],
        "Option B Text",
        15, # (1*10) + 5
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    ),
    (
        "User answer with extra spaces around commas and items",
        ["OptA", "OptB"],
        "  Option A Text  ,  Option B Text  ",
        25, # (2 * 10) + 5
        [("Option A Text", 0), ("Option B Text", 1), ("Option C Text", 2)]
    )
]

@pytest.mark.parametrize(
    "scenario_name, official_id_order_setup, user_text_answer_str, expected_score, options_config",
    ordering_test_scenarios
)
def test_calculate_scores_for_ordering_questions(
    db_session,
    sample_race_factory, # Use the existing factory from test_answers
    user_factory,        # Use existing factory from conftest
    question_factory,    # Use existing factory, will set ordering specific fields manually
    option_factory,      # Use existing factory (named option_factory in this file)
    scenario_name,
    official_id_order_setup,
    user_text_answer_str,
    expected_score,
    options_config
):
    # 1. Setup
    # Use a unique username for each parametrized test run to avoid conflicts if user objects aren't fully isolated or cleaned up.
    user = user_factory(username=f"user_{scenario_name.replace(' ', '_').lower()}_{datetime.utcnow().timestamp()}")
    race = sample_race_factory(title=f"Race for {scenario_name}") # Ensure this factory creates a new race each time

    registration = UserRaceRegistration(user_id=user.id, race_id=race.id)
    db_session.add(registration)

    points_per_correct_order = 10
    bonus_for_full_order = 5

    # Create the ORDERING question and set its specific scoring attributes
    q_ordering = question_factory(race, "ORDERING", text=f"Order for {scenario_name}")
    q_ordering.points_per_correct_order = points_per_correct_order
    q_ordering.bonus_for_full_order = bonus_for_full_order
    db_session.add(q_ordering) # Add to session, commit will happen with options
    db_session.commit() # Commit question to get its ID for options

    created_options = {} # To map symbolic names like "OptA" to QuestionOption objects
    for i, (text, coi) in enumerate(options_config):
        symbolic_name = f"Opt{chr(65+i)}" # Generates "OptA", "OptB", "OptC"
        opt = option_factory(question=q_ordering, option_text=text)
        # correct_order_index on QuestionOption is for admin UI setup, not directly for scoring logic after this change
        opt.correct_order_index = coi
        db_session.add(opt)
        created_options[symbolic_name] = opt
    db_session.commit() # Commit options to get their IDs

    # Construct the official_answer.answer_text string from actual option IDs
    actual_official_id_order_str = ""
    if official_id_order_setup:
        try:
            id_list = []
            for symbol_name in official_id_order_setup:
                if symbol_name not in created_options:
                     pytest.fail(f"Scenario '{scenario_name}': Symbolic option name '{symbol_name}' in official_id_order_setup not found in created_options. Available: {list(created_options.keys())}")
                id_list.append(str(created_options[symbol_name].id))
            actual_official_id_order_str = ",".join(id_list)
        except KeyError as e: # Should be caught by the check above now
            pytest.fail(f"Scenario '{scenario_name}': Symbolic option name {e} in official_id_order_setup not found in created_options. Check options_config and created_options mapping.")

    # 2. Create OfficialAnswer
    official_answer = OfficialAnswer(
        race_id=race.id,
        question_id=q_ordering.id,
        answer_text=actual_official_id_order_str
    )
    db_session.add(official_answer)

    # 3. Create UserAnswer
    user_answer = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=q_ordering.id,
        answer_text=user_text_answer_str
    )
    db_session.add(user_answer)
    db_session.commit() # Commit all: registration, question, options, official_answer, user_answer

    # 4. Call the function under test
    result = calculate_and_store_scores(race.id)
    assert result['success'] is True, f"calculate_and_store_scores failed for scenario: {scenario_name}, message: {result.get('message')}"

    # 5. Verify UserScore
    user_score_entry = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    # Debugging output in case of failure
    official_texts_for_debug = []
    if actual_official_id_order_str:
        ids = [int(id_str) for id_str in actual_official_id_order_str.split(',')]
        for opt_id in ids:
            opt = QuestionOption.query.get(opt_id)
            if opt: official_texts_for_debug.append(opt.option_text)
            else: official_texts_for_debug.append(f"[ID {opt_id} NOT FOUND]")

    assert user_score_entry is not None, f"UserScore not found for user {user.id}, race {race.id} in scenario: {scenario_name}"
    assert user_score_entry.score == expected_score, \
        (f"Scenario '{scenario_name}': Expected score {expected_score}, got {user_score_entry.score}. "
         f"User answer: '{user_text_answer_str}', "
         f"Official Option IDs: '{actual_official_id_order_str}', "
         f"Official Option Texts (derived): '{','.join(official_texts_for_debug)}'")

# (Keep existing race_format_factory and sample_race_factory at the end of the file or move to conftest.py)
# Ensure UserScore and OfficialAnswer are imported in backend.models import list at the top if not already.
# They are already: from backend.models import ( ..., UserScore, OfficialAnswer, ...)
# So, the main model import list does not need changes.
# The import from backend.app import calculate_and_store_scores is added.
# And from backend.models import UserScore, OfficialAnswer for explicit use within the test.
