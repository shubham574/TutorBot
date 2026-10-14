"""Content chunks database model for RAG hybrid search."""
import uuid
from typing import Optional, List
from sqlalchemy import String, Integer, Text, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ContentChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    RAG content chunk with structure-aware metadata, embeddings, and text.
    Supports both shared institutional corpus (student_id = NULL)
    and per-student private uploads.
    """
    __tablename__ = "content_chunks"

    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL represents shared global curriculum corpus",
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("syllabus_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Linked syllabus node for topic-specific retrieval",
    )
    subject: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    source_doc_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Unique identifier of the source document",
    )
    source_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Readable title (e.g., NCERT Physics Part 1)",
    )
    page_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(
        String(64),
        default="notes",
        nullable=False,
        comment="textbook, notes, handout, past_paper",
    )
    difficulty: Mapped[str] = mapped_column(
        String(32),
        default="medium",
        nullable=False,
        comment="easy, medium, hard",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Stored as JSON list of floats for database portability (Postgres + SQLite tests)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        JSON,
        nullable=True,
    )
