import pytest
from backend.models import Question, UserAnswer, OfficialAnswer, QuestionType, QuestionOption, UserScore

# DO NOT import _calculate_score_for_answer or calculate_and_store_scores from backend.app at the top level.
# Import them inside test functions or fixtures that need them, after app context is set.

# Mock objects to simulate SQLAlchemy models for testing scoring function directly
class MockQuestion:
    def __init__(self, id, question_type_name, slider_points_exact=0, slider_threshold_partial=None, slider_points_partial=0):
        self.id = id
        self.question_type = MockQuestionType(question_type_name)
        self.slider_points_exact = slider_points_exact
        self.slider_threshold_partial = slider_threshold_partial
        self.slider_points_partial = slider_points_partial

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
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 100
    assert is_correct == True

def test_slider_partial_match_upper_bound(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=80.0) # 75 + 5
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_partial_match_lower_bound(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=70.0) # 75 - 5
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_partial_match_within_threshold(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0) # 75 + 2 (within threshold of 5)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_no_match_above_partial(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=80.1) # 75 + 5.1 (just outside threshold)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_no_match_below_partial(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=69.9) # 75 - 5.1 (just outside threshold)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_no_user_answer(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=None)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_no_official_answer(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=None)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_both_answers_none(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=None)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=None)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

def test_slider_partial_scoring_disabled_threshold_none(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    q_no_partial_threshold = MockQuestion(
        id=1, question_type_name='SLIDER', slider_points_exact=100,
        slider_threshold_partial=None,
        slider_points_partial=50
    )
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, q_no_partial_threshold)
    assert points == 0
    assert is_correct == False
    user_ans_exact = MockUserAnswer(question_id=1, slider_answer_value=75.0)
    points_exact, is_correct_exact = _calculate_score_for_answer(user_ans_exact, official_ans, q_no_partial_threshold)
    assert points_exact == 100
    assert is_correct_exact == True

def test_slider_partial_scoring_disabled_points_none(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    q_no_partial_points = MockQuestion(
        id=1, question_type_name='SLIDER', slider_points_exact=100,
        slider_threshold_partial=5.0,
        slider_points_partial=None
    )
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, q_no_partial_points)
    assert points == 0
    assert is_correct == False

def test_slider_partial_scoring_disabled_points_zero(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    q_zero_partial_points = MockQuestion(
        id=1, question_type_name='SLIDER', slider_points_exact=100,
        slider_threshold_partial=5.0,
        slider_points_partial=0
    )
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=77.0)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, q_zero_partial_points)
    assert points == 0
    assert is_correct == False

def test_slider_float_values_exact_match(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.123)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.123)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 100
    assert is_correct == True

def test_slider_float_values_partial_match(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=78.123)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.123)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_exact_match_near_epsilon(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    epsilon = 1e-9
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 + epsilon / 2)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 100
    assert is_correct == True

def test_slider_partial_match_near_epsilon_upper(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    epsilon = 1e-9
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 + slider_question_scoring.slider_threshold_partial + epsilon/2)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_partial_match_near_epsilon_lower(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    epsilon = 1e-9
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 - slider_question_scoring.slider_threshold_partial - epsilon/2)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 50
    assert is_correct == True

def test_slider_no_match_just_outside_epsilon_partial_upper(slider_question_scoring):
    from backend.app import _calculate_score_for_answer
    epsilon = 1e-9
    user_ans = MockUserAnswer(question_id=1, slider_answer_value=75.0 + slider_question_scoring.slider_threshold_partial + epsilon * 1.5)
    official_ans = MockOfficialAnswer(question_id=1, correct_slider_value=75.0)
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, slider_question_scoring)
    assert points == 0
    assert is_correct == False

# --- Unit Tests for _calculate_score_for_answer with ORDERING Questions (Mock-based) ---

@pytest.fixture
def ordering_question_for_calc_score_helper():
    """Provides a mock Question object for testing ordering logic in _calculate_score_for_answer."""
    return MockQuestion(
        id=101, # Different ID from slider
        question_type_name='ORDERING'
        # Specific scoring attributes will be set directly on this mock object in tests
    )

