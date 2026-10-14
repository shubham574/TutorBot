"""Study plan database model for adaptive learning schedules."""
import datetime
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Date, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class StudyPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Personalized timeline allocating curriculum topics across available study days."""
    __tablename__ = "study_plans"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_schedule: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        comment="List of daily session objects with date, topic_id, topic_name, minutes, status",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
        comment="active, completed, archived",
    )
    start_date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
    )
    target_exam_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date,
        nullable=True,
    )
