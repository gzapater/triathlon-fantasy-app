import pytest
from backend.models import Question, UserAnswer, OfficialAnswer, QuestionType
from backend.app import _calculate_score_for_answer # Assuming this is importable or adjust path

# Mock objects to simulate SQLAlchemy models for testing scoring function directly
class MockQuestion:
    def __init__(self, id, question_type_name, slider_points_exact=0, slider_threshold_partial=None, slider_points_partial=0):
        self.id = id
        self.question_type = MockQuestionType(question_type_name)
        self.slider_points_exact = slider_points_exact
        self.slider_threshold_partial = slider_threshold_partial
        self.slider_points_partial = slider_points_partial
        # Add other question type specific fields if _calculate_score_for_answer uses them directly

class MockQuestionType:
    def __init__(self, name):
        self.name = name

class MockUserAnswer:
    def __init__(self, question_id, slider_answer_value=None, answer_text=None, selected_option_id=None, selected_mc_options=None):
        self.id = 1 # Dummy ID
        self.question_id = question_id
        self.slider_answer_value = slider_answer_value
        self.answer_text = answer_text
        self.selected_option_id = selected_option_id
        self.selected_mc_options = selected_mc_options if selected_mc_options else []

class MockOfficialAnswer:
    def __init__(self, question_id, correct_slider_value=None, answer_text=None, selected_option_id=None, official_selected_mc_options=None):
        self.question_id = question_id
        self.correct_slider_value = correct_slider_value
        self.answer_text = answer_text
        self.selected_option_id = selected_option_id
        self.official_selected_mc_options = official_selected_mc_options if official_selected_mc_options else []

@pytest.fixture
def slider_question_scoring():
    return MockQuestion(
        id=1,
        question_type_name='SLIDER',
        slider_points_exact=100,
        slider_threshold_partial=5.0,
        slider_points_partial=50
    )

def test_slider_exact_match(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 100
    assert is_correct == True

def test_slider_partial_match_upper_bound(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=80.0) # 75 + 5
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_partial_match_lower_bound(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=70.0) # 75 - 5
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_partial_match_within_threshold(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0) # 75 + 2 (within threshold of 5)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_no_match_above_partial(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=80.1) # 75 + 5.1 (just outside threshold)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_no_match_below_partial(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=69.9) # 75 - 5.1 (just outside threshold)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_no_user_answer(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=None)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_no_official_answer(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=None)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_both_answers_none(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=None)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=None)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_partial_scoring_disabled_threshold_none(slider_question_scoring):
    q_no_partial_threshold = MockQuestion(
        id=1, question_type_name='SLIDER', slider_points_exact=100,
        slider_threshold_partial=None, # Partial scoring disabled via threshold
        slider_points_partial=50
    )
    # Partial match range, but should not score partial
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, q_no_partial_threshold)
    assert points == 0
    assert is_correct == False

    # Exact match should still score
    user_ans_exact = MockUserAnswer(question_id=1, slider_answer_value=75.0)
    points_exact, is_correct_exact = _calculate_score_for_answer(user_ans_exact, official_ans, q_no_partial_threshold)
    assert points_exact == 100
    assert is_correct_exact == True

def test_slider_partial_scoring_disabled_points_none(slider_question_scoring):
    q_no_partial_points = MockQuestion(
        id=1, question_type_name='SLIDER', slider_points_exact=100,
        slider_threshold_partial=5.0,
        slider_points_partial=None # Partial scoring disabled via points
    )
    # Partial match range, but should not score partial
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    # The scoring logic currently checks `points_partial >=0`. If None, this might error or behave unexpectedly.
    # Let's assume None for points means partial scoring is off for that rule.
    # _calculate_score_for_answer should handle points_partial being None gracefully.
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, q_no_partial_points)
    assert points == 0
    assert is_correct == False

def test_slider_partial_scoring_disabled_points_zero(slider_question_scoring):
    # Scenario: Partial threshold exists, but partial points are zero.
    q_zero_partial_points = MockQuestion(
        id=1, question_type_name='SLIDER', slider_points_exact=100,
        slider_threshold_partial=5.0,
        slider_points_partial=0
    )
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0) # Within partial threshold
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, q_zero_partial_points)
    assert points == 0
    # is_correct is True if points_partial > 0. Since points_partial is 0, is_correct should be False.
    assert is_correct == False


def test_slider_float_values_exact_match(slider_question_scoring):
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.123)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.123)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 100
    assert is_correct == True

def test_slider_float_values_partial_match(slider_question_scoring):
    # slider_threshold_partial=5.0
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=78.123) # 75.123 + 3.0
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.123)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_exact_match_near_epsilon(slider_question_scoring):
    epsilon = 1e-9
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 + epsilon / 2)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 100 # Should be exact
    assert is_correct == True

def test_slider_partial_match_near_epsilon_upper(slider_question_scoring):
    epsilon = 1e-9
    # User value is official + threshold + epsilon/2 (so it's just within partial range due to epsilon in comparison)
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 + slider_question_scoring.slider_threshold_partial + epsilon/2)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_partial_match_near_epsilon_lower(slider_question_scoring):
    epsilon = 1e-9
    # User value is official - threshold - epsilon/2
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 - slider_question_scoring.slider_threshold_partial - epsilon/2)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_no_match_just_outside_epsilon_partial_upper(slider_question_scoring):
    epsilon = 1e-9
    # User value is official + threshold + epsilon * 1.5 (just outside partial due to epsilon in comparison)
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 + slider_question_scoring.slider_threshold_partial + epsilon * 1.5)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False
