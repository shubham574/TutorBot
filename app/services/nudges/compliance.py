"""Deterministic compliance rules for WhatsApp: quiet hours, 24-hr window, and frequency caps."""
import datetime
import uuid
from typing import Optional
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog


class NudgeComplianceService:
    """Enforces deterministic policies before sending proactive outbound messages."""

    def is_in_quiet_hours(
        self,
        student: Student,
        current_time: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Checks whether current time falls within student's quiet hours in their local timezone.
        Default: 22:00 to 07:00.
        """
        now_utc = current_time or datetime.datetime.now(datetime.timezone.utc)
        try:
            tz = ZoneInfo(student.timezone or "Asia/Kolkata")
            local_now = now_utc.astimezone(tz)
        except Exception:
            local_now = now_utc

        current_local_time = local_now.time()
        start = student.quiet_hours_start
        end = student.quiet_hours_end

        # Case 1: Quiet hours span overnight (e.g., 22:00 to 07:00)
        if start > end:
            in_quiet = current_local_time >= start or current_local_time < end
        else:
            in_quiet = start <= current_local_time < end

        if in_quiet:
            logger.info(
                "Proactive message blocked by student quiet hours",
                student_id=str(student.id),
                local_time=str(current_local_time),
            )
        return in_quiet

    async def is_within_24h_window(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
        check_time: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Meta WhatsApp Cloud API policy: Freeform messages and interactive buttons
        can ONLY be sent within 24 hours of the student's last inbound message.
        Outside 24h, an approved business template must be used.
        """
        now = check_time or datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=24)

        stmt = (
            select(WhatsAppMessageLog.created_at)
            .where(
                and_(
                    WhatsAppMessageLog.student_id == student_id,
                    WhatsAppMessageLog.direction == "INBOUND",
                )
            )
            .order_by(WhatsAppMessageLog.created_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        last_inbound_time = res.scalar_one_or_none()

        if not last_inbound_time:
            return False

        # Make sure timezone aware
        if last_inbound_time.tzinfo is None:
            last_inbound_time = last_inbound_time.replace(tzinfo=datetime.timezone.utc)

        return last_inbound_time >= cutoff

    async def check_daily_frequency_cap(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
        max_nudges_per_day: int = 1,
    ) -> bool:
        """
        Guarantees students are not spammed with proactive notifications.
        Returns True if allowed to send, False if cap is reached.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        stmt = (
            select(func.count(WhatsAppMessageLog.id))
            .where(
                and_(
                    WhatsAppMessageLog.student_id == student_id,
                    WhatsAppMessageLog.direction == "OUTBOUND",
                    WhatsAppMessageLog.message_type == "proactive_nudge",
                    WhatsAppMessageLog.created_at >= today_start,
                )
            )
        )
        res = await session.execute(stmt)
        nudge_count = res.scalar() or 0
        return nudge_count < max_nudges_per_day


compliance_service = NudgeComplianceService()
