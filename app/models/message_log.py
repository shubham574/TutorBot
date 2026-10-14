"""WhatsApp messages log database model for deduplication and audit."""
import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.student import Student


class WhatsAppMessageLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Logs inbound and outbound WhatsApp messages for idempotency and audit trail."""
    __tablename__ = "whatsapp_messages_log"

    wamid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
        comment="Meta WhatsApp message ID used for deduplication",
    )
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        comment="Sender or recipient phone number",
    )
    direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="INBOUND or OUTBOUND",
    )
    message_type: Mapped[str] = mapped_column(
        String(32),
        default="text",
        nullable=False,
        comment="text, interactive, document, audio, etc.",
    )
    raw_payload: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="Raw incoming or outgoing JSON payload",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="RECEIVED",
        index=True,
        nullable=False,
        comment="RECEIVED, QUEUED, PROCESSED, FAILED, SENT",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        back_populates="messages",
    )
