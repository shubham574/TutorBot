"""Unit tests for hybrid retriever and answer mode gating."""
import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.content import ContentChunk
from app.rag.retriever import retriever, AnswerMode
from app.services.llm.embeddings import generate_deterministic_embedding


@pytest.fixture
async def content_db():
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
async def test_retriever_empty_corpus_declines(content_db):
    """Empty database should trigger DECLINE_OR_CLARIFY mode."""
    async with content_db() as session:
        result = await retriever.retrieve(
            query="Explain Newton's third law",
            student_id=uuid.uuid4(),
            session=session,
        )
        assert result.mode == AnswerMode.DECLINE_OR_CLARIFY
        assert result.confidence == 0.0
        assert len(result.chunks) == 0


@pytest.mark.asyncio
async def test_retriever_grounded_mode_with_shared_corpus(content_db):
    """Relevant content in shared corpus (student_id=None) returns GROUNDED mode."""
    content_text = "Newton's Third Law states that for every action there is an equal and opposite reaction."
    emb = generate_deterministic_embedding(content_text)

    async with content_db() as session:
        chunk = ContentChunk(
            id=uuid.uuid4(),
            student_id=None,  # Shared institutional corpus
            subject="Physics",
            source_doc_id="ncert_phy_ch5",
            source_title="NCERT Physics Class 11",
            page_number=45,
            content=content_text,
            embedding=emb,
        )
        session.add(chunk)
        await session.commit()

    student_id = uuid.uuid4()
    async with content_db() as session:
        result = await retriever.retrieve(
            query="What is Newton's third law of motion?",
            student_id=student_id,
            session=session,
        )
        assert result.mode in [AnswerMode.GROUNDED, AnswerMode.GENERAL_KNOWLEDGE]
        assert len(result.chunks) >= 1
        assert result.chunks[0].page_number == 45
        assert result.chunks[0].source_title == "NCERT Physics Class 11"


@pytest.mark.asyncio
async def test_retriever_private_student_isolation(content_db):
    """Student A cannot access Student B's private uploaded chunks."""
    student_a_id = uuid.uuid4()
    student_b_id = uuid.uuid4()

    text_b = "Private notes about Quantum Tunneling belonging exclusively to Student B."
    emb_b = generate_deterministic_embedding(text_b)

    async with content_db() as session:
        chunk_b = ContentChunk(
            id=uuid.uuid4(),
            student_id=student_b_id,
            subject="Physics",
            source_doc_id="notes_b_01",
            source_title="Student B Private Notes",
            page_number=1,
            content=text_b,
            embedding=emb_b,
        )
        session.add(chunk_b)
        await session.commit()

    # Query as Student A
    async with content_db() as session:
        res_a = await retriever.retrieve(
            query="Quantum Tunneling",
            student_id=student_a_id,
            session=session,
        )
        # Should NOT find student B's private chunk
        assert len(res_a.chunks) == 0
        assert res_a.mode == AnswerMode.DECLINE_OR_CLARIFY
