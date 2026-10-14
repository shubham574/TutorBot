"""Syllabus hierarchy database model."""
import datetime
import uuid
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, Date, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.student import Student


class SyllabusNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Hierarchical syllabus representation:
    subject -> unit -> topic -> subtopic.
    Every RAG chunk, quiz question, and study plan references these nodes.
    """
    __tablename__ = "syllabus_nodes"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("syllabus_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="subject, unit, topic, subtopic",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    exam_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date,
        nullable=True,
    )
    marks_weightage: Mapped[Optional[float]] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )
    estimated_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        backref="syllabus_nodes",
    )
    parent: Mapped[Optional["SyllabusNode"]] = relationship(
        "SyllabusNode",
        remote_side="SyllabusNode.id",
        back_populates="children",
    )
    children: Mapped[List["SyllabusNode"]] = relationship(
        "SyllabusNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="SyllabusNode.order_index",
    )
