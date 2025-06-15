import pytest
from backend.models import db, Race, Question, QuestionType, QuestionOption, OfficialAnswer, OfficialAnswerMultipleChoiceOption
from sqlalchemy.exc import IntegrityError

# Helper function to create a question with options
def create_question_with_options(db_session, race, question_type_name, text, options_texts=None, is_mc_multiple_correct=False):
    question_type = QuestionType.query.filter_by(name=question_type_name).first()
    if not question_type:
        question_type = QuestionType(name=question_type_name)
        db_session.add(question_type)
        db_session.commit()

    question = Question(
        race_id=race.id,
        question_type_id=question_type.id,
        text=text,
        is_mc_multiple_correct=is_mc_multiple_correct
    )
    db_session.add(question)
    db_session.commit()

    created_options = []
    if options_texts:
        for i, option_text in enumerate(options_texts):
            q_option = QuestionOption(
                question_id=question.id,
                option_text=option_text,
                correct_order_index=i if question_type_name == 'ORDERING' else None
            )
            db_session.add(q_option)
            created_options.append(q_option)
        db_session.commit()
    return question, created_options

def test_create_official_answer_free_text(db_session, sample_race):
    question, _ = create_question_with_options(db_session, sample_race, "FREE_TEXT", "Who will win?")

    official_answer = OfficialAnswer(
        race_id=sample_race.id,
        question_id=question.id,
        answer_text="John Doe"
    )
    db_session.add(official_answer)
    db_session.commit()

    assert official_answer.id is not None
    assert official_answer.race_id == sample_race.id
    assert official_answer.question_id == question.id
    assert official_answer.answer_text == "John Doe"
    assert official_answer.question.text == "Who will win?"
    assert official_answer.race.title == sample_race.title

def test_create_official_answer_mc_single(db_session, sample_race):
    question, options = create_question_with_options(db_session, sample_race, "MULTIPLE_CHOICE", "Best brand?", ["Brand A", "Brand B"])

    official_answer = OfficialAnswer(
        race_id=sample_race.id,
        question_id=question.id,
        selected_option_id=options[0].id
    )
    db_session.add(official_answer)
    db_session.commit()

    assert official_answer.id is not None
    assert official_answer.selected_option_id == options[0].id
    assert official_answer.selected_option.option_text == "Brand A"

def test_create_official_answer_mc_multiple(db_session, sample_race):
    question, options = create_question_with_options(db_session, sample_race, "MULTIPLE_CHOICE", "Select two colors", ["Red", "Green", "Blue"], is_mc_multiple_correct=True)

    official_answer = OfficialAnswer(
        race_id=sample_race.id,
        question_id=question.id
    )
    db_session.add(official_answer)
    db_session.commit() # Commit to get official_answer.id

    oa_mc_opt1 = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=options[0].id)
    oa_mc_opt2 = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=options[1].id)
    db_session.add_all([oa_mc_opt1, oa_mc_opt2])
    db_session.commit()

    assert official_answer.id is not None
    assert len(official_answer.official_selected_mc_options) == 2
    selected_option_texts = sorted([item.question_option.option_text for item in official_answer.official_selected_mc_options])
    assert selected_option_texts == ["Green", "Red"] # Order might vary depending on retrieval, so sort

def test_create_official_answer_ordering(db_session, sample_race):
    question, _ = create_question_with_options(db_session, sample_race, "ORDERING", "Order the steps", ["Step 1", "Step 2", "Step 3"])

    official_answer = OfficialAnswer(
        race_id=sample_race.id,
        question_id=question.id,
        answer_text="Step 1\nStep 2\nStep 3"
    )
    db_session.add(official_answer)
    db_session.commit()

    assert official_answer.id is not None
    assert official_answer.answer_text == "Step 1\nStep 2\nStep 3"

def test_official_answer_unique_constraint(db_session, sample_race):
    question, _ = create_question_with_options(db_session, sample_race, "FREE_TEXT", "Unique Question")

    oa1 = OfficialAnswer(race_id=sample_race.id, question_id=question.id, answer_text="Answer 1")
    db_session.add(oa1)
    db_session.commit()

    oa2 = OfficialAnswer(race_id=sample_race.id, question_id=question.id, answer_text="Answer 2")
    db_session.add(oa2)
    with pytest.raises(IntegrityError):
        db_session.commit() # Should fail due to ('_race_question_uc', 'race_id', 'question_id')

def test_official_answer_mc_option_unique_constraint(db_session, sample_race):
    question, options = create_question_with_options(db_session, sample_race, "MULTIPLE_CHOICE", "MC Unique Options", ["Opt X", "Opt Y"], is_mc_multiple_correct=True)
    official_answer = OfficialAnswer(race_id=sample_race.id, question_id=question.id)
    db_session.add(official_answer)
    db_session.commit()

    mc_opt1 = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=options[0].id)
    db_session.add(mc_opt1)
    db_session.commit()

    mc_opt2 = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=options[0].id) # Duplicate
    db_session.add(mc_opt2)
    with pytest.raises(IntegrityError):
        db_session.commit() # Should fail due to ('_official_answer_option_uc', 'official_answer_id', 'question_option_id')

def test_cascade_delete_official_answer(db_session, sample_race):
    question, options = create_question_with_options(db_session, sample_race, "MULTIPLE_CHOICE", "Cascade Test", ["C1", "C2"], is_mc_multiple_correct=True)
    official_answer = OfficialAnswer(race_id=sample_race.id, question_id=question.id)
    db_session.add(official_answer)
    db_session.commit()

    oa_mc_opt = OfficialAnswerMultipleChoiceOption(official_answer_id=official_answer.id, question_option_id=options[0].id)
    db_session.add(oa_mc_opt)
    db_session.commit()

    mc_option_id = oa_mc_opt.id
    assert OfficialAnswerMultipleChoiceOption.query.get(mc_option_id) is not None

    db_session.delete(official_answer)
    db_session.commit()

    assert OfficialAnswer.query.get(official_answer.id) is None
    assert OfficialAnswerMultipleChoiceOption.query.get(mc_option_id) is None # Should be cascade deleted
