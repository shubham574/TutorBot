"""Integration tests for Tutor Agent and the 3 answer modes."""
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.content import ContentChunk
from app.rag.tutor import tutor_agent, AnswerMode
from app.rag.retriever import RetrievalResult, RetrievedChunk
from app.workers.tasks import process_whatsapp_message


@pytest.fixture
async def tutor_test_db():
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
async def test_tutor_mode_grounded_includes_citations(tutor_test_db):
    """Grounded mode must cite page numbers and source documents."""
    mock_chunks = [
        RetrievedChunk(
            chunk_id=uuid.uuid4(),
            content="Total Internal Reflection occurs when the angle of incidence exceeds the critical angle.",
            source_title="NCERT Physics Part 2",
            page_number=120,
            subject="Physics",
            score=0.88,
            doc_type="textbook",
        )
    ]
    mock_retrieval = RetrievalResult(
        mode=AnswerMode.GROUNDED,
        confidence=0.88,
        rewritten_query="Total Internal Reflection",
        chunks=mock_chunks,
    )

    async with tutor_test_db() as session:
        with patch("app.rag.tutor.retriever.retrieve", new=AsyncMock(return_value=mock_retrieval)):
            with patch("app.rag.tutor.llm_client.chat_completion", new=AsyncMock(return_value="Total Internal Reflection is a phenomenon where light rays are reflected completely back into the denser medium.")):
                reply, buttons, mode = await tutor_agent.answer_question(
                    question="Explain Total Internal Reflection",
                    student_id=uuid.uuid4(),
                    session=session,
                )

    assert mode == AnswerMode.GROUNDED
    assert "Sources & Page Citations" in reply
    assert "NCERT Physics Part 2 (Page 120)" in reply
    assert any(b.id == "quiz_this_topic" for b in buttons)


@pytest.mark.asyncio
async def test_tutor_mode_general_knowledge_includes_disclaimer(tutor_test_db):
    """General knowledge mode must include the mandatory transparency disclaimer."""
    mock_retrieval = RetrievalResult(
        mode=AnswerMode.GENERAL_KNOWLEDGE,
        confidence=0.52,
        rewritten_query="Avogadro constant",
        chunks=[],
    )

    async with tutor_test_db() as session:
        with patch("app.rag.tutor.retriever.retrieve", new=AsyncMock(return_value=mock_retrieval)):
            with patch("app.rag.tutor.llm_client.chat_completion", new=AsyncMock(return_value="The Avogadro constant is 6.022 x 10²³ particles per mole.")):
                reply, buttons, mode = await tutor_agent.answer_question(
                    question="What is Avogadro's number?",
                    student_id=uuid.uuid4(),
                    session=session,
                )

    assert mode == AnswerMode.GENERAL_KNOWLEDGE
    assert "This explanation is based on general curriculum knowledge" in reply
    assert "not directly found in your uploaded study notes" in reply


@pytest.mark.asyncio
async def test_tutor_mode_decline_or_clarify(tutor_test_db):
    """Low confidence requests must decline gracefully and suggest uploading notes."""
    mock_retrieval = RetrievalResult(
        mode=AnswerMode.DECLINE_OR_CLARIFY,
        confidence=0.15,
        rewritten_query="xyz unknown topic",
        chunks=[],
    )

    async with tutor_test_db() as session:
        with patch("app.rag.tutor.retriever.retrieve", new=AsyncMock(return_value=mock_retrieval)):
            reply, buttons, mode = await tutor_agent.answer_question(
                question="Tell me about xyz unknown topic",
                student_id=uuid.uuid4(),
                session=session,
            )

    assert mode == AnswerMode.DECLINE_OR_CLARIFY
    assert "couldn't find enough reliable material" in reply
    assert any(b.id == "reupload_syllabus" for b in buttons)


@pytest.mark.asyncio
async def test_worker_academic_question_flow(tutor_test_db):
    """Verifies end-to-end task flow when student asks an academic question."""
    message_data = {
        "wamid": "wamid.QUESTION_01",
        "sender_phone": "919876543210",
        "sender_name": "Bob",
        "message_type": "text",
        "text_content": "Can you explain Photosynthesis?",
        "raw_payload": {},
    }

    with patch("app.rag.tutor.tutor_agent.answer_question", new=AsyncMock(return_value=(
        "Photosynthesis is the process by which green plants create food.\n\n📖 *Sources & Page Citations:*\n• Biology Textbook (Page 55)",
        [],
        AnswerMode.GROUNDED
    ))):
        res = await process_whatsapp_message(ctx={}, message_data=message_data)
        assert res["status"] == "success"
