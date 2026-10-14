"""Unit tests for quiz generation, verifier agreement, and answer submission."""
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.quiz import QuestionBank, Attempt
from app.models.mastery import TopicMastery
from app.services.quiz.schemas import GeneratedMCQ, VerifierEvaluation
from app.services.quiz.service import quiz_service


@pytest.fixture
async def quiz_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_and_verify_question_success(quiz_db):
    """When verifier agrees with generator, question is saved to question_bank."""
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    async with quiz_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        topic = SyllabusNode(id=topic_id, student_id=student_id, node_type="topic", title="Thermodynamics")
        session.add_all([student, topic])
        await session.commit()

    mock_mcq = GeneratedMCQ(
        question="What is the unit of entropy in SI?",
        options={"A": "Joule/Kelvin", "B": "Newton/meter", "C": "Watt/second"},
        correct_answer="A",
        explanation="Entropy in SI units is measured in Joules per Kelvin (J/K).",
        difficulty="medium",
    )
    mock_verifier = VerifierEvaluation(
        solved_answer="A",
        confidence=1.0,
        reasoning="Entropy S = dQ/T has units Joules divided by Kelvin.",
    )

    async with quiz_db() as session:
        with patch("app.services.quiz.service.llm_client.extract_structured", side_effect=[mock_mcq, mock_verifier]):
            question = await quiz_service.generate_and_verify_question(topic_id=topic_id, session=session)

    assert question is not None
    assert question.correct_answer == "A"
    assert question.verifier_score == 1.0


@pytest.mark.asyncio
async def test_generate_and_verify_question_mismatch_discarded(quiz_db):
    """When verifier disagrees with generator, question is rejected and not saved."""
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    async with quiz_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        topic = SyllabusNode(id=topic_id, student_id=student_id, node_type="topic", title="Optics")
        session.add_all([student, topic])
        await session.commit()

    mock_mcq = GeneratedMCQ(
        question="Which mirror is used as a rear-view mirror?",
        options={"A": "Concave", "B": "Convex", "C": "Plane"},
        correct_answer="A",  # Deliberate wrong answer key in generator
        explanation="Test explanation",
        difficulty="easy",
    )
    mock_verifier = VerifierEvaluation(
        solved_answer="B",  # Verifier correctly spots Convex!
        confidence=0.95,
        reasoning="Convex mirrors produce virtual, erect and diminished images giving a wider field of view.",
    )

    async with quiz_db() as session:
        with patch("app.services.quiz.service.llm_client.extract_structured", side_effect=[mock_mcq, mock_verifier]):
            question = await quiz_service.generate_and_verify_question(topic_id=topic_id, session=session)

    # Discarded due to mismatch!
    assert question is None


@pytest.mark.asyncio
async def test_submit_answer_updates_mastery(quiz_db):
    """Submitting an answer logs the attempt and updates FSRS TopicMastery."""
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    question_id = uuid.uuid4()

    async with quiz_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        topic = SyllabusNode(id=topic_id, student_id=student_id, node_type="topic", title="Vectors")
        q = QuestionBank(
            id=question_id,
            topic_id=topic_id,
            question_text="What is the magnitude of a unit vector?",
            options={"A": "0", "B": "1", "C": "Infinity"},
            correct_answer="B",
            explanation="A unit vector by definition has a magnitude of exactly 1.",
        )
        session.add_all([student, topic, q])
        await session.commit()

    async with quiz_db() as session:
        feedback, buttons = await quiz_service.submit_answer(
            student_id=student_id,
            question_id=question_id,
            selected_option="B",
            session=session,
        )

    assert "Correct! Excellent job!" in feedback
    assert "Topic Mastery" in feedback
    assert any(b.id == "quiz_next_question" for b in buttons)


def test_format_question_for_whatsapp_buttons_length():
    q = QuestionBank(
        id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        question_text="What is Ohm's Law?",
        options={
            "A": "V = IR where V is voltage",
            "B": "P = VI for electrical power",
            "C": "F = ma for force acceleration",
        },
        correct_answer="A",
        explanation="V = IR expresses the relationship between voltage, current, and resistance.",
    )

    body, buttons = quiz_service.format_question_for_whatsapp(q, "Current Electricity")
    assert "Quiz: Current Electricity" in body
    assert len(buttons) == 3
    # WhatsApp reply button titles must strictly be <= 20 characters
    for btn in buttons:
        assert len(btn.title) <= 20
        assert btn.id.startswith(f"quiz_ans_{q.id}_")
