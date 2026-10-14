"""Unit tests for NudgeComplianceService (quiet hours, 24-hr window, frequency caps)."""
import datetime
import uuid
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog
from app.services.nudges.compliance import compliance_service


@pytest.fixture
async def compliance_db():
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


def test_is_in_quiet_hours_overnight():
    """Quiet hours from 22:00 to 07:00 local time (Asia/Kolkata)."""
    student = Student(
        id=uuid.uuid4(),
        phone_number="919876543210",
        timezone="Asia/Kolkata",
        quiet_hours_start=datetime.time(22, 0),
        quiet_hours_end=datetime.time(7, 0),
    )

    # 1. 23:30 IST (18:00 UTC) -> should be in quiet hours
    time_2330_ist = datetime.datetime(2026, 10, 15, 18, 0, tzinfo=datetime.timezone.utc)
    assert compliance_service.is_in_quiet_hours(student, current_time=time_2330_ist) is True

    # 2. 05:30 IST (00:00 UTC) -> should be in quiet hours
    time_0530_ist = datetime.datetime(2026, 10, 15, 0, 0, tzinfo=datetime.timezone.utc)
    assert compliance_service.is_in_quiet_hours(student, current_time=time_0530_ist) is True

    # 3. 14:30 IST (09:00 UTC) -> study time (NOT quiet hours)
    time_1430_ist = datetime.datetime(2026, 10, 15, 9, 0, tzinfo=datetime.timezone.utc)
    assert compliance_service.is_in_quiet_hours(student, current_time=time_1430_ist) is False


def test_is_in_quiet_hours_same_day():
    """Quiet hours from 01:00 to 05:00."""
    student = Student(
        id=uuid.uuid4(),
        phone_number="919876543210",
        timezone="UTC",
        quiet_hours_start=datetime.time(1, 0),
        quiet_hours_end=datetime.time(5, 0),
    )

    in_time = datetime.datetime(2026, 10, 15, 2, 30, tzinfo=datetime.timezone.utc)
    assert compliance_service.is_in_quiet_hours(student, current_time=in_time) is True

    out_time = datetime.datetime(2026, 10, 15, 6, 0, tzinfo=datetime.timezone.utc)
    assert compliance_service.is_in_quiet_hours(student, current_time=out_time) is False


@pytest.mark.asyncio
async def test_is_within_24h_window(compliance_db):
    """Verifies WhatsApp customer service 24-hr session window rule."""
    student_id = uuid.uuid4()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    async with compliance_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        session.add(student)
        await session.commit()

        # No messages -> False
        res_empty = await compliance_service.is_within_24h_window(student_id, session, check_time=now_utc)
        assert res_empty is False

        # Inbound message 2 hours ago -> True
        recent_log = WhatsAppMessageLog(
            wamid="wamid.RECENT_001",
            student_id=student_id,
            phone_number="919876543210",
            direction="INBOUND",
            message_type="text",
            created_at=now_utc - datetime.timedelta(hours=2),
        )
        session.add(recent_log)
        await session.commit()

        res_recent = await compliance_service.is_within_24h_window(student_id, session, check_time=now_utc)
        assert res_recent is True

        # Inbound message 26 hours ago -> False
        recent_log.created_at = now_utc - datetime.timedelta(hours=26)
        await session.commit()

        res_expired = await compliance_service.is_within_24h_window(student_id, session, check_time=now_utc)
        assert res_expired is False


@pytest.mark.asyncio
async def test_check_daily_frequency_cap(compliance_db):
    """Ensures max 1 proactive nudge per student per calendar day."""
    student_id = uuid.uuid4()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    async with compliance_db() as session:
        student = Student(id=student_id, phone_number="919876543210")
        session.add(student)
        await session.commit()

        # 0 nudges sent today -> allowed
        allowed_1 = await compliance_service.check_daily_frequency_cap(student_id, session, max_nudges_per_day=1)
        assert allowed_1 is True

        # Log a nudge sent today
        nudge_log = WhatsAppMessageLog(
            wamid="wamid.NUDGE_TODAY",
            student_id=student_id,
            phone_number="919876543210",
            direction="OUTBOUND",
            message_type="proactive_nudge",
            created_at=now_utc,
        )
        session.add(nudge_log)
        await session.commit()

        # 1 nudge already sent -> disallowed
        allowed_2 = await compliance_service.check_daily_frequency_cap(student_id, session, max_nudges_per_day=1)
        assert allowed_2 is False
