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

# --- Tests for the new PUT /api/user_answers/<user_answer_id> endpoint ---

def test_update_user_answer_free_text_success(client, authenticated_user, sample_question_ft, sample_race_registration):
    """Test successfully updating a free text answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_question_ft.race_id
    question_id = sample_question_ft.id

    # Create an initial answer
    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=race_id, question_id=question_id, answer_text="Initial answer")
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    payload = {"answer_text": "Updated answer"}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == "Answer updated successfully"
    assert data['updated_answer']['id'] == user_answer_id
    assert data['updated_answer']['answer_text'] == "Updated answer"

    updated_ua_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_ua_in_db.answer_text == "Updated answer"
    assert updated_ua_in_db.selected_option_id is None
    assert updated_ua_in_db.slider_answer_value is None

def test_update_user_answer_mc_single_success(client, authenticated_user, sample_question_mc_single, sample_race_registration):
    """Test successfully updating a single-choice MC answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_question_mc_single.race_id
    question_id = sample_question_mc_single.id
    option_to_select = sample_question_mc_single.options.first()

    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=race_id, question_id=question_id, selected_option_id=None)
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    payload = {"selected_option_id": option_to_select.id}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['updated_answer']['selected_option_id'] == option_to_select.id

    updated_ua_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_ua_in_db.selected_option_id == option_to_select.id
    assert updated_ua_in_db.answer_text is None

def test_update_user_answer_mc_multiple_success(client, authenticated_user, sample_question_mc_multiple, sample_race_registration):
    """Test successfully updating a multiple-choice MC answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_question_mc_multiple.race_id
    question_id = sample_question_mc_multiple.id
    options_to_select = [opt.id for opt in sample_question_mc_multiple.options.limit(2)]

    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=race_id, question_id=question_id)
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    payload = {"selected_option_ids": options_to_select}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    # Ensure selected_mc_options in response matches (ignoring order)
    response_selected_ids = {opt['option_id'] for opt in data['updated_answer']['selected_mc_options']}
    assert response_selected_ids == set(options_to_select)


    updated_ua_in_db = UserAnswer.query.get(user_answer_id)
    db_selected_ids = {sel_opt.question_option_id for sel_opt in updated_ua_in_db.selected_mc_options}
    assert db_selected_ids == set(options_to_select)
    assert updated_ua_in_db.answer_text is None

def test_update_user_answer_ordering_success(client, authenticated_user, sample_question_ordering, sample_race_registration):
    """Test successfully updating an ordering answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_question_ordering.race_id
    question_id = sample_question_ordering.id

    # Assuming options are 'Option A', 'Option B', 'Option C'
    ordered_texts = "Option C,Option A,Option B"

    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=race_id, question_id=question_id, answer_text="Initial order")
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    payload = {"answer_text": ordered_texts} # Frontend uses 'answer_text' for ordering payload
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['updated_answer']['answer_text'] == ordered_texts

    updated_ua_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_ua_in_db.answer_text == ordered_texts

def test_update_user_answer_not_owned(client, authenticated_user, other_user, sample_question_ft, sample_race_registration):
    """Test updating an answer not owned by the current user."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'} # Current user is authenticated_user

    # Answer created by other_user
    other_user_answer = UserAnswer(user_id=other_user.id, race_id=sample_question_ft.race_id, question_id=sample_question_ft.id, answer_text="Other user's answer")
    db.session.add(other_user_answer)
    db.session.commit()
    user_answer_id = other_user_answer.id

    payload = {"answer_text": "Attempted update"}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)

    assert response.status_code == 403
    data = response.get_json()
    assert "Forbidden" in data['message']

def test_update_user_answer_race_closed(client, authenticated_user, sample_question_ft, sample_race_registration_closed_quiniela):
    """Test updating an answer when the race quiniela is closed."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    race_id = sample_question_ft.race_id # This race's quiniela is closed by the fixture
    question_id = sample_question_ft.id

    user_answer = UserAnswer(user_id=authenticated_user['id'], race_id=race_id, question_id=question_id, answer_text="Before close")
    db.session.add(user_answer)
    db.session.commit()
    user_answer_id = user_answer.id

    payload = {"answer_text": "After close attempt"}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)

    assert response.status_code == 403
    data = response.get_json()
    assert "quiniela for this race is closed" in data['message']

def test_update_user_answer_not_found(client, authenticated_user):
    """Test updating a non-existent user answer."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    non_existent_id = 99999
    payload = {"answer_text": "Update for non-existent"}
    response = client.put(f'/api/user_answers/{non_existent_id}', json=payload, headers=headers)

    assert response.status_code == 404
    data = response.get_json()
    assert "Answer not found" in data['message']

def test_update_user_answer_invalid_payload_mc_multiple(client, authenticated_user, sample_question_mc_multiple, sample_race_registration):
    """Test updating MC-multiple with invalid payload (not a list)."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=sample_question_mc_multiple.race_id, question_id=sample_question_mc_multiple.id)
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    payload = {"selected_option_ids": "not-a-list"}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)
    assert response.status_code == 400
    assert "'selected_option_ids' must be a list" in response.get_json()['message']

def test_update_user_answer_invalid_option_id_mc_single(client, authenticated_user, sample_question_mc_single, sample_race_registration):
    """Test updating MC-single with an option ID that doesn't belong to the question."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=sample_question_mc_single.race_id, question_id=sample_question_mc_single.id)
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    invalid_option_id = 98765 # An ID that certainly doesn't exist or belong
    payload = {"selected_option_id": invalid_option_id}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)
    assert response.status_code == 400 # Or 404 if option not found is treated that way by endpoint
    assert f"Invalid option ID {invalid_option_id}" in response.get_json()['message']

def test_update_user_answer_clear_mc_single(client, authenticated_user, sample_question_mc_single, sample_race_registration):
    """Test clearing a single-choice MC answer by sending null."""
    headers = {'Authorization': f'Bearer {authenticated_user["access_token"]}'}
    option_to_select = sample_question_mc_single.options.first()
    initial_ua = UserAnswer(user_id=authenticated_user['id'], race_id=sample_question_mc_single.race_id, question_id=sample_question_mc_single.id, selected_option_id=option_to_select.id)
    db.session.add(initial_ua)
    db.session.commit()
    user_answer_id = initial_ua.id

    payload = {"selected_option_id": None}
    response = client.put(f'/api/user_answers/{user_answer_id}', json=payload, headers=headers)
    assert response.status_code == 200
    updated_ua_in_db = UserAnswer.query.get(user_answer_id)
    assert updated_ua_in_db.selected_option_id is None
