import pytest
import json
from backend.models import db, Race, Question, QuestionType, QuestionOption, OfficialAnswer, OfficialAnswerMultipleChoiceOption

# Helper to create questions of various types for a race
def setup_questions_for_race(db_session, race_id):
    qt_free_text = QuestionType.query.filter_by(name='FREE_TEXT').first()
    qt_mc = QuestionType.query.filter_by(name='MULTIPLE_CHOICE').first()
    qt_ordering = QuestionType.query.filter_by(name='ORDERING').first()

    if not all([qt_free_text, qt_mc, qt_ordering]):
        # This should ideally be seeded by conftest or app setup
        if not qt_free_text: qt_free_text = QuestionType(name='FREE_TEXT'); db_session.add(qt_free_text)
        if not qt_mc: qt_mc = QuestionType(name='MULTIPLE_CHOICE'); db_session.add(qt_mc)
        if not qt_ordering: qt_ordering = QuestionType(name='ORDERING'); db_session.add(qt_ordering)
        db_session.commit()

    q1_text = Question(race_id=race_id, question_type_id=qt_free_text.id, text="Overall winner?")
    q2_mc_single = Question(race_id=race_id, question_type_id=qt_mc.id, text="Fastest swim?", is_mc_multiple_correct=False)
    q3_mc_multi = Question(race_id=race_id, question_type_id=qt_mc.id, text="Podium finishers (select up to 3)?", is_mc_multiple_correct=True)
    q4_ordering = Question(race_id=race_id, question_type_id=qt_ordering.id, text="Order top 2 by run split:")

    db_session.add_all([q1_text, q2_mc_single, q3_mc_multi, q4_ordering])
    db_session.commit()

    # Options for MC Single
    opt_s1 = QuestionOption(question_id=q2_mc_single.id, option_text="Athlete A")
    opt_s2 = QuestionOption(question_id=q2_mc_single.id, option_text="Athlete B")
    db_session.add_all([opt_s1, opt_s2])

    # Options for MC Multi
    opt_m1 = QuestionOption(question_id=q3_mc_multi.id, option_text="Athlete X")
    opt_m2 = QuestionOption(question_id=q3_mc_multi.id, option_text="Athlete Y")
    opt_m3 = QuestionOption(question_id=q3_mc_multi.id, option_text="Athlete Z")
    db_session.add_all([opt_m1, opt_m2, opt_m3])

    # Options for Ordering
    opt_o1 = QuestionOption(question_id=q4_ordering.id, option_text="Runner P", correct_order_index=0)
    opt_o2 = QuestionOption(question_id=q4_ordering.id, option_text="Runner Q", correct_order_index=1)
    db_session.add_all([opt_o1, opt_o2])

    db_session.commit()
    return {
        "q_text": q1_text, "q_mc_single": q2_mc_single, "q_mc_multi": q3_mc_multi, "q_ordering": q4_ordering,
        "opts_s": [opt_s1, opt_s2], "opts_m": [opt_m1, opt_m2, opt_m3], "opts_o": [opt_o1, opt_o2]
    }

# --- GET /api/races/<race_id>/official_answers Tests ---

def test_get_official_answers_admin(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("ADMIN")
    questions_data = setup_questions_for_race(db_session, sample_race.id)

    # Pre-populate an official answer
    oa = OfficialAnswer(race_id=sample_race.id, question_id=questions_data["q_text"].id, answer_text="Admin Answer")
    db_session.add(oa)
    db_session.commit()

    response = client.get(f'/api/races/{sample_race.id}/official_answers')
    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]['question_id'] == questions_data["q_text"].id
    assert data[0]['answer_text'] == "Admin Answer"

