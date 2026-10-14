"""Student database model."""
import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.message_log import WhatsAppMessageLog


class Student(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Student profile and privacy/scheduling preferences."""
    __tablename__ = "students"

    phone_number: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        comment="E.164 formatted phone number",
    )
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    grade_level: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_exam: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Kolkata",
        nullable=False,
    )
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_given_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    quiet_hours_start: Mapped[datetime.time] = mapped_column(
        Time,
        default=datetime.time(22, 0),
        nullable=False,
    )
    quiet_hours_end: Mapped[datetime.time] = mapped_column(
        Time,
        default=datetime.time(7, 0),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    messages: Mapped[List["WhatsAppMessageLog"]] = relationship(
        "WhatsAppMessageLog",
        back_populates="student",
        cascade="all, delete-orphan",
    )
