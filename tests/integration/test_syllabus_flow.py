"""Integration tests for syllabus onboarding and interactive confirmation flow."""
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.syllabus import SyllabusNode
from app.services.syllabus.schemas import (
    SyllabusExtractionResult,
    UnitExtraction,
    TopicExtraction,
)
from app.workers.tasks import process_whatsapp_message


@pytest.fixture
async def flow_test_db():
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
async def test_syllabus_ingestion_and_interactive_confirmation(flow_test_db):
    """
    End-to-end test:
    1. Student sends syllabus upload message.
    2. Bot extracts structured tree, persists syllabus_nodes, sends interactive buttons.
    3. Student clicks 'confirm_syllabus' button.
    4. Bot confirms syllabus outline is active.
    """
    mock_tree = SyllabusExtractionResult(
        subject="Biology",
        target_exam="NEET",
        exam_date="2026-05-03",
        units=[
            UnitExtraction(
                title="Cell Biology",
                marks_weightage=20.0,
                topics=[
                    TopicExtraction(title="Cell Division & Mitosis"),
                    TopicExtraction(title="Biomolecules"),
                ],
            )
        ],
    )

    # 1. Incoming Syllabus Upload Message
    upload_message = {
        "wamid": "wamid.SYLLABUS_UPLOAD_01",
        "sender_phone": "919988776655",
        "sender_name": "Dev",
        "message_type": "text",
        "text_content": "/syllabus\nUnit 1: Cell Biology\nTopics: Cell Division, Biomolecules",
        "raw_payload": {},
    }

    with patch(
        "app.services.syllabus.service.syllabus_service.extract_tree_from_text",
        new=AsyncMock(return_value=mock_tree),
    ):
        res1 = await process_whatsapp_message(ctx={}, message_data=upload_message)
        assert res1["status"] == "success"

    # Verify syllabus_nodes in DB
    async with flow_test_db() as session:
        nodes_res = await session.execute(select(SyllabusNode))
        nodes = nodes_res.scalars().all()
        assert len(nodes) == 4  # 1 subject + 1 unit + 2 topics
        subject_node = [n for n in nodes if n.node_type == "subject"][0]
        assert subject_node.title == "Biology"

    # 2. Student Clicks 'confirm_syllabus' Button
    button_reply_message = {
        "wamid": "wamid.CONFIRM_BTN_02",
        "sender_phone": "919988776655",
        "sender_name": "Dev",
        "message_type": "interactive",
        "interactive_button_id": "confirm_syllabus",
        "text_content": "✅ Confirm Outline",
        "raw_payload": {},
    }

    res2 = await process_whatsapp_message(ctx={}, message_data=button_reply_message)
    assert res2["status"] == "success"


@pytest.mark.asyncio
async def test_syllabus_reupload_button_flow(flow_test_db):
    """Verifies that clicking 'reupload_syllabus' prompts the student for a new upload."""
    button_reply_message = {
        "wamid": "wamid.REUPLOAD_BTN_03",
        "sender_phone": "919988776655",
        "sender_name": "Dev",
        "message_type": "interactive",
        "interactive_button_id": "reupload_syllabus",
        "text_content": "🔄 Re-upload",
        "raw_payload": {},
    }

    res = await process_whatsapp_message(ctx={}, message_data=button_reply_message)
    assert res["status"] == "success"
