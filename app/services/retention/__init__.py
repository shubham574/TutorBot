"""Data Retention Service: Automated cleanup of inactive student data with warning notifications."""
import datetime
import uuid
from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.settings import settings
from app.config.logging_config import logger
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog
from app.services.deletion import data_deletion_service
from app.services.whatsapp.client import whatsapp_client
from app.services.whatsapp.schemas import OutgoingReplyButton


class DataRetentionService:
    """Handles automated data retention policies with warnings and purging."""

    def __init__(self):
        self.inactive_days = settings.RETENTION_INACTIVE_DAYS
        self.warning_days = settings.RETENTION_WARNING_DAYS

    async def run_retention_job(self, session: AsyncSession) -> dict:
        """
        Runs the full retention job:
        1. Finds students inactive for (inactive_days - warning_days) -> send warning
        2. Finds students inactive for inactive_days -> purge data

        Returns:
            dict: Summary of actions taken
        """
        logger.info("Starting data retention job", inactive_days=self.inactive_days, warning_days=self.warning_days)

        now = datetime.datetime.now(datetime.timezone.utc)
        warning_cutoff = now - datetime.timedelta(days=self.inactive_days - self.warning_days)
        purge_cutoff = now - datetime.timedelta(days=self.inactive_days)

        results = {
            "warnings_sent": 0,
            "students_purged": 0,
            "errors": [],
        }

        # 1. Send warnings to students approaching purge threshold
        warning_students = await self._get_inactive_students(session, warning_cutoff, purge_cutoff)
        for student in warning_students:
            try:
                await self._send_retention_warning(student, session)
                results["warnings_sent"] += 1
            except Exception as e:
                logger.error("Failed to send retention warning", student_id=str(student.id), error=str(e))
                results["errors"].append(f"Warning failed for {student.id}: {e}")

        # 2. Purge students past the inactive threshold
        purge_students = await self._get_inactive_students(session, purge_cutoff, None)
        for student in purge_students:
            try:
                await self._purge_student_data(student, session)
                results["students_purged"] += 1
            except Exception as e:
                logger.error("Failed to purge student data", student_id=str(student.id), error=str(e))
                results["errors"].append(f"Purge failed for {student.id}: {e}")

        logger.info("Completed data retention job", **results)
        return results

    async def _get_inactive_students(
        self,
        session: AsyncSession,
        cutoff: datetime.datetime,
        upper_bound: Optional[datetime.datetime] = None,
    ) -> List[Student]:
        """
        Gets students whose last inbound message was before the cutoff.

        Args:
            session: Database session
            cutoff: Students inactive since before this time
            upper_bound: Optional upper bound (for warning phase)

        Returns:
            List of inactive Student objects
        """
        # Subquery to get last inbound message time per student
        subq = (
            select(
                WhatsAppMessageLog.student_id,
                func.max(WhatsAppMessageLog.created_at).label("last_inbound"),
            )
            .where(
                and_(
                    WhatsAppMessageLog.direction == "INBOUND",
                    WhatsAppMessageLog.student_id.is_not(None),
                )
            )
            .group_by(WhatsAppMessageLog.student_id)
            .subquery()
        )

        # Main query: students with last_inbound < cutoff
        stmt = select(Student).join(
            subq,
            Student.id == subq.c.student_id,
        ).where(
            and_(
                Student.is_active == True,
                subq.c.last_inbound < cutoff,
            )
        )

        if upper_bound:
            stmt = stmt.where(subq.c.last_inbound >= upper_bound)

        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def _send_retention_warning(self, student: Student, session: AsyncSession) -> None:
        """Sends a retention warning notification to the student."""
        warning_message = (
            f"⚠️ *Data Retention Notice*\n\n"
            f"Your TutorBot account has been inactive for {self.inactive_days - self.warning_days} days.\n\n"
            f"To protect your privacy, accounts inactive for {self.inactive_days} days "
            f"are automatically deleted along with all associated data (syllabus, progress, quizzes, files).\n\n"
            f"*Your data will be permanently deleted in {self.warning_days} days.*\n\n"
            f"To keep your account active, simply send any message or use a command like /help, /quiz, or /progress."
        )

        buttons = [
            OutgoingReplyButton(id="help_menu", title="❓ Help Menu"),
            OutgoingReplyButton(id="view_progress", title="📊 My Progress"),
        ]

        res = await whatsapp_client.send_interactive_buttons(
            recipient_phone=student.phone_number,
            body_text=warning_message,
            buttons=buttons,
        )

        # Log the outbound warning message
        sent_wamid = res.get("messages", [{}])[0].get("id") if res.get("messages") else f"retention_warning_{student.id}"
        outbound_log = WhatsAppMessageLog(
            wamid=sent_wamid,
            student_id=student.id,
            phone_number=student.phone_number,
            direction="OUTBOUND",
            message_type="interactive",
            raw_payload=res,
            status="SENT",
        )
        session.add(outbound_log)
        await session.commit()

        logger.info("Sent retention warning", student_id=str(student.id), phone=student.phone_number)

    async def _purge_student_data(self, student: Student, session: AsyncSession) -> None:
        """Purges all data for an inactive student."""
        logger.info("Purging inactive student data", student_id=str(student.id))

        # Use the existing data deletion service
        await data_deletion_service.delete_student_data(
            student_id=student.id,
            session=session,
        )

        logger.info("Purged inactive student data", student_id=str(student.id))


data_retention_service = DataRetentionService()