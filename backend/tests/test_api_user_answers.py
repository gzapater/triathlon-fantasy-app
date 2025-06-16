import pytest
from backend.models import db, UserAnswer, Question # Assuming other necessary imports like User, Race are in conftest

def test_submit_slider_answer_success(client, authenticated_user, sample_slider_question, sample_race_registration):
    """Test submitting a valid slider answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    payload = {
        str(question_id): { # Answers are keyed by question_id as string
            "slider_answer_value": 35.5
        }
    }

    response = client.post(f'/api/races/{race_id}/answers', json=payload, headers=headers)

    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == "Answers saved successfully"

    user_answer_in_db = UserAnswer.query.filter_by(
        user_id=authenticated_user['id'],
        question_id=question_id
    ).first()

    assert user_answer_in_db is not None
    assert user_answer_in_db.slider_answer_value == 35.5
    assert user_answer_in_db.answer_text is None
    assert user_answer_in_db.selected_option_id is None

def test_submit_slider_answer_invalid_value(client, authenticated_user, sample_slider_question, sample_race_registration):
    """Test submitting a slider answer with an invalid (non-numeric) value."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
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
    response = client.post(f'/api/races/{race_id}/answers', json=payload, headers=headers)
    assert response.status_code == 201 # Still 201 as it saves other valid answers or nullifies this one

    user_answer_in_db = UserAnswer.query.filter_by(
        user_id=authenticated_user['id'],
        question_id=question_id
    ).first()
    assert user_answer_in_db is not None
    assert user_answer_in_db.slider_answer_value is None # Should be stored as None

def test_get_user_slider_answer(client, authenticated_user, sample_slider_question, sample_race_registration):
    """Test retrieving user answers including a slider answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    # First, submit an answer
    UserAnswer.query.delete() # Clear previous
    db.session.commit()

    user_answer = UserAnswer(
        user_id=authenticated_user['id'],
        race_id=race_id,
        question_id=question_id,
        slider_answer_value=42.0
    )
    db.session.add(user_answer)
    db.session.commit()

    response = client.get(f'/api/races/{race_id}/user_answers', headers=headers)
    assert response.status_code == 200
    data = response.get_json()

    assert isinstance(data, list)
    retrieved_answer = next((ans for ans in data if ans['question_id'] == question_id), None)

    assert retrieved_answer is not None
    assert retrieved_answer['question_type'] == 'SLIDER'
    assert retrieved_answer['slider_answer_value'] == 42.0

def test_update_user_slider_answer_success(client, authenticated_user, sample_slider_question, sample_race_registration):
    """Test updating a user's slider answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_slider_question.race_id
    question_id = sample_slider_question.id

    # Initial answer
    initial_answer = UserAnswer(
        user_id=authenticated_user['id'],
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

    response = client.put(f'/api/user_answers/{user_answer_id}', json=update_payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == "Answer updated successfully"

    updated_answer_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_answer_in_db is not None
    assert updated_answer_in_db.slider_answer_value == 30.5

def test_update_user_slider_answer_clear_value(client, authenticated_user, sample_slider_question, sample_race_registration):
    """Test clearing a user's slider answer by sending null."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    initial_answer = UserAnswer(
        user_id=authenticated_user['id'],
        race_id=sample_slider_question.race_id,
        question_id=sample_slider_question.id,
        slider_answer_value=25.0
    )
    db.session.add(initial_answer)
    db.session.commit()
    user_answer_id = initial_answer.id

    update_payload = {"slider_answer_value": None}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=update_payload, headers=headers)

    assert response.status_code == 200
    updated_answer_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_answer_in_db.slider_answer_value is None

def test_update_user_slider_answer_invalid_value(client, authenticated_user, sample_slider_question, sample_race_registration):
    """Test updating a user's slider answer with an invalid value."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    initial_answer = UserAnswer(
        user_id=authenticated_user['id'],
        race_id=sample_slider_question.race_id,
        question_id=sample_slider_question.id,
        slider_answer_value=25.0
    )
    db.session.add(initial_answer)
    db.session.commit()
    user_answer_id = initial_answer.id

    update_payload = {"slider_answer_value": "not-a-valid-float"}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=update_payload, headers=headers)

    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid 'slider_answer_value'" in data['message']

    # Ensure original value is unchanged
    answer_in_db = UserAnswer.query.get(user_answer_id)
    assert answer_in_db.slider_answer_value == 25.0
