"""Quiz and question bank models."""
import datetime
import uuid
from typing import Dict, Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, Text, Boolean, ForeignKey, JSON, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.syllabus import SyllabusNode


class QuestionBank(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Verified questions grounded in syllabus topics."""
    __tablename__ = "question_bank"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("syllabus_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(
        String(32),
        default="MCQ",
        nullable=False,
        comment="MCQ, NUMERICAL, SUBJECTIVE",
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    options: Mapped[Dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        comment="Mapping of option keys to text, e.g. {'A': '...', 'B': '...', 'C': '...'}",
    )
    correct_answer: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="Key of the correct option (e.g. 'A')",
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    difficulty: Mapped[str] = mapped_column(
        String(32),
        default="medium",
        nullable=False,
        comment="easy, medium, hard",
    )
    verifier_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Dual-pass solver agreement score (0.0 to 1.0)",
    )
    verified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Attempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Log of a student's answer attempt for mastery tracking."""
    __tablename__ = "attempts"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_bank.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_response: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    time_taken_seconds: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
