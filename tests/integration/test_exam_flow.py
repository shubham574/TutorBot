"""Integration tests for exam paper generation and grading flow."""
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.services.grading.service import GradingReport, StepScore
from app.workers.tasks import process_whatsapp_message


@pytest.fixture
async def exam_flow_db():
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
async def test_exam_paper_generation_flow(exam_flow_db):
    """Student requests an exam paper using /exam."""
    student_id = uuid.uuid4()

    async with exam_flow_db() as session:
        student = Student(id=student_id, phone_number="919876543210", name="Dev")
        topic = SyllabusNode(id=uuid.uuid4(), student_id=student_id, node_type="topic", title="Thermodynamics")
        session.add_all([student, topic])
        await session.commit()

    message_data = {
        "wamid": "wamid.EXAM_REQ_001",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/exam",
        "raw_payload": {},
    }

    res = await process_whatsapp_message(ctx={}, message_data=message_data)
    assert res["status"] == "success"


@pytest.mark.asyncio
async def test_subjective_grading_submission_flow(exam_flow_db):
    """Student submits an answer for grading using /grade."""
    mock_report = GradingReport(
        max_marks=5.0,
        total_awarded=5.0,
        percentage=100.0,
        step_breakdown=[
            StepScore(step_name="Formula", max_marks=2.0, marks_awarded=2.0, feedback="Perfect"),
            StepScore(step_name="Working", max_marks=2.0, marks_awarded=2.0, feedback="Step-by-step"),
            StepScore(step_name="Result", max_marks=1.0, marks_awarded=1.0, feedback="Exact"),
        ],
        strengths=["Clear logic"],
        areas_for_improvement=[],
        sympy_verified=True,
        overall_summary="Flawless answer.",
    )

    message_data = {
        "wamid": "wamid.GRADE_REQ_002",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/grade Derive kinetic energy --- K = 1/2 * m * v^2",
        "raw_payload": {},
    }

    with patch("app.services.grading.service.llm_client.extract_structured", new=AsyncMock(return_value=mock_report)):
        res = await process_whatsapp_message(ctx={}, message_data=message_data)
        assert res["status"] == "success"
