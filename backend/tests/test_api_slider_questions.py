import pytest
from flask import jsonify
from backend.models import db, Race, Question, QuestionType, User, Role

def test_create_slider_question_success(client, authenticated_user_admin, sample_race):
    """Test creating a slider question successfully."""
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}

    race_id = sample_race.id
    payload = {
        "text": "What is the expected average speed in km/h?",
        "is_active": True,
        "slider_unit": "km/h",
        "slider_min_value": 10.0,
        "slider_max_value": 50.0,
        "slider_step": 0.5,
        "slider_points_exact": 100,
        "slider_threshold_partial": 2.0,
        "slider_points_partial": 50
    }

    response = client.post(f'/api/races/{race_id}/questions/slider', json=payload, headers=headers)

    assert response.status_code == 201
    data = response.get_json()
    assert data['text'] == payload['text']
    assert data['question_type'] == 'SLIDER'
    assert data['slider_unit'] == payload['slider_unit']
    assert data['slider_min_value'] == payload['slider_min_value']
    assert data['slider_max_value'] == payload['slider_max_value']
    assert data['slider_step'] == payload['slider_step']
    assert data['slider_points_exact'] == payload['slider_points_exact']
    assert data['slider_threshold_partial'] == payload['slider_threshold_partial']
    assert data['slider_points_partial'] == payload['slider_points_partial']

    question_in_db = Question.query.get(data['id'])
    assert question_in_db is not None
    assert question_in_db.question_type.name == 'SLIDER'

def test_create_slider_question_invalid_data(client, authenticated_user_admin, sample_race):
    """Test creating a slider question with invalid data."""
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}
    race_id = sample_race.id

    # Missing required fields
    payload_missing = {"text": "Test"}
    response_missing = client.post(f'/api/races/{race_id}/questions/slider', json=payload_missing, headers=headers)
    assert response_missing.status_code == 400

    # Min value >= Max value
    payload_min_max = {
        "text": "Min Max Test", "slider_min_value": 50.0, "slider_max_value": 10.0,
        "slider_step": 1.0, "slider_points_exact": 10
    }
    response_min_max = client.post(f'/api/races/{race_id}/questions/slider', json=payload_min_max, headers=headers)
    assert response_min_max.status_code == 400
    assert "slider_min_value must be less than slider_max_value" in response_min_max.get_json()['message']

    # Invalid step (zero or negative)
    payload_step = {
        "text": "Step Test", "slider_min_value": 10.0, "slider_max_value": 50.0,
        "slider_step": 0, "slider_points_exact": 10
    }
    response_step = client.post(f'/api/races/{race_id}/questions/slider', json=payload_step, headers=headers)
    assert response_step.status_code == 400
    assert "slider_step must be a positive number" in response_step.get_json()['message']

    # Non-numeric points
    payload_points = {
        "text": "Points Test", "slider_min_value": 10.0, "slider_max_value": 50.0,
        "slider_step": 1.0, "slider_points_exact": "not-a-number"
    }
    response_points = client.post(f'/api/races/{race_id}/questions/slider', json=payload_points, headers=headers)
    assert response_points.status_code == 400 # Expecting validation for integer type

def test_update_slider_question_success(client, authenticated_user_admin, sample_slider_question):
    """Test updating a slider question successfully."""
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}
    question_id = sample_slider_question.id

    payload = {
        "text": "Updated: What is the expected average speed in km/h?",
        "is_active": False,
        "slider_unit": "mph",
        "slider_min_value": 5.0,
        "slider_max_value": 60.0,
        "slider_step": 1.0,
        "slider_points_exact": 150,
        "slider_threshold_partial": 1.0,
        "slider_points_partial": 75
    }

    response = client.put(f'/api/questions/slider/{question_id}', json=payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['text'] == payload['text']
    assert data['is_active'] == payload['is_active']
    assert data['slider_unit'] == payload['slider_unit']
    assert data['slider_min_value'] == payload['slider_min_value']
    assert data['slider_max_value'] == payload['slider_max_value']
    assert data['slider_step'] == payload['slider_step']
    assert data['slider_points_exact'] == payload['slider_points_exact']
    assert data['slider_threshold_partial'] == payload['slider_threshold_partial']
    assert data['slider_points_partial'] == payload['slider_points_partial']

    question_in_db = Question.query.get(question_id)
    assert question_in_db.text == payload['text']
    assert question_in_db.slider_unit == payload['slider_unit']

def test_update_slider_question_partial_update(client, authenticated_user_admin, sample_slider_question):
    """Test partially updating a slider question."""
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}
    question_id = sample_slider_question.id

    payload = {"slider_points_exact": 200}
    response = client.put(f'/api/questions/slider/{question_id}', json=payload, headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['slider_points_exact'] == 200
    # Ensure other fields remain unchanged
    assert data['text'] == sample_slider_question.text
    assert data['slider_min_value'] == sample_slider_question.slider_min_value

def test_update_slider_question_invalid_data(client, authenticated_user_admin, sample_slider_question):
    """Test updating a slider question with invalid data."""
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}
    question_id = sample_slider_question.id

    payload_min_max = {"slider_min_value": 60.0, "slider_max_value": 10.0}
    response_min_max = client.put(f'/api/questions/slider/{question_id}', json=payload_min_max, headers=headers)
    assert response_min_max.status_code == 400
    assert "slider_min_value must be less than slider_max_value" in response_min_max.get_json()['message']

def test_update_non_slider_question_via_slider_endpoint(client, authenticated_user_admin, sample_free_text_question):
    """Test updating a non-slider question via slider endpoint."""
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}
    question_id = sample_free_text_question.id # This is a FREE_TEXT question

    payload = {"slider_points_exact": 100}
    response = client.put(f'/api/questions/slider/{question_id}', json=payload, headers=headers)
    assert response.status_code == 400 # Expecting error as it's not a slider question
    assert "Cannot update non-SLIDER question via this endpoint" in response.get_json()['message']

def test_update_slider_question_not_found(client, authenticated_user_admin):
    headers = {'Authorization': f'Bearer {authenticated_user_admin["access_token"]}'}
    response = client.put('/api/questions/slider/99999', json={"text": "test"}, headers=headers)
    assert response.status_code == 404

def test_create_slider_question_unauthorized(client, sample_race):
    race_id = sample_race.id
    payload = {"text": "Test"}
    response = client.post(f'/api/races/{race_id}/questions/slider', json=payload) # No auth header
    assert response.status_code == 401 # Or 302 if redirecting to login

def test_update_slider_question_unauthorized(client, sample_slider_question):
    question_id = sample_slider_question.id
    payload = {"text": "Test"}
    response = client.put(f'/api/questions/slider/{question_id}', json=payload) # No auth header
    assert response.status_code == 401 # Or 302
