"""Unit tests for structure-aware document chunking."""
import uuid
import pytest
from app.rag.chunker import chunker, DocumentChunk, MAX_CHUNK_CHARS, TARGET_CHUNK_CHARS


def test_chunk_pages_preserves_metadata():
    pages = [
        (1, "Chapter 1: Kinematics\n\nMotion in a straight line is the simplest form of motion."),
        (2, "Chapter 1 Continued\n\nVelocity is the rate of change of position with respect to time."),
    ]
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    chunks = chunker.chunk_document_pages(
        pages=pages,
        subject="Physics",
        source_doc_id="doc_ncert_phy_ch1",
        source_title="NCERT Physics Class 11",
        doc_type="textbook",
        difficulty="medium",
        topic_id=topic_id,
        student_id=student_id,
    )

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[0].subject == "Physics"
    assert chunks[0].source_title == "NCERT Physics Class 11"
    assert chunks[0].student_id == student_id
    assert chunks[0].topic_id == topic_id
    assert chunks[1].page_number == 2


def test_chunk_large_page_splits_with_bounds():
    # Construct a page exceeding MAX_CHUNK_CHARS (~4000 characters)
    paragraphs = [f"Paragraph {i}: " + ("Educational explanation of physics. " * 25) for i in range(5)]
    large_page_text = "\n\n".join(paragraphs)
    assert len(large_page_text) > MAX_CHUNK_CHARS

    chunks = chunker.chunk_document_pages(
        pages=[(1, large_page_text)],
        subject="Physics",
        source_doc_id="doc_large_01",
        source_title="Comprehensive Physics",
    )

    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.content) <= MAX_CHUNK_CHARS
        assert c.page_number == 1
