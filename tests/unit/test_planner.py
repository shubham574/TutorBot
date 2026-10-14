"""Unit tests for StudyPlannerService."""
import datetime
import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.services.planner.service import study_planner


@pytest.fixture
async def planner_db():
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
async def test_generate_study_plan_with_topics(planner_db):
    """Verifies that syllabus topics are distributed across schedule with revision buffer."""
    student_id = uuid.uuid4()
    today = datetime.date(2026, 10, 1)
    exam_date = datetime.date(2026, 10, 31)  # 30 days

    async with planner_db() as session:
        student = Student(id=student_id, phone_number="919876543210", name="Dev")
        session.add(student)

        # Add 4 topics
        for i in range(1, 5):
            topic = SyllabusNode(
                id=uuid.uuid4(),
                student_id=student_id,
                node_type="topic",
                title=f"Physics Topic {i}",
                order_index=i,
                estimated_minutes=45,
            )
            session.add(topic)
        await session.commit()

        plan = await study_planner.generate_study_plan(
            student_id=student_id,
            session=session,
            start_date=today,
            target_exam_date=exam_date,
        )

        assert plan is not None
        assert plan.student_id == student_id
        assert plan.status == "active"
        # 4 topics + 1 final buffer revision session = 5 sessions
        assert len(plan.plan_schedule) == 5
        assert plan.plan_schedule[0]["topic_name"] == "Physics Topic 1"
        assert "Full Syllabus Review" in plan.plan_schedule[-1]["topic_name"]


@pytest.mark.asyncio
async def test_generate_study_plan_no_topics(planner_db):
    """Verifies fallback when student has not yet uploaded syllabus."""
    student_id = uuid.uuid4()
    today = datetime.date(2026, 10, 1)

    async with planner_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        session.add(student)
        await session.commit()

        plan = await study_planner.generate_study_plan(
            student_id=student_id,
            session=session,
            start_date=today,
        )

        assert len(plan.plan_schedule) == 1
        assert plan.plan_schedule[0]["topic_name"] == "Syllabus Overview & Foundation"


def test_format_study_plan_for_whatsapp():
    """Verifies formatting of study plan message and buttons."""
    from app.models.study_plan import StudyPlan

    plan = StudyPlan(
        student_id=uuid.uuid4(),
        status="active",
        start_date=datetime.date(2026, 10, 1),
        target_exam_date=datetime.date(2026, 10, 31),
        plan_schedule=[
            {
                "day": 1,
                "date": "2026-10-01",
                "topic_id": str(uuid.uuid4()),
                "topic_name": "Kinematics",
                "target_minutes": 45,
                "status": "pending",
            },
            {
                "day": 2,
                "date": "2026-10-02",
                "topic_id": str(uuid.uuid4()),
                "topic_name": "Dynamics",
                "target_minutes": 50,
                "status": "completed",
            },
        ],
    )

    body, buttons = study_planner.format_study_plan_for_whatsapp(plan, "Physics")
    assert "Personalized Study Plan: Physics" in body
    assert "Kinematics" in body
    assert "Dynamics" in body
    assert len(buttons) == 2
    assert buttons[0].id == "start_first_topic"