def test_calc_score_ordering_full_correct(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 10
    question.bonus_for_full_order = 5

    user_ans = MockUserAnswer(question_id=question.id, answer_text="Alpha,Beta,Gamma")
    # official_ordering_data_for_q_type is a map {question_id: [ordered_texts]}
    # Texts should be pre-lowercased as if prepared by get_participant_answers
    official_data = {question.id: ["alpha", "beta", "gamma"]}

    # official_answer_obj is not strictly used by _calculate_score_for_answer for ORDERING if official_ordering_data_for_q_type is present
    # However, the function expects it not to be None for the initial guard.
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)


    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    assert points == (3 * 10) + 5
    assert is_correct == True

def test_calc_score_ordering_partial_correct(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 10
    question.bonus_for_full_order = 5

    user_ans = MockUserAnswer(question_id=question.id, answer_text="Alpha,Gamma,Beta") # Beta and Gamma swapped
    official_data = {question.id: ["alpha", "beta", "gamma"]}
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    assert points == 10 # Only Alpha is correct
    assert is_correct == False

def test_calc_score_ordering_incorrect(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 10
    question.bonus_for_full_order = 5

    user_ans = MockUserAnswer(question_id=question.id, answer_text="Charlie,Delta,Echo")
    official_data = {question.id: ["alpha", "beta", "gamma"]}
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    assert points == 0
    assert is_correct == False

def test_calc_score_ordering_case_insensitivity(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 10
    question.bonus_for_full_order = 5

    user_ans = MockUserAnswer(question_id=question.id, answer_text="ALPHA,beta,GaMmA")
    official_data = {question.id: ["alpha", "beta", "gamma"]} # Already lowercased
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    assert points == (3*10) + 5
    assert is_correct == True

def test_calc_score_ordering_no_bonus_if_points_per_item_zero(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 0 # Points per item is zero
    question.bonus_for_full_order = 20

    user_ans = MockUserAnswer(question_id=question.id, answer_text="Alpha,Beta,Gamma")
    official_data = {question.id: ["alpha", "beta", "gamma"]}
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    # Bonus should not be awarded if points_per_correct_order is 0, even if order is perfect.
    assert points == 0
    assert is_correct == True # Still a correct match, just worth 0 points + 0 bonus based on logic

def test_calc_score_ordering_user_shorter(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 10
    question.bonus_for_full_order = 5

    user_ans = MockUserAnswer(question_id=question.id, answer_text="Alpha,Beta")
    official_data = {question.id: ["alpha", "beta", "gamma"]}
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    assert points == 20 # Alpha, Beta correct
    assert is_correct == False # Not a full match

def test_calc_score_ordering_user_longer(ordering_question_for_calc_score_helper):
    from backend.app import _calculate_score_for_answer
    question = ordering_question_for_calc_score_helper
    question.points_per_correct_order = 10
    question.bonus_for_full_order = 5

    user_ans = MockUserAnswer(question_id=question.id, answer_text="Alpha,Beta,Gamma,Delta")
    official_data = {question.id: ["alpha", "beta", "gamma"]}
    mock_official_ans_obj = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, mock_official_ans_obj, question, official_ordering_data_for_q_type=official_data)
    assert points == 30 # Alpha, Beta, Gamma correct
    assert is_correct == False # Not a full match due to length


# --- Integration Tests for calculate_and_store_scores with ORDERING Questions ---

@pytest.fixture
def ordering_question_setup(db_session, sample_race, player_user):
    """Sets up an ordering question, options, user, and race for testing."""
    ordering_type, _ = QuestionType.get_or_create(name='ORDERING') # Removed description

    question = Question(
        race_id=sample_race.id,
        question_type_id=ordering_type.id,
        text="Order these items: A, B, C",
        is_active=True,
        points_per_correct_order=10,
        bonus_for_full_order=5
    )
    db_session.add(question)
    db_session.flush()

    options_text = ["Option A", "Option B", "Option C"]
    options = []
    for i, text in enumerate(options_text):
        opt = QuestionOption(question_id=question.id, option_text=text, correct_order_index=i)
        options.append(opt)
    db_session.add_all(options)

    from backend.models import UserRaceRegistration
    registration = UserRaceRegistration(user_id=player_user.id, race_id=sample_race.id)
    db_session.add(registration)

    db_session.commit()
    return {
        "race": sample_race,
        "user": player_user,
        "question": question,
        "options": {"A": options[0], "B": options[1], "C": options[2]}
    }

def test_ordering_full_correct_order(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore

    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id,
        question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(official_ans)

    user_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    assert user_score is not None
    assert user_score.score == (3 * 10) + 5

def test_ordering_partial_correct_order(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore

    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(official_ans)

    user_ans = UserAnswer(
        user_id=user.id, race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['C'].option_text},{opts['B'].option_text}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()
    assert user_score is not None
    assert user_score.score == 10

def test_ordering_completely_incorrect_order(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore
    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(official_ans)

    user_ans = UserAnswer(
        user_id=user.id, race_id=race.id, question_id=question.id,
        answer_text=f"{opts['C'].option_text},{opts['A'].option_text},{opts['B'].option_text}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()
    assert user_score is not None
    assert user_score.score == 0


# --- Integration Tests for calculate_and_store_scores with SLIDER Questions ---

@pytest.fixture
def slider_question_integration_setup(db_session, sample_race, player_user):
    """Sets up a slider question, options, user, and race for integration testing."""
    slider_type, _ = QuestionType.get_or_create(name='SLIDER')

    question = Question(
        race_id=sample_race.id,
        question_type_id=slider_type.id,
        text="Predict the finish time in minutes.",
        is_active=True,
        slider_min_value=60.0,
        slider_max_value=120.0,
        slider_step=1.0,
        slider_points_exact=25,
        slider_threshold_partial=5.0, # e.g., if official is 90, answers between 85-95 (exclusive of 90) get partial
        slider_points_partial=10
    )
    db_session.add(question)

    from backend.models import UserRaceRegistration
    registration = UserRaceRegistration(user_id=player_user.id, race_id=sample_race.id)
    db_session.add(registration)

    db_session.commit()
    return {
        "race": sample_race,
        "user": player_user,
        "question": question
    }

def test_slider_score_aggregation_exact_match(db_session, slider_question_integration_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore

    setup = slider_question_integration_setup
    race, user, question = setup["race"], setup["user"], setup["question"]

    # Official answer: 90 minutes
    official_ans = OfficialAnswer(
        race_id=race.id,
        question_id=question.id,
        correct_slider_value=90.0
    )
    db_session.add(official_ans)

    # User answer: 90 minutes (exact match)
    user_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        slider_answer_value=90.0
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    assert user_score is not None
    assert user_score.score == 25 # Expecting exact points

def test_slider_score_aggregation_partial_match(db_session, slider_question_integration_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore

    setup = slider_question_integration_setup
    race, user, question = setup["race"], setup["user"], setup["question"]

    # Official answer: 90 minutes
    official_ans = OfficialAnswer(
        race_id=race.id,
        question_id=question.id,
        correct_slider_value=90.0
    )
    db_session.add(official_ans)

    # User answer: 93 minutes (90 + 3, which is within threshold of 5)
    user_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        slider_answer_value=93.0
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    assert user_score is not None
    assert user_score.score == 10 # Expecting partial points

def test_slider_score_aggregation_no_match(db_session, slider_question_integration_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore

    setup = slider_question_integration_setup
    race, user, question = setup["race"], setup["user"], setup["question"]

    # Official answer: 90 minutes
    official_ans = OfficialAnswer(
        race_id=race.id,
        question_id=question.id,
        correct_slider_value=90.0
    )
    db_session.add(official_ans)

    # User answer: 100 minutes (90 + 10, which is outside threshold of 5)
    user_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question.id,
        slider_answer_value=100.0
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    assert user_score is not None
    assert user_score.score == 0 # Expecting no points

def test_slider_and_other_question_score_aggregation(db_session, slider_question_integration_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore, QuestionType as DBQuestionType

    setup = slider_question_integration_setup
    race, user, slider_question = setup["race"], setup["user"], setup["question"]

    # --- Slider Question Setup (Exact Match for 25 points) ---
    official_slider_ans = OfficialAnswer(
        race_id=race.id,
        question_id=slider_question.id,
        correct_slider_value=90.0
    )
    db_session.add(official_slider_ans)
    user_slider_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=slider_question.id,
        slider_answer_value=90.0 # Exact match for 25 points
    )
    db_session.add(user_slider_ans)

    # --- Free Text Question Setup (Correct for 15 points) ---
    free_text_type, _ = DBQuestionType.get_or_create(name='FREE_TEXT')
    ft_question = Question(
        race_id=race.id,
        question_type_id=free_text_type.id,
        text="Who won?",
        is_active=True,
        max_score_free_text=15
    )
    db_session.add(ft_question)
    db_session.flush() # Get ID for ft_question

    official_ft_ans = OfficialAnswer(
        race_id=race.id,
        question_id=ft_question.id,
        answer_text="Alice"
    )
    db_session.add(official_ft_ans)
    user_ft_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=ft_question.id,
        answer_text="alice" # Correct (case-insensitive) for 15 points
    )
    db_session.add(user_ft_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    assert user_score is not None
    expected_total_score = 25 (slider) + 15 (free_text)
    assert user_score.score == expected_total_score

# --- Unit Tests for _calculate_score_for_answer with MULTIPLE_CHOICE Questions (Mock-based) ---

@pytest.fixture
def mc_question_single_correct_base():
    """Provides a base mock Question object for single-correct MC testing."""
    q = MockQuestion(id=201, question_type_name='MULTIPLE_CHOICE')
    q.is_mc_multiple_correct = False
    q.total_score_mc_single = 100 # Points for correct answer
    # points_per_incorrect_mc is not typically used for single-correct MCQs in this system's design
    return q

@pytest.fixture
def mc_question_multiple_correct_base():
    """Provides a base mock Question object for multiple-correct MC testing."""
    q = MockQuestion(id=202, question_type_name='MULTIPLE_CHOICE')
    q.is_mc_multiple_correct = True
    q.points_per_correct_mc = 50
    q.points_per_incorrect_mc = -20 # Penalty stored as negative
    return q

class MockQuestionOption:
    def __init__(self, id, text="Option"):
        self.id = id
        self.option_text = text

class MockUserAnswerMultipleChoiceOption:
    def __init__(self, question_option_id):
        self.question_option_id = question_option_id

class MockOfficialAnswerMultipleChoiceOption:
    def __init__(self, question_option_id):
        self.question_option_id = question_option_id


# --- Tests for Single-Correct Multiple Choice ---

def test_mc_single_correct_answered_correctly(mc_question_single_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_single_correct_base
    user_ans = MockUserAnswer(question_id=question.id, selected_option_id=1)
    official_ans = MockOfficialAnswer(question_id=question.id, selected_option_id=1)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question)
    assert points == 100
    assert is_correct is True

def test_mc_single_correct_answered_incorrectly(mc_question_single_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_single_correct_base
    user_ans = MockUserAnswer(question_id=question.id, selected_option_id=2) # User chose 2
    official_ans = MockOfficialAnswer(question_id=question.id, selected_option_id=1) # Correct is 1

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question)
    assert points == 0
    assert is_correct is False

def test_mc_single_correct_no_user_answer(mc_question_single_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_single_correct_base
    user_ans = MockUserAnswer(question_id=question.id, selected_option_id=None)
    official_ans = MockOfficialAnswer(question_id=question.id, selected_option_id=1)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question)
    assert points == 0
    assert is_correct is False

def test_mc_single_correct_no_official_answer(mc_question_single_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_single_correct_base
    user_ans = MockUserAnswer(question_id=question.id, selected_option_id=1)
    # OfficialAnswer has selected_option_id=None, meaning no correct answer defined by admin
    official_ans = MockOfficialAnswer(question_id=question.id, selected_option_id=None)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question)
    assert points == 0
    assert is_correct is False # Cannot be correct if official answer isn't defined

def test_mc_single_correct_score_is_zero(mc_question_single_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_single_correct_base
    question.total_score_mc_single = 0 # Question is worth 0 points
    user_ans = MockUserAnswer(question_id=question.id, selected_option_id=1)
    official_ans = MockOfficialAnswer(question_id=question.id, selected_option_id=1)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question)
    assert points == 0
    assert is_correct is True # Still a correct match, just worth 0 points

# --- Tests for Multiple-Correct Multiple Choice ---

def test_mc_multiple_all_correct_selected(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base # 50 pts per correct, 20 penalty per incorrect
    # Official correct options: 1, 2
    official_mc_options = {question.id: {1, 2}}
    # User selects: 1, 2
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=1),
        MockUserAnswerMultipleChoiceOption(question_option_id=2)
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    # official_ans object is needed but its selected_option_id isn't used for MC-multiple logic if map is provided
    official_ans = MockOfficialAnswer(question_id=question.id)


    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 100 # 50 (for #1) + 50 (for #2)
    assert is_correct is True

def test_mc_multiple_some_correct_selected(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    official_mc_options = {question.id: {1, 2}} # Correct: 1, 2
    user_selected_mc_options = [MockUserAnswerMultipleChoiceOption(question_option_id=1)] # User selects only 1
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 50 # 50 (for #1)
    assert is_correct is False # Not all correct options were selected

def test_mc_multiple_one_correct_one_incorrect_selected(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base # 50 correct, 20 penalty
    official_mc_options = {question.id: {1, 2}} # Correct: 1, 2
    # User selects 1 (correct) and 3 (incorrect)
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=1),
        MockUserAnswerMultipleChoiceOption(question_option_id=3)
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    # Assuming points_per_incorrect_mc is stored as positive 20
    # Logic: score -= penalty_value
    # Expected: 50 (for #1) - 20 (for #3) = 30
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 30
    assert is_correct is False

def test_mc_multiple_one_correct_one_incorrect_penalty_negative_storage(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    question.points_per_incorrect_mc = -20 # Penalty stored as negative
    official_mc_options = {question.id: {1, 2}}
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=1), # Correct
        MockUserAnswerMultipleChoiceOption(question_option_id=3)  # Incorrect
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    # If logic is `score += penalty` (where penalty is -20): 50 + (-20) = 30
    # If logic is `score -= penalty` (where penalty is -20): 50 - (-20) = 70 (This is the bug scenario)
    # This test will verify the fix. After the fix (score += penalty), this should be 30.
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    # We expect the bug to be present initially, so this might assert 70.
    # After the fix, this assertion should be 30.
    # For now, let's assume the fix will make it 30. If not, this test will guide the fix.
    # The user reports -5 (penalty) becomes +5. So -20 would become +20. Total 50+20=70.
    # assert points == 70 # This would be the assertion if the bug is present as described
    assert points == 30 # This is the assertion for the corrected behavior (50 + (-20))
    assert is_correct is False

def test_mc_multiple_all_incorrect_selected(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base # 50 correct, 20 penalty
    official_mc_options = {question.id: {1, 2}} # Correct: 1, 2
    # User selects 3, 4 (both incorrect)
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=3),
        MockUserAnswerMultipleChoiceOption(question_option_id=4)
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    # Expected: -20 (for #3) - 20 (for #4) = -40
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == -40
    assert is_correct is False

def test_mc_multiple_no_options_selected_by_user(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    official_mc_options = {question.id: {1, 2}}
    user_selected_mc_options = [] # User selects nothing
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 0
    assert is_correct is False # Not correct because correct options were missed

def test_mc_multiple_no_official_correct_options_defined(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    official_mc_options = {question.id: set()} # No correct options defined by admin
    user_selected_mc_options = [MockUserAnswerMultipleChoiceOption(question_option_id=1)] # User selects 1
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    # User selected 1, which is not in the empty set of official correct options. So it's incorrect.
    # Penalty is stored as negative, so score becomes points_per_incorrect_mc.
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == (question.points_per_incorrect_mc or 0) # e.g. -20
    assert is_correct is False

def test_mc_multiple_points_per_correct_is_zero(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    question.points_per_correct_mc = 0
    official_mc_options = {question.id: {1, 2}}
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=1),
        MockUserAnswerMultipleChoiceOption(question_option_id=2)
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 0
    assert is_correct is True # Match is still correct, just worth 0 points

def test_mc_multiple_penalty_is_zero(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    question.points_per_incorrect_mc = 0 # Penalty is zero
    official_mc_options = {question.id: {1}} # Correct: 1
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=1), # Correct
        MockUserAnswerMultipleChoiceOption(question_option_id=2)  # Incorrect, but 0 penalty
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    # Expected: 50 (for #1) - 0 (for #2) = 50
    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 50
    assert is_correct is False # Incorrect option was selected

def test_mc_multiple_penalty_is_none(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    question.points_per_incorrect_mc = None # Penalty is None (should default to 0 in calculation)
    official_mc_options = {question.id: {1}}
    user_selected_mc_options = [
        MockUserAnswerMultipleChoiceOption(question_option_id=1),
        MockUserAnswerMultipleChoiceOption(question_option_id=2)
    ]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == (question.points_per_correct_mc or 0) # 50 - 0 = 50
    assert is_correct is False

def test_mc_multiple_points_correct_is_none(mc_question_multiple_correct_base):
    from backend.app import _calculate_score_for_answer
    question = mc_question_multiple_correct_base
    question.points_per_correct_mc = None # Points for correct is None (should default to 0)
    official_mc_options = {question.id: {1}}
    user_selected_mc_options = [MockUserAnswerMultipleChoiceOption(question_option_id=1)]
    user_ans = MockUserAnswer(question_id=question.id, selected_mc_options=user_selected_mc_options)
    official_ans = MockOfficialAnswer(question_id=question.id)

    points, is_correct = _calculate_score_for_answer(user_ans, official_ans, question, official_mc_multiple_options_map=official_mc_options)
    assert points == 0
    assert is_correct is True # It's a correct match, even if worth 0 points.

def test_ordering_user_answer_shorter(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore
    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(official_ans)

    user_ans = UserAnswer(
        user_id=user.id, race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()
    assert user_score is not None
    assert user_score.score == 20

def test_ordering_user_answer_longer(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore
    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text}"
    )
    db_session.add(official_ans)

    user_ans = UserAnswer(
        user_id=user.id, race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()
    assert user_score is not None
    assert user_score.score == 20

def test_ordering_case_insensitivity(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore
    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text.upper()},{opts['B'].option_text.upper()},{opts['C'].option_text.upper()}"
    )
    db_session.add(official_ans)
    user_ans = UserAnswer(
        user_id=user.id, race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text.lower()},{opts['B'].option_text.lower()},{opts['C'].option_text.lower()}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()
    assert user_score is not None
    assert user_score.score == (3 * 10) + 5

def test_ordering_empty_user_answer(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore
    setup = ordering_question_setup
    race, user, question = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    official_ans = OfficialAnswer(
        race_id=race.id, question_id=question.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(official_ans)
    user_ans = UserAnswer(
        user_id=user.id, race_id=race.id, question_id=question.id,
        answer_text=""
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()
    assert user_score is not None
    assert user_score.score == 0

def test_ordering_no_bonus_if_points_per_item_is_zero(db_session, ordering_question_setup):
    from backend.app import calculate_and_store_scores
    from backend.models import OfficialAnswer, UserAnswer, UserScore, Question

    setup = ordering_question_setup
    race, user, question_orig = setup["race"], setup["user"], setup["question"]
    opts = setup["options"]

    question_orig.points_per_correct_order = 0
    question_orig.bonus_for_full_order = 20
    db_session.add(question_orig)
    db_session.commit()

    official_ans = OfficialAnswer(
        race_id=race.id,
        question_id=question_orig.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(official_ans)

    user_ans = UserAnswer(
        user_id=user.id,
        race_id=race.id,
        question_id=question_orig.id,
        answer_text=f"{opts['A'].option_text},{opts['B'].option_text},{opts['C'].option_text}"
    )
    db_session.add(user_ans)
    db_session.commit()

    calculate_and_store_scores(race.id)
    user_score = UserScore.query.filter_by(user_id=user.id, race_id=race.id).first()

    assert user_score is not None
    assert user_score.score == 0
