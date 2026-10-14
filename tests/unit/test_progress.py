"""Unit tests for ProgressReportService and progress bar rendering."""
import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.mastery import TopicMastery
from app.models.quiz import Attempt
from app.services.progress.service import progress_service, render_progress_bar


@pytest.fixture
async def progress_db():
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


def test_render_progress_bar():
    """Verifies Unicode block generation at various percentages."""
    bar_0 = render_progress_bar(0.0, total_blocks=10)
    assert bar_0 == "[░░░░░░░░░░] 0%"

    bar_50 = render_progress_bar(50.0, total_blocks=10)
    assert bar_50 == "[█████░░░░░] 50%"

    bar_100 = render_progress_bar(100.0, total_blocks=10)
    assert bar_100 == "[██████████] 100%"

    # Clamping behavior
    assert render_progress_bar(-10.0, total_blocks=10) == "[░░░░░░░░░░] -10%"
    assert render_progress_bar(120.0, total_blocks=10) == "[██████████] 120%"


@pytest.mark.asyncio
async def test_generate_progress_report_empty(progress_db):
    """When a student has not uploaded syllabus or taken any quizzes."""
    student_id = uuid.uuid4()

    async with progress_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        session.add(student)
        await session.commit()

        body, buttons = await progress_service.generate_progress_report(student_id, session)
        assert "Student Academic Progress Dashboard" in body
        assert "Total Topics in Syllabus:* 0" in body
        assert "Questions Answered: 0" in body
        assert len(buttons) == 2


@pytest.mark.asyncio
async def test_generate_progress_report_with_data(progress_db):
    """When a student has syllabus topics, topic mastery, and quiz attempts."""
    student_id = uuid.uuid4()
    t1_id = uuid.uuid4()
    t2_id = uuid.uuid4()

    async with progress_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        t1 = SyllabusNode(id=t1_id, student_id=student_id, node_type="topic", title="Topic 1")
        t2 = SyllabusNode(id=t2_id, student_id=student_id, node_type="topic", title="Topic 2")
        session.add_all([student, t1, t2])

        # Mastery: Topic 1 mastered (0.85), Topic 2 learning (0.45)
        m1 = TopicMastery(student_id=student_id, topic_id=t1_id, mastery_score=0.85)
        m2 = TopicMastery(student_id=student_id, topic_id=t2_id, mastery_score=0.45)
        session.add_all([m1, m2])

        # Quiz attempts: 3 attempts, 2 correct, 1 incorrect
        att1 = Attempt(student_id=student_id, question_id=uuid.uuid4(), student_response="A", is_correct=True)
        att2 = Attempt(student_id=student_id, question_id=uuid.uuid4(), student_response="B", is_correct=True)
        att3 = Attempt(student_id=student_id, question_id=uuid.uuid4(), student_response="C", is_correct=False)
        session.add_all([att1, att2, att3])

        await session.commit()

        body, buttons = await progress_service.generate_progress_report(student_id, session)
        assert "Total Topics in Syllabus:* 2" in body
        assert "Mastered Topics:* 1" in body
        assert "Topics in Learning:* 1" in body
        assert "Questions Answered: 3" in body
        assert "Overall Accuracy: 66% (2/3 correct)" in body
        assert len(buttons) == 2