def test_get_official_answers_league_admin(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("LEAGUE_ADMIN")
    setup_questions_for_race(db_session, sample_race.id) # Setup questions
    response = client.get(f'/api/races/{sample_race.id}/official_answers')
    assert response.status_code == 200 # League admins can view

def test_get_official_answers_player_forbidden(authenticated_client, sample_race):
    client, _ = authenticated_client("PLAYER")
    response = client.get(f'/api/races/{sample_race.id}/official_answers')
    assert response.status_code == 403

def test_get_official_answers_unauthenticated(client, sample_race):
    response = client.get(f'/api/races/{sample_race.id}/official_answers')
    assert response.status_code == 401 # Or redirect, depending on Flask-Login config

def test_get_official_answers_non_existent_race(authenticated_client):
    client, _ = authenticated_client("ADMIN")
    response = client.get('/api/races/9999/official_answers')
    assert response.status_code == 404

def test_get_official_answers_empty(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("ADMIN")
    setup_questions_for_race(db_session, sample_race.id) # Ensure questions exist, but no answers
    response = client.get(f'/api/races/{sample_race.id}/official_answers')
    assert response.status_code == 200
    assert response.json == []


# --- POST /api/races/<race_id>/official_answers Tests ---

def test_post_official_answers_admin(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("ADMIN")
    q_data = setup_questions_for_race(db_session, sample_race.id)

    payload = {
        str(q_data["q_text"].id): {"answer_text": "Test Winner"},
        str(q_data["q_mc_single"].id): {"selected_option_id": q_data["opts_s"][0].id},
        str(q_data["q_mc_multi"].id): {"selected_option_ids": [q_data["opts_m"][0].id, q_data["opts_m"][1].id]},
        str(q_data["q_ordering"].id): {"ordered_options_text": f"{q_data['opts_o'][0].option_text}\n{q_data['opts_o'][1].option_text}"}
    }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload)
    assert response.status_code == 201
    assert response.json['message'] == "Official answers saved successfully"

    # Verify data
    official_answers = OfficialAnswer.query.filter_by(race_id=sample_race.id).all()
    assert len(official_answers) == 4 # One for each question in payload

    oa_text = OfficialAnswer.query.filter_by(question_id=q_data["q_text"].id).first()
    assert oa_text.answer_text == "Test Winner"

    oa_mc_single = OfficialAnswer.query.filter_by(question_id=q_data["q_mc_single"].id).first()
    assert oa_mc_single.selected_option_id == q_data["opts_s"][0].id

    oa_mc_multi = OfficialAnswer.query.filter_by(question_id=q_data["q_mc_multi"].id).first()
    assert len(oa_mc_multi.official_selected_mc_options) == 2
    selected_ids = sorted([item.question_option_id for item in oa_mc_multi.official_selected_mc_options])
    assert selected_ids == sorted([q_data["opts_m"][0].id, q_data["opts_m"][1].id])

    oa_ordering = OfficialAnswer.query.filter_by(question_id=q_data["q_ordering"].id).first()
    assert oa_ordering.answer_text == f"{q_data['opts_o'][0].option_text}\n{q_data['opts_o'][1].option_text}"


def test_post_official_answers_league_admin(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("LEAGUE_ADMIN")
    q_data = setup_questions_for_race(db_session, sample_race.id)
    payload = { str(q_data["q_text"].id): {"answer_text": "League Admin Answer"} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload)
    assert response.status_code == 201

def test_post_official_answers_player_forbidden(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("PLAYER")
    q_data = setup_questions_for_race(db_session, sample_race.id)
    payload = { str(q_data["q_text"].id): {"answer_text": "Player Answer"} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload)
    assert response.status_code == 403

def test_post_official_answers_unauthenticated(client, sample_race, db_session):
    q_data = setup_questions_for_race(db_session, sample_race.id)
    payload = { str(q_data["q_text"].id): {"answer_text": "Anon Answer"} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload)
    assert response.status_code == 401

def test_post_official_answers_replace_existing(authenticated_client, sample_race, db_session):
    client, admin = authenticated_client("ADMIN") # Using admin for setup and test
    q_data = setup_questions_for_race(db_session, sample_race.id)

    # Initial answers
    initial_payload = { str(q_data["q_text"].id): {"answer_text": "Initial"} }
    client.post(f'/api/races/{sample_race.id}/official_answers', json=initial_payload)

    oa_initial = OfficialAnswer.query.filter_by(race_id=sample_race.id, question_id=q_data["q_text"].id).first()
    assert oa_initial.answer_text == "Initial"
    initial_oa_id = oa_initial.id

    # New answers - should replace
    new_payload = { str(q_data["q_text"].id): {"answer_text": "Updated"} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=new_payload)
    assert response.status_code == 201

    # Verify old one is gone (or updated, depending on implementation - current is delete then create)
    # Based on current POST logic (delete all then create new):
    assert OfficialAnswer.query.get(initial_oa_id) is None

    oa_updated = OfficialAnswer.query.filter_by(race_id=sample_race.id, question_id=q_data["q_text"].id).first()
    assert oa_updated is not None
    assert oa_updated.answer_text == "Updated"
    assert len(OfficialAnswer.query.filter_by(race_id=sample_race.id).all()) == 1


def test_post_official_answers_invalid_payload(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("ADMIN")
    q_data = setup_questions_for_race(db_session, sample_race.id)

    # Invalid question ID string
    payload_invalid_q_id_str = { "not_an_int": {"answer_text": "bad qid"} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload_invalid_q_id_str)
    # The loop just continues on invalid int conversion, so it might be a 201 if other parts are empty or valid
    # Depending on strictness, this might be okay or a 400. Current API code skips.
    # For a more robust test, ensure it doesn't create anything or returns specific error.
    # For now, let's check it doesn't create an answer for "not_an_int"
    assert OfficialAnswer.query.filter_by(answer_text="bad qid").first() is None

    # Invalid option ID for MC single
    payload_invalid_opt_id = { str(q_data["q_mc_single"].id): {"selected_option_id": 99999} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload_invalid_opt_id)
    assert response.status_code == 201 # API logs warning but continues
    oa_mc_single = OfficialAnswer.query.filter_by(question_id=q_data["q_mc_single"].id).first()
    assert oa_mc_single is not None
    assert oa_mc_single.selected_option_id is None # Should be set to None due to invalid option

    # Question ID not belonging to the race
    other_race = Race(title="Other Race", race_format_id=sample_race.race_format_id, event_date=sample_race.event_date, user_id=sample_race.user_id, gender_category="M")
    db_session.add(other_race)
    db_session.commit()
    other_question = Question(race_id=other_race.id, question_type_id=q_data["q_text"].question_type_id, text="Belongs to other race")
    db_session.add(other_question)
    db_session.commit()

    payload_mismatched_q = { str(other_question.id): {"answer_text": "Mismatched"} }
    response = client.post(f'/api/races/{sample_race.id}/official_answers', json=payload_mismatched_q)
    assert response.status_code == 201 # API logs warning and skips this question
    assert OfficialAnswer.query.filter_by(answer_text="Mismatched").first() is None


def test_post_official_answers_non_existent_race(authenticated_client):
    client, _ = authenticated_client("ADMIN")
    payload = { "1": {"answer_text": "For non-existent race"} }
    response = client.post('/api/races/9999/official_answers', json=payload)
    assert response.status_code == 404

def test_get_official_answers_structure(authenticated_client, sample_race, db_session):
    client, _ = authenticated_client("ADMIN")
    q_data = setup_questions_for_race(db_session, sample_race.id)

    # Create diverse official answers
    oa_text = OfficialAnswer(race_id=sample_race.id, question_id=q_data["q_text"].id, answer_text="Text Answer")
    oa_mc_s = OfficialAnswer(race_id=sample_race.id, question_id=q_data["q_mc_single"].id, selected_option_id=q_data["opts_s"][0].id)
    oa_mc_m = OfficialAnswer(race_id=sample_race.id, question_id=q_data["q_mc_multi"].id)
    db_session.add_all([oa_text, oa_mc_s, oa_mc_m])
    db_session.commit()

    oamco1 = OfficialAnswerMultipleChoiceOption(official_answer_id=oa_mc_m.id, question_option_id=q_data["opts_m"][0].id)
    oamco2 = OfficialAnswerMultipleChoiceOption(official_answer_id=oa_mc_m.id, question_option_id=q_data["opts_m"][1].id)
    db_session.add_all([oamco1, oamco2])

    oa_ord = OfficialAnswer(race_id=sample_race.id, question_id=q_data["q_ordering"].id, answer_text="Runner P\nRunner Q")
    db_session.add(oa_ord)
    db_session.commit()

    response = client.get(f'/api/races/{sample_race.id}/official_answers')
    assert response.status_code == 200
    data = response.json
    assert len(data) == 4

    for answer_detail in data:
        assert "question_id" in answer_detail
        assert "question_text" in answer_detail
        assert "question_type" in answer_detail
        assert "answer_text" in answer_detail
        assert "selected_option_id" in answer_detail
        assert "selected_option_text" in answer_detail
        assert "selected_mc_options" in answer_detail
        assert "all_question_options" in answer_detail
        assert isinstance(answer_detail["all_question_options"], list)

        if answer_detail["question_id"] == q_data["q_text"].id:
            assert answer_detail["answer_text"] == "Text Answer"
        elif answer_detail["question_id"] == q_data["q_mc_single"].id:
            assert answer_detail["selected_option_id"] == q_data["opts_s"][0].id
            assert answer_detail["selected_option_text"] == q_data["opts_s"][0].option_text
        elif answer_detail["question_id"] == q_data["q_mc_multi"].id:
            assert len(answer_detail["selected_mc_options"]) == 2
            texts = sorted([item["option_text"] for item in answer_detail["selected_mc_options"]])
            assert texts == sorted([q_data["opts_m"][0].option_text, q_data["opts_m"][1].option_text])
        elif answer_detail["question_id"] == q_data["q_ordering"].id:
             assert answer_detail["answer_text"] == "Runner P\nRunner Q"
             assert len(answer_detail["all_question_options"]) == 2
             assert answer_detail["all_question_options"][0]["option_text"] == "Runner P"
             assert answer_detail["all_question_options"][0]["correct_order_index"] == 0
