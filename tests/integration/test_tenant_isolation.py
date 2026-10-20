"""Integration tests for tenant (student) isolation."""
import pytest
import uuid
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.content import ContentChunk
from app.models.mastery import TopicMastery
from app.models.quiz import Attempt
from app.rag.retriever import retriever, AnswerMode
from app.repositories import StudentScopedRepository


@pytest.fixture
async def test_db_session():
    """Sets up an in-memory SQLite database for tenant isolation testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    with patch("app.workers.tasks.async_session_factory", session_factory):
        yield session_factory

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_retriever_enforces_student_isolation(test_db_session):
    """Tests that the hybrid retriever never returns Student A's private chunks to Student B."""
    async with test_db_session() as session:
        # Create two students
        student_a = Student(phone_number="919876543210", name="Student A")
        student_b = Student(phone_number="919876543211", name="Student B")
        session.add_all([student_a, student_b])
        await session.flush()

        # Create private content chunk for Student A
        chunk_a = ContentChunk(
            student_id=student_a.id,
            subject="Physics",
            source_doc_id="doc_a_001",
            source_title="Student A Notes",
            page_number=1,
            doc_type="notes",
            difficulty="medium",
            content="Kinematics is the study of motion without considering forces.",
        )
        # Create private content chunk for Student B
        chunk_b = ContentChunk(
            student_id=student_b.id,
            subject="Physics",
            source_doc_id="doc_b_001",
            source_title="Student B Notes",
            page_number=1,
            doc_type="notes",
            difficulty="medium",
            content="Thermodynamics deals with heat and temperature.",
        )
        # Create shared global corpus chunk (student_id = NULL)
        chunk_shared = ContentChunk(
            student_id=None,
            subject="Physics",
            source_doc_id="ncert_physics",
            source_title="NCERT Physics Class 11",
            page_number=42,
            doc_type="textbook",
            difficulty="medium",
            content="Newton's First Law states that an object remains at rest unless acted upon by a force.",
        )
        session.add_all([chunk_a, chunk_b, chunk_shared])
        await session.commit()

        # Query as Student A - should see A's private + shared, NOT B's private
        result_a = await retriever.retrieve(
            query="kinematics motion",
            student_id=student_a.id,
            session=session,
            top_k=10,
        )

        # Query as Student B - should see B's private + shared, NOT A's private
        result_b = await retriever.retrieve(
            query="thermodynamics heat",
            student_id=student_b.id,
            session=session,
            top_k=10,
        )

        # Query with no student_id (unauthenticated) - should only see shared
        result_none = await retriever.retrieve(
            query="newton first law",
            student_id=None,
            session=session,
            top_k=10,
        )

        # Verify Student A's results
        chunk_ids_a = {c.chunk_id for c in result_a.chunks}
        assert chunk_a.id in chunk_ids_a, "Student A should see their own private chunk"
        assert chunk_shared.id in chunk_ids_a, "Student A should see shared corpus"
        assert chunk_b.id not in chunk_ids_a, "Student A must NOT see Student B's private chunk"

        # Verify Student B's results
        chunk_ids_b = {c.chunk_id for c in result_b.chunks}
        assert chunk_b.id in chunk_ids_b, "Student B should see their own private chunk"
        assert chunk_shared.id in chunk_ids_b, "Student B should see shared corpus"
        assert chunk_a.id not in chunk_ids_b, "Student B must NOT see Student A's private chunk"

        # Verify unauthenticated results (student_id=None)
        chunk_ids_none = {c.chunk_id for c in result_none.chunks}
        assert chunk_shared.id in chunk_ids_none, "Unauthenticated should see shared corpus"
        assert chunk_a.id not in chunk_ids_none, "Unauthenticated must NOT see Student A's private chunk"
        assert chunk_b.id not in chunk_ids_none, "Unauthenticated must NOT see Student B's private chunk"


