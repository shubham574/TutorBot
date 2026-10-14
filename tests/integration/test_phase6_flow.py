"""Integration tests for Phase 6: Planner, Spaced-Repetition Nudges, and Progress."""
import datetime
import uuid
import pytest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.mastery import TopicMastery
from app.models.study_plan import StudyPlan
from app.workers.tasks import process_whatsapp_message, dispatch_scheduled_nudges


@pytest.fixture
async def phase6_db():
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
async def test_study_plan_generation_flow(phase6_db):
    """Student requests their study schedule via /plan."""
    student_id = uuid.uuid4()

    async with phase6_db() as session:
        student = Student(id=student_id, phone_number="919876543210", name="Dev")
        t1 = SyllabusNode(id=uuid.uuid4(), student_id=student_id, node_type="topic", title="Thermodynamics")
        t2 = SyllabusNode(id=uuid.uuid4(), student_id=student_id, node_type="topic", title="Optics")
        session.add_all([student, t1, t2])
        await session.commit()

    msg_data = {
        "wamid": "wamid.PLAN_REQ_001",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/plan",
        "raw_payload": {},
    }

    res = await process_whatsapp_message(ctx={}, message_data=msg_data)
    assert res["status"] == "success"

    # Verify study plan was created in database
    async with phase6_db() as session:
        plan_stmt = select(StudyPlan).where(StudyPlan.student_id == student_id)
        plan_res = await session.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        assert plan is not None
        assert len(plan.plan_schedule) >= 2


@pytest.mark.asyncio
async def test_progress_dashboard_flow(phase6_db):
    """Student requests their academic dashboard via /progress."""
    student_id = uuid.uuid4()

    async with phase6_db() as session:
        student = Student(id=student_id, phone_number="919876543210", name="Dev")
        session.add(student)
        await session.commit()

    msg_data = {
        "wamid": "wamid.PROG_REQ_001",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/progress",
        "raw_payload": {},
    }

    res = await process_whatsapp_message(ctx={}, message_data=msg_data)
    assert res["status"] == "success"


@pytest.mark.asyncio
async def test_opt_out_and_opt_in_flow(phase6_db):
    """Student opts out of proactive nudges with /opt-out and resumes with /opt-in."""
    student_id = uuid.uuid4()

    async with phase6_db() as session:
        student = Student(id=student_id, phone_number="919876543210", is_active=True)
        session.add(student)
        await session.commit()

    # 1. Opt out
    msg_out = {
        "wamid": "wamid.OPT_OUT_001",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/opt-out",
        "raw_payload": {},
    }
    await process_whatsapp_message(ctx={}, message_data=msg_out)

    async with phase6_db() as session:
        s_res = await session.execute(select(Student).where(Student.id == student_id))
        s = s_res.scalar_one()
        assert s.is_active is False

    # 2. Opt in
    msg_in = {
        "wamid": "wamid.OPT_IN_001",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/opt-in",
        "raw_payload": {},
    }
    await process_whatsapp_message(ctx={}, message_data=msg_in)

    async with phase6_db() as session:
        s_res = await session.execute(select(Student).where(Student.id == student_id))
        s = s_res.scalar_one()
        assert s.is_active is True


@pytest.mark.asyncio
async def test_voice_note_message_flow(phase6_db):
    """Student sends a voice note."""
    student_id = uuid.uuid4()

    async with phase6_db() as session:
        student = Student(id=student_id, phone_number="919876543210", name="Dev")
        session.add(student)
        await session.commit()

    msg_data = {
        "wamid": "wamid.VOICE_001",
        "sender_phone": "919876543210",
        "sender_name": "Dev",
        "message_type": "audio",
        "text_content": None,
        "raw_payload": {"audio": {"id": "media-audio-123"}},
    }

    res = await process_whatsapp_message(ctx={}, message_data=msg_data)
    assert res["status"] == "success"


@pytest.mark.asyncio
async def test_scheduled_nudges_dispatch(phase6_db):
    """Periodic task dispatches review nudges for due topics to active students."""
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    past_due = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    async with phase6_db() as session:
        student = Student(
            id=student_id,
            phone_number="919876543210",
            name="Dev",
            is_active=True,
            timezone="UTC",
            # Set daytime quiet hours so test run is not in quiet hours
            quiet_hours_start=datetime.time(1, 0),
            quiet_hours_end=datetime.time(2, 0),
        )
        topic = SyllabusNode(id=topic_id, student_id=student_id, node_type="topic", title="Newton Laws")
        mastery = TopicMastery(
            student_id=student_id,
            topic_id=topic_id,
            next_review=past_due,
            mastery_score=0.5,
        )
        session.add_all([student, topic, mastery])
        await session.commit()

    with patch("app.services.nudges.compliance.compliance_service.is_in_quiet_hours", return_value=False):
        dispatched_count = await dispatch_scheduled_nudges()
        assert dispatched_count == 1
