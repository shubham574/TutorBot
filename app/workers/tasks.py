"""ARQ worker background tasks."""
from typing import Any, Dict
from sqlalchemy import select
from app.api.deps import async_session_factory
from app.config.logging_config import logger
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog
from app.services.whatsapp.client import whatsapp_client


async def process_whatsapp_message(ctx: Dict[Any, Any], message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main asynchronous handler for inbound WhatsApp messages.
    Performs DB deduplication, updates student state, and executes the Phase 1 Echo response.
    """
    wamid = message_data.get("wamid")
    sender_phone = message_data.get("sender_phone")
    sender_name = message_data.get("sender_name")
    message_type = message_data.get("message_type", "text")
    text_content = message_data.get("text_content") or ""
    raw_payload = message_data.get("raw_payload", {})

    logger.info(
        "Worker processing WhatsApp message",
        wamid=wamid,
        sender=sender_phone,
        message_type=message_type,
    )

    async with async_session_factory() as session:
        # 1. DB Deduplication check
        stmt = select(WhatsAppMessageLog).where(WhatsAppMessageLog.wamid == wamid)
        result = await session.execute(stmt)
        existing_log = result.scalar_one_or_none()

        if existing_log and existing_log.status == "PROCESSED":
            logger.info("Message already processed in DB, skipping", wamid=wamid)
            return {"status": "duplicate_skipped", "wamid": wamid}

        # 2. Get or create Student
        student_stmt = select(Student).where(Student.phone_number == sender_phone)
        student_res = await session.execute(student_stmt)
        student = student_res.scalar_one_or_none()

        if not student:
            student = Student(
                phone_number=sender_phone,
                name=sender_name,
            )
            session.add(student)
            await session.flush()
            logger.info("Created new student profile", sender=sender_phone, student_id=str(student.id))

        # 3. Create or update inbound message log
        if not existing_log:
            inbound_log = WhatsAppMessageLog(
                wamid=wamid,
                student_id=student.id,
                phone_number=sender_phone,
                direction="INBOUND",
                message_type=message_type,
                raw_payload=raw_payload,
                status="PROCESSING",
            )
            session.add(inbound_log)
        else:
            inbound_log = existing_log
            inbound_log.status = "PROCESSING"

        await session.commit()

        # 4. Phase 1 Response Generation (Echo Bot + basic system commands)
        normalized_text = text_content.strip()
        if normalized_text == "/ping":
            reply_text = "Pong! 🏓 TutorBot is online and ready."
        elif normalized_text == "/help":
            reply_text = (
                "👋 Hello! I am *TutorBot*, your personal AI tutor.\n\n"
                "*Phase 1 Operational:*\n"
                "• Webhook signature verification: Active ✅\n"
                "• Message deduplication: Active ✅\n"
                "• Async Redis queue: Active ✅\n\n"
                "Send any message and I will echo it back to verify connectivity!"
            )
        elif message_type != "text":
            reply_text = f"Received {message_type} message! Document and media processing will be enabled in Phase 2 (Syllabus Ingestion)."
        else:
            reply_text = f"Echo from TutorBot:\n\n{text_content}"

        # 5. Outbound WhatsApp delivery (honors DRY_RUN)
        outbound_results = await whatsapp_client.send_text_message(
            recipient_phone=sender_phone,
            text=reply_text,
        )

        # 6. Log outbound messages & mark inbound as PROCESSED
        for res in outbound_results:
            sent_wamid = (
                res.get("messages", [{}])[0].get("id")
                if res.get("messages")
                else f"outbound-{wamid}"
            )
            outbound_log = WhatsAppMessageLog(
                wamid=sent_wamid,
                student_id=student.id,
                phone_number=sender_phone,
                direction="OUTBOUND",
                message_type="text",
                raw_payload=res,
                status="SENT",
            )
            session.add(outbound_log)

        inbound_log.status = "PROCESSED"
        await session.commit()

        logger.info(
            "Finished processing WhatsApp message",
            wamid=wamid,
            sender=sender_phone,
            reply_length=len(reply_text),
        )

        return {"status": "success", "wamid": wamid}
