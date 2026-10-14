"""Mastery tracking database model using FSRS (Free Spaced Repetition Scheduler)."""
import datetime
import uuid
from typing import Optional
from sqlalchemy import Float, Integer, String, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class TopicMastery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Student mastery state per syllabus node tracked via FSRS.
    """
    __tablename__ = "mastery"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("syllabus_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stability: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="FSRS memory stability in days",
    )
    difficulty: Mapped[float] = mapped_column(
        Float,
        default=5.0,
        nullable=False,
        comment="FSRS difficulty rating (1.0 to 10.0)",
    )
    reps: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total successful repetitions",
    )
    lapses: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times student failed the question",
    )
    state: Mapped[str] = mapped_column(
        String(32),
        default="new",
        nullable=False,
        comment="new, learning, review",
    )
    last_reviewed: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_review: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    mastery_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Normalized retention mastery level (0.0 to 1.0)",
    )