@pytest.mark.asyncio
async def test_repository_enforces_student_scoping(test_db_session):
    """Tests that the StudentScopedRepository enforces student_id on all operations."""
    async with test_db_session() as session:
        # Create two students
        student_a = Student(phone_number="919876543210", name="Student A")
        student_b = Student(phone_number="919876543211", name="Student B")
        session.add_all([student_a, student_b])
        await session.flush()

        # Create content chunks for both students
        chunk_a = ContentChunk(
            student_id=student_a.id,
            subject="Physics",
            source_doc_id="doc_a",
            source_title="Doc A",
            page_number=1,
            doc_type="notes",
            difficulty="medium",
            content="Student A content",
        )
        chunk_b = ContentChunk(
            student_id=student_b.id,
            subject="Physics",
            source_doc_id="doc_b",
            source_title="Doc B",
            page_number=1,
            doc_type="notes",
            difficulty="medium",
            content="Student B content",
        )
        session.add_all([chunk_a, chunk_b])
        await session.commit()

        # Create repositories
        repo_a = StudentScopedRepository(ContentChunk, session)
        repo_b = StudentScopedRepository(ContentChunk, session)

        # Test get_all - Student A should only see their chunks
        chunks_a = await repo_a.get_all(student_id=student_a.id)
        assert len(chunks_a) == 1
        assert chunks_a[0].id == chunk_a.id

        # Test get_all - Student B should only see their chunks
        chunks_b = await repo_b.get_all(student_id=student_b.id)
        assert len(chunks_b) == 1
        assert chunks_b[0].id == chunk_b.id

        # Test get_by_id - Student A can get their chunk
        retrieved = await repo_a.get_by_id(chunk_a.id, student_a.id)
        assert retrieved is not None
        assert retrieved.id == chunk_a.id

        # Test get_by_id - Student A cannot get Student B's chunk
        retrieved = await repo_a.get_by_id(chunk_b.id, student_a.id)
        assert retrieved is None

        # Test count
        count_a = await repo_a.count(student_a.id)
        assert count_a == 1
        count_b = await repo_b.count(student_b.id)
        assert count_b == 1

        # Test exists
        exists_a = await repo_a.exists(chunk_a.id, student_a.id)
        assert exists_a is True
        exists_b = await repo_a.exists(chunk_b.id, student_a.id)
        assert exists_b is False

        # Test delete_all scoped to student
        deleted = await repo_a.delete_all(student_a.id)
        assert deleted == 1

        # Verify Student B's data is untouched
        remaining_b = await repo_b.get_all(student_id=student_b.id)
        assert len(remaining_b) == 1
        assert remaining_b[0].id == chunk_b.id


@pytest.mark.asyncio
async def test_mastery_isolation(test_db_session):
    """Tests that TopicMastery records are isolated per student."""
    async with test_db_session() as session:
        student_a = Student(phone_number="919876543210", name="Student A")
        student_b = Student(phone_number="919876543211", name="Student B")
        session.add_all([student_a, student_b])
        await session.flush()

        # Create syllabus topic
        from app.models.syllabus import SyllabusNode
        topic = SyllabusNode(
            student_id=student_a.id,
            node_type="topic",
            title="Kinematics",
            order_index=0,
            estimated_minutes=30,
        )
        session.add(topic)
        await session.flush()

        # Create mastery for Student A
        mastery_a = TopicMastery(
            student_id=student_a.id,
            topic_id=topic.id,
            stability=2.0,
            difficulty=3.5,
            reps=2,
            lapses=0,
            state="review",
            mastery_score=0.65,
        )
        session.add(mastery_a)
        await session.commit()

        # Query mastery - Student A should see their record
        repo_a = StudentScopedRepository(TopicMastery, session)
        masteries_a = await repo_a.get_all(student_id=student_a.id)
        assert len(masteries_a) == 1
        assert masteries_a[0].student_id == student_a.id

        # Student B should see no mastery records
        repo_b = StudentScopedRepository(TopicMastery, session)
        masteries_b = await repo_b.get_all(student_id=student_b.id)
        assert len(masteries_b) == 0


@pytest.mark.asyncio
async def test_attempt_isolation(test_db_session):
    """Tests that Attempt records are isolated per student."""
    async with test_db_session() as session:
        student_a = Student(phone_number="919876543210", name="Student A")
        student_b = Student(phone_number="919876543211", name="Student B")
        session.add_all([student_a, student_b])
        await session.flush()

        from app.models.syllabus import SyllabusNode
        from app.models.quiz import QuestionBank
        topic = SyllabusNode(
            student_id=student_a.id,
            node_type="topic",
            title="Kinematics",
            order_index=0,
            estimated_minutes=30,
        )
        session.add(topic)
        await session.flush()

        question = QuestionBank(
            topic_id=topic.id,
            question_type="MCQ",
            question_text="Test question",
            options={"A": "Opt A", "B": "Opt B", "C": "Opt C"},
            correct_answer="A",
            explanation="Test explanation",
            difficulty="medium",
            verifier_score=1.0,
        )
        session.add(question)
        await session.flush()

        # Create attempt for Student A
        attempt_a = Attempt(
            student_id=student_a.id,
            question_id=question.id,
            student_response="A",
            is_correct=True,
            score=1.0,
            feedback="Correct",
            time_taken_seconds=30,
        )
        session.add(attempt_a)
        await session.commit()

        # Query attempts
        repo_a = StudentScopedRepository(Attempt, session)
        attempts_a = await repo_a.get_all(student_id=student_a.id)
        assert len(attempts_a) == 1
        assert attempts_a[0].student_id == student_a.id

        # Student B should see no attempts
        repo_b = StudentScopedRepository(Attempt, session)
        attempts_b = await repo_b.get_all(student_id=student_b.id)
        assert len(attempts_b) == 0