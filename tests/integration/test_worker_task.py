"""Integration tests for ARQ worker tasks and echo bot pipeline."""
import pytest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog
from app.workers.tasks import process_whatsapp_message


@pytest.fixture
async def test_db_session():
    """Sets up an in-memory SQLite database for task testing."""
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
async def test_worker_process_echo_message(test_db_session):
    """Verifies that an incoming message creates student, echoes text, and logs in DB."""
    message_data = {
        "wamid": "wamid.TEST_WORKER_001",
        "sender_phone": "919876543210",
        "sender_name": "Alice",
        "message_type": "text",
        "text_content": "Can you help me study Physics?",
        "raw_payload": {"test": "data"},
    }

    result = await process_whatsapp_message(ctx={}, message_data=message_data)
    assert result["status"] == "success"
    assert result["wamid"] == "wamid.TEST_WORKER_001"

    # Verify DB records
    async with test_db_session() as session:
        # Check student
        student_res = await session.execute(
            select(Student).where(Student.phone_number == "919876543210")
        )
        student = student_res.scalar_one_or_none()
        assert student is not None
        assert student.name == "Alice"

        # Check inbound message log
        inbound_res = await session.execute(
            select(WhatsAppMessageLog).where(WhatsAppMessageLog.wamid == "wamid.TEST_WORKER_001")
        )
        inbound_log = inbound_res.scalar_one_or_none()
        assert inbound_log is not None
        assert inbound_log.direction == "INBOUND"
        assert inbound_log.status == "PROCESSED"
        assert inbound_log.student_id == student.id

        # Check outbound message log
        outbound_res = await session.execute(
            select(WhatsAppMessageLog).where(WhatsAppMessageLog.direction == "OUTBOUND")
        )
        outbound_logs = outbound_res.scalars().all()
        assert len(outbound_logs) >= 1
        assert outbound_logs[0].status == "SENT"
        assert outbound_logs[0].student_id == student.id


@pytest.mark.asyncio
async def test_worker_deduplication(test_db_session):
    """Verifies that processing the same message twice is skipped via DB log check."""
    message_data = {
        "wamid": "wamid.TEST_WORKER_DUP_002",
        "sender_phone": "919876543210",
        "sender_name": "Alice",
        "message_type": "text",
        "text_content": "First run",
        "raw_payload": {},
    }

    # First run
    res1 = await process_whatsapp_message(ctx={}, message_data=message_data)
    assert res1["status"] == "success"

    # Second run with same wamid
    res2 = await process_whatsapp_message(ctx={}, message_data=message_data)
    assert res2["status"] == "duplicate_skipped"


@pytest.mark.asyncio
async def test_worker_ping_command(test_db_session):
    """Verifies that /ping receives the Pong response."""
    message_data = {
        "wamid": "wamid.TEST_PING_003",
        "sender_phone": "919876543210",
        "sender_name": "Bob",
        "message_type": "text",
        "text_content": "/ping",
        "raw_payload": {},
    }

    result = await process_whatsapp_message(ctx={}, message_data=message_data)
    assert result["status"] == "success"
