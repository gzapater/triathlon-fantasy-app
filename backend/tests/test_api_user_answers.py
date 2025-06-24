import pytest
from backend.models import db, UserAnswer, Question # Assuming other necessary imports like User, Race are in conftest

def test_submit_slider_answer_success(authenticated_client, sample_slider_question, sample_race_registration): # Changed fixture
    """Test submitting a valid slider answer."""
    client, user = authenticated_client("PLAYER") # Use factory, assuming PLAYER role for submitting answers
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    payload = {
        str(question_id): { # Answers are keyed by question_id as string
            "slider_answer_value": 35.5
        }
    }

    response = client.post(f'/api/races/{race_id}/answers', json=payload) # Removed headers

    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == "Answers saved successfully"

    user_answer_in_db = UserAnswer.query.filter_by(
        user_id=user.id, # Use user from factory
        question_id=question_id
    ).first()

    assert user_answer_in_db is not None
    assert user_answer_in_db.slider_answer_value == 35.5
    assert user_answer_in_db.answer_text is None
    assert user_answer_in_db.selected_option_id is None

def test_submit_slider_answer_invalid_value(authenticated_client, sample_slider_question, sample_race_registration): # Changed fixture
    """Test submitting a slider answer with an invalid (non-numeric) value."""
    client, user = authenticated_client("PLAYER") # Use factory
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    payload = {
        str(question_id): {
            "slider_answer_value": "not-a-number"
        }
    }

    # The backend currently logs a warning and stores None for invalid slider values during POST.
    # It doesn't return a 400 for this specific case in save_user_answers.
    # Depending on desired strictness, this could be a 400. For now, test current behavior.
    response = client.post(f'/api/races/{race_id}/answers', json=payload) # Removed headers
    assert response.status_code == 201 # Still 201 as it saves other valid answers or nullifies this one

    user_answer_in_db = UserAnswer.query.filter_by(
        user_id=user.id, # Use user from factory
        question_id=question_id
    ).first()
    assert user_answer_in_db is not None
    assert user_answer_in_db.slider_answer_value is None # Should be stored as None

def test_get_user_slider_answer(authenticated_client, sample_slider_question, sample_race_registration): # Changed fixture
    """Test retrieving user answers including a slider answer."""
    client, user = authenticated_client("PLAYER") # Use factory
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    # First, submit an answer
    UserAnswer.query.delete() # Clear previous
    db.session.commit()

    user_answer = UserAnswer(
        user_id=user.id, # Use user from factory
        race_id=race_id,
        question_id=question_id,
        slider_answer_value=42.0
    )
    db.session.add(user_answer)
    db.session.commit()

    response = client.get(f'/api/races/{race_id}/user_answers') # Removed headers
    assert response.status_code == 200
    data = response.get_json()

    # The response structure is {"answers": [...], "num_total_questions": X, "num_answered_questions": Y}
    assert "answers" in data
    assert isinstance(data["answers"], list)
    retrieved_answer = next((ans for ans in data["answers"] if ans['question_id'] == question_id), None)

    assert retrieved_answer is not None
    assert retrieved_answer['question_type'] == 'SLIDER'
    assert retrieved_answer['slider_answer_value'] == 42.0

def test_update_user_slider_answer_success(authenticated_client, sample_slider_question, sample_race_registration): # Changed fixture
    """Test updating a user's slider answer."""
    client, user = authenticated_client("PLAYER") # Use factory
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    # Initial answer
    initial_answer = UserAnswer(
        user_id=user.id, # Use user from factory
        race_id=race_id,
        question_id=question_id,
        slider_answer_value=25.0
    )
    db.session.add(initial_answer)
    db.session.commit()
    user_answer_id = initial_answer.id

    update_payload = {
        "slider_answer_value": 30.5
    }

    response = client.put(f'/api/user_answers/{user_answer_id}', json=update_payload) # Removed headers

    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == "Answer updated successfully"

    updated_answer_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_answer_in_db is not None
    assert updated_answer_in_db.slider_answer_value == 30.5

def test_update_user_slider_answer_clear_value(authenticated_client, sample_slider_question, sample_race_registration): # Changed fixture
    """Test clearing a user's slider answer by sending null."""
    client, user = authenticated_client("PLAYER") # Use factory
    initial_answer = UserAnswer(
        user_id=user.id, # Use user from factory
        race_id=sample_slider_question.race_id,
        question_id=sample_slider_question.id,
        slider_answer_value=25.0
    )
    db.session.add(initial_answer)
    db.session.commit()
    user_answer_id = initial_answer.id

    update_payload = {"slider_answer_value": None}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=update_payload) # Removed headers

    assert response.status_code == 200
    updated_answer_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_answer_in_db.slider_answer_value is None

def test_update_user_slider_answer_invalid_value(authenticated_client, sample_slider_question, sample_race_registration): # Changed fixture
    """Test updating a user's slider answer with an invalid value."""
    client, user = authenticated_client("PLAYER") # Use factory
    initial_answer = UserAnswer(
        user_id=user.id, # Use user from factory
        race_id=sample_slider_question.race_id,
        question_id=sample_slider_question.id,
        slider_answer_value=25.0
    )
    db.session.add(initial_answer)
    db.session.commit()
    user_answer_id = initial_answer.id

    update_payload = {"slider_answer_value": "not-a-valid-float"}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=update_payload) # Removed headers

    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid 'slider_answer_value'" in data['message']

    # Ensure original value is unchanged
    answer_in_db = UserAnswer.query.get(user_answer_id)
    assert answer_in_db.slider_answer_value == 25.0
