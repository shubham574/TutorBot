"""Integration tests for interactive WhatsApp quiz flow."""
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.quiz import QuestionBank, Attempt
from app.models.mastery import TopicMastery
from app.workers.tasks import process_whatsapp_message


@pytest.fixture
async def quiz_flow_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    with patch("app.workers.tasks.async_session_factory", session_factory):
        yield session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_full_interactive_quiz_flow(quiz_flow_db):
    """
    End-to-End Quiz Flow:
    1. Student triggers /quiz.
    2. Bot generates verified MCQ and delivers interactive buttons [A, B, C].
    3. Student taps option B button.
    4. Bot grades response, updates FSRS TopicMastery, and sends feedback.
    """
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    question_id = uuid.uuid4()

    # Pre-populate student and syllabus topic
    async with quiz_flow_db() as session:
        student = Student(id=student_id, phone_number="919876543210", name="Bob")
        topic = SyllabusNode(id=topic_id, student_id=student_id, node_type="topic", title="Kinematics")
        q = QuestionBank(
            id=question_id,
            topic_id=topic_id,
            question_text="What is the acceleration due to gravity on Earth near the surface?",
            options={"A": "4.9 m/s²", "B": "9.8 m/s²", "C": "19.6 m/s²"},
            correct_answer="B",
            explanation="The standard acceleration of gravity g on Earth is approximately 9.8 m/s².",
        )
        session.add_all([student, topic, q])
        await session.commit()

    # 1. Student requests quiz with /quiz
    quiz_request_msg = {
        "wamid": "wamid.QUIZ_REQ_001",
        "sender_phone": "919876543210",
        "sender_name": "Bob",
        "message_type": "text",
        "text_content": "/quiz",
        "raw_payload": {},
    }

    with patch("app.services.quiz.service.quiz_service.generate_and_verify_question", new=AsyncMock(return_value=q)):
        res1 = await process_whatsapp_message(ctx={}, message_data=quiz_request_msg)
        assert res1["status"] == "success"

    # 2. Student taps button for option B (correct)
    ans_button_msg = {
        "wamid": "wamid.QUIZ_ANS_002",
        "sender_phone": "919876543210",
        "sender_name": "Bob",
        "message_type": "interactive",
        "interactive_button_id": f"quiz_ans_{question_id}_B",
        "text_content": "B: 9.8 m/s²",
        "raw_payload": {},
    }

    res2 = await process_whatsapp_message(ctx={}, message_data=ans_button_msg)
    assert res2["status"] == "success"

    # 3. Verify attempt logged in database
    async with quiz_flow_db() as session:
        attempt_res = await session.execute(select(Attempt).where(Attempt.student_id == student_id))
        attempt = attempt_res.scalar_one_or_none()
        assert attempt is not None
        assert attempt.student_response == "B"
        assert attempt.is_correct is True

        # Verify FSRS mastery updated
        mastery_res = await session.execute(select(TopicMastery).where(TopicMastery.student_id == student_id))
        mastery = mastery_res.scalar_one_or_none()
        assert mastery is not None
        assert mastery.reps == 1
        assert mastery.lapses == 0
        assert mastery.stability > 1.0
