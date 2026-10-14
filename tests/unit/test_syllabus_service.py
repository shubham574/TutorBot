"""Unit tests for syllabus ingestion service."""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.services.syllabus.schemas import (
    SyllabusExtractionResult,
    UnitExtraction,
    TopicExtraction,
    SubtopicExtraction,
)
from app.services.syllabus.service import syllabus_service


@pytest.fixture
async def in_memory_db():
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
async def test_save_tree_to_db(in_memory_db):
    """Verifies that save_tree_to_db creates hierarchical nodes with proper parent linkages."""
    student_id = uuid.uuid4()

    # Pre-create student record
    async with in_memory_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        session.add(student)
        await session.commit()

    sample_tree = SyllabusExtractionResult(
        subject="Chemistry",
        target_exam="CBSE 12",
        exam_date="2026-03-20",
        units=[
            UnitExtraction(
                title="Unit 1: Solutions",
                marks_weightage=12.0,
                topics=[
                    TopicExtraction(
                        title="Raoult's Law",
                        estimated_minutes=45,
                        subtopics=[
                            SubtopicExtraction(title="Ideal Solutions"),
                            SubtopicExtraction(title="Azeotropes"),
                        ],
                    ),
                    TopicExtraction(
                        title="Colligative Properties",
                        estimated_minutes=50,
                        subtopics=[],
                    ),
                ],
            ),
            UnitExtraction(
                title="Unit 2: Electrochemistry",
                marks_weightage=14.0,
                topics=[],
            ),
        ],
    )

    async with in_memory_db() as session:
        root_node = await syllabus_service.save_tree_to_db(
            student_id=student_id,
            tree=sample_tree,
            session=session,
        )
        await session.commit()
        root_id = root_node.id

    # Verify nodes in database
    async with in_memory_db() as session:
        # 1. Subject root
        subject_res = await session.execute(
            select(SyllabusNode).where(SyllabusNode.node_type == "subject")
        )
        subjects = subject_res.scalars().all()
        assert len(subjects) == 1
        assert subjects[0].title == "Chemistry"
        assert str(subjects[0].exam_date) == "2026-03-20"

        # 2. Units
        unit_res = await session.execute(
            select(SyllabusNode).where(SyllabusNode.node_type == "unit")
        )
        units = unit_res.scalars().all()
        assert len(units) == 2
        assert all(u.parent_id == root_id for u in units)

        # 3. Topics
        topic_res = await session.execute(
            select(SyllabusNode).where(SyllabusNode.node_type == "topic")
        )
        topics = topic_res.scalars().all()
        assert len(topics) == 2

        # 4. Subtopics
        subtopic_res = await session.execute(
            select(SyllabusNode).where(SyllabusNode.node_type == "subtopic")
        )
        subtopics = subtopic_res.scalars().all()
        assert len(subtopics) == 2


def test_format_confirmation_message():
    sample_tree = SyllabusExtractionResult(
        subject="Mathematics",
        target_exam="JEE Main",
        exam_date="2026-04-10",
        units=[
            UnitExtraction(
                title="Calculus",
                marks_weightage=40.0,
                topics=[
                    TopicExtraction(title="Limits & Continuity"),
                    TopicExtraction(title="Integration"),
                ],
            )
        ],
    )

    msg_body, buttons = syllabus_service.format_confirmation_message(sample_tree)
    assert "Syllabus Ingested: Mathematics" in msg_body
    assert "JEE Main" in msg_body
    assert "Calculus" in msg_body
    assert len(buttons) == 2
    assert buttons[0].id == "confirm_syllabus"
    assert buttons[1].id == "reupload_syllabus"
