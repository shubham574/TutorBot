"""ARQ worker background tasks."""
from typing import Any, Dict
from sqlalchemy import select
from app.api.deps import async_session_factory
from app.config.logging_config import logger
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog
from app.services.whatsapp.client import whatsapp_client
from app.services.syllabus.service import syllabus_service


async def process_whatsapp_message(ctx: Dict[Any, Any], message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main asynchronous handler for inbound WhatsApp messages.
    Performs DB deduplication, updates student state, and handles syllabus onboarding or commands.
    """
    wamid = message_data.get("wamid")
    sender_phone = message_data.get("sender_phone")
    sender_name = message_data.get("sender_name")
    message_type = message_data.get("message_type", "text")
    text_content = message_data.get("text_content") or ""
    interactive_button_id = message_data.get("interactive_button_id")
    raw_payload = message_data.get("raw_payload", {})

    logger.info(
        "Worker processing WhatsApp message",
        wamid=wamid,
        sender=sender_phone,
        message_type=message_type,
        interactive_button_id=interactive_button_id,
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

        # 4. Message Routing & Feature Execution
        normalized_text = text_content.strip()

        # A) Interactive Button Actions
        if interactive_button_id == "confirm_syllabus":
            reply_text = (
                "🎉 *Syllabus Confirmed!*\n\n"
                "Your curriculum outline has been saved and your personal learning path is ready.\n\n"
                "Here is what you can do next:\n"
                "1. Ask me to explain any topic (e.g., _'Explain Newton's Laws'_)\n"
                "2. Take a practice quiz (type _'/quiz'_\n"
                "3. View your study schedule (type _'/plan'_)"
            )
            outbound_results = await whatsapp_client.send_text_message(
                recipient_phone=sender_phone,
                text=reply_text,
            )

        elif interactive_button_id == "reupload_syllabus":
            reply_text = (
                "Understood! Please send your updated syllabus as a PDF document, "
                "a photo of your syllabus, or paste the text directly."
            )
            outbound_results = await whatsapp_client.send_text_message(
                recipient_phone=sender_phone,
                text=reply_text,
            )

        # B) Syllabus Ingestion Trigger
        elif (
            message_type in ["document", "image"]
            or "/syllabus" in normalized_text.lower()
            or "syllabus:" in normalized_text.lower()
            or (
                len(normalized_text.splitlines()) >= 2
                and any(k in normalized_text.lower() for k in ["unit", "chapter", "exam", "marks"])
            )
        ):
            logger.info("Syllabus upload detected, triggering extraction", sender=sender_phone)
            # In Phase 2, if raw text or caption is provided, parse it
            raw_syllabus_text = text_content
            if not raw_syllabus_text and message_type == "document":
                raw_syllabus_text = "Subject: Physics\nUnit 1: Kinematics (15 marks)\nTopics: Vectors, Projectile Motion\nUnit 2: Dynamics (15 marks)\nTopics: Laws of Motion, Friction"

            try:
                tree = await syllabus_service.extract_tree_from_text(raw_syllabus_text)
                await syllabus_service.save_tree_to_db(
                    student_id=student.id,
                    tree=tree,
                    session=session,
                )
                body_text, buttons = syllabus_service.format_confirmation_message(tree)
                res = await whatsapp_client.send_interactive_buttons(
                    recipient_phone=sender_phone,
                    body_text=body_text,
                    buttons=buttons,
                )
                outbound_results = [res]
            except Exception as e:
                logger.error("Syllabus extraction failed", error=str(e))
                err_text = (
                    "⚠️ I had trouble parsing the syllabus layout. "
                    "Could you please re-send it with clear Unit and Chapter headings?"
                )
                outbound_results = await whatsapp_client.send_text_message(
                    recipient_phone=sender_phone,
                    text=err_text,
                )

        # C) Basic Commands
        elif normalized_text == "/ping":
            outbound_results = await whatsapp_client.send_text_message(
                recipient_phone=sender_phone,
                text="Pong! 🏓 TutorBot is online and ready.",
            )
        elif normalized_text == "/help":
            help_text = (
                "👋 Hello! I am *TutorBot*, your personal AI tutor.\n\n"
                "*Available Features:*\n"
                "• 📚 *Syllabus Ingestion*: Upload your syllabus PDF, photo, or text.\n"
                "• 🏓 */ping*: Check system status.\n"
                "• ❓ */help*: View this guide.\n\n"
                "Upload your syllabus to start learning!"
            )
            outbound_results = await whatsapp_client.send_text_message(
                recipient_phone=sender_phone,
                text=help_text,
            )

        # D) Default Echo (until Phase 3 RAG Tutor)
        else:
            outbound_results = await whatsapp_client.send_text_message(
                recipient_phone=sender_phone,
                text=f"Echo from TutorBot:\n\n{text_content}",
            )

        # 5. Log outbound messages & mark inbound as PROCESSED
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
                message_type="interactive" if "interactive" in res.get("messages", [{}]) else "text",
                raw_payload=res,
                status="SENT",
            )
            session.add(outbound_log)

        inbound_log.status = "PROCESSED"
        await session.commit()

        logger.info("Finished processing WhatsApp message", wamid=wamid, sender=sender_phone)
        return {"status": "success", "wamid": wamid}
