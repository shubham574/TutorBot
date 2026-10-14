"""Proactive spaced-repetition nudge dispatcher with compliance checks."""
import datetime
import uuid
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.mastery import TopicMastery
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.message_log import WhatsAppMessageLog
from app.services.nudges.compliance import compliance_service
from app.services.whatsapp.client import whatsapp_client
from app.services.whatsapp.schemas import OutgoingReplyButton


class SpacedRepetitionDispatcher:
    """Scans for due reviews and dispatches proactive revision nudges compliant with Meta rules."""

    async def dispatch_due_nudges(self, session: AsyncSession) -> int:
        """
        Finds topics due for review, verifies quiet hours and 24-hr session windows,
        and dispatches personalized WhatsApp revision alerts.
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Fetch due reviews for active students
        stmt = (
            select(TopicMastery, Student, SyllabusNode)
            .join(Student, TopicMastery.student_id == Student.id)
            .join(SyllabusNode, TopicMastery.topic_id == SyllabusNode.id)
            .where(
                and_(
                    Student.is_active == True,
                    TopicMastery.next_review <= now,
                )
            )
        )
        res = await session.execute(stmt)
        due_items = res.all()

        nudges_dispatched = 0

        for mastery, student, topic in due_items:
            # 2. Check Quiet Hours
            if compliance_service.is_in_quiet_hours(student):
                continue

            # 3. Check Frequency Cap (Max 1 proactive nudge per day)
            is_cap_allowed = await compliance_service.check_daily_frequency_cap(
                student_id=student.id,
                session=session,
            )
            if not is_cap_allowed:
                continue

            # 4. Check 24-Hour WhatsApp Customer Care Window
            is_24h_active = await compliance_service.is_within_24h_window(
                student_id=student.id,
                session=session,
            )

            student_name = student.name or "there"
            if is_24h_active:
                # Inside 24h: Full interactive message with action buttons
                nudge_text = (
                    f"👋 Hi {student_name}! FSRS spaced repetition indicates it's time for a "
                    f"quick 2-minute review of *{topic.title}* to keep your retention strong (90%+).\n\n"
                    "Take a quick practice question to lock it into your memory!"
                )
                buttons = [
                    OutgoingReplyButton(id=f"quiz_this_topic", title="⚡ Quick Quiz"),
                    OutgoingReplyButton(id=f"start_first_topic", title="📅 Study Plan"),
                ]
                outbound_results = [
                    await whatsapp_client.send_interactive_buttons(
                        recipient_phone=student.phone_number,
                        body_text=nudge_text,
                        buttons=buttons,
                    )
                ]
            else:
                # Outside 24h: Meta template message
                template_text = (
                    f"Reminder for {student_name}: You have a scheduled study review for {topic.title}. "
                    "Reply to this message to resume your learning session."
                )
                outbound_results = await whatsapp_client.send_text_message(
                    recipient_phone=student.phone_number,
                    text=template_text,
                )

            # 5. Log outbound proactive nudge to guarantee frequency cap tracking
            for out_res in outbound_results:
                sent_wamid = (
                    out_res.get("messages", [{}])[0].get("id")
                    if out_res.get("messages")
                    else f"nudge-{uuid.uuid4().hex[:12]}"
                )
                nudge_log = WhatsAppMessageLog(
                    wamid=sent_wamid,
                    student_id=student.id,
                    phone_number=student.phone_number,
                    direction="OUTBOUND",
                    message_type="proactive_nudge",
                    raw_payload=out_res,
                    status="SENT",
                )
                session.add(nudge_log)

            nudges_dispatched += 1

        if nudges_dispatched > 0:
            await session.commit()
            logger.info("Dispatched proactive spaced repetition nudges", count=nudges_dispatched)

        return nudges_dispatched


nudge_dispatcher = SpacedRepetitionDispatcher()
