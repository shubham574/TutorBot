"""ARQ worker background tasks."""
import uuid
from typing import Any, Dict
from sqlalchemy import select
from app.api.deps import async_session_factory
from app.config.logging_config import logger
from app.models.student import Student
from app.models.message_log import WhatsAppMessageLog
from app.models.syllabus import SyllabusNode
from app.services.whatsapp.client import whatsapp_client
from app.services.syllabus.service import syllabus_service
from app.rag.tutor import tutor_agent
from app.services.quiz.service import quiz_service
from app.services.exam.service import exam_service
from app.services.grading.service import grading_service
from app.services.whatsapp.schemas import OutgoingReplyButton


async def process_whatsapp_message(ctx: Dict[Any, Any], message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main asynchronous handler for inbound WhatsApp messages.
    Handles syllabus onboarding, RAG questions, and interactive quizzes.
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

        # A) Quiz Answer Submission via Button
        if interactive_button_id and interactive_button_id.startswith("quiz_ans_"):
            parts = interactive_button_id.split("_")
            # format: quiz_ans_{question_id}_{opt_key}
            q_id_str = parts[2]
            selected_option = parts[3]
            feedback_text, next_buttons = await quiz_service.submit_answer(
                student_id=student.id,
                question_id=uuid.UUID(q_id_str),
                selected_option=selected_option,
                session=session,
            )
            res = await whatsapp_client.send_interactive_buttons(
                recipient_phone=sender_phone,
                body_text=feedback_text,
                buttons=next_buttons,
            )
            outbound_results = [res]

        # B) Quiz Generation Trigger (/quiz or tapping [Quiz This Topic])
        elif (
            interactive_button_id in ["quiz_this_topic", "quiz_next_question"]
            or normalized_text.lower() == "/quiz"
        ):
            # Find a topic from the student's syllabus
            topic_stmt = select(SyllabusNode).where(
                SyllabusNode.student_id == student.id,
                SyllabusNode.node_type == "topic",
            ).limit(1)
            topic_res = await session.execute(topic_stmt)
            topic = topic_res.scalar_one_or_none()

            if not topic:
                reply_text = (
                    "📋 You haven't uploaded your syllabus yet!\n\n"
                    "Please upload your syllabus PDF, photo, or text first so I can generate "
                    "tailored practice questions on your exact curriculum."
                )
                outbound_results = await whatsapp_client.send_text_message(
                    recipient_phone=sender_phone,
                    text=reply_text,
                )
            else:
                question = await quiz_service.generate_and_verify_question(
                    topic_id=topic.id,
                    session=session,
                )
                if question:
                    body, buttons = quiz_service.format_question_for_whatsapp(
                        question=question,
                        topic_title=topic.title,
                    )
                    res = await whatsapp_client.send_interactive_buttons(
                        recipient_phone=sender_phone,
                        body_text=body,
                        buttons=buttons,
                    )
                    outbound_results = [res]
                else:
                    reply_text = (
                        f"⚠️ I couldn't verify a question on *{topic.title}* right now. "
                        "Please ask me to explain the topic or try another chapter!"
                    )
                    outbound_results = await whatsapp_client.send_text_message(
                        recipient_phone=sender_phone,
                        text=reply_text,
                    )

        # C) Syllabus Confirmation Buttons
        elif interactive_button_id == "confirm_syllabus":
            reply_text = (
                "🎉 *Syllabus Confirmed!*\n\n"
                "Your curriculum outline has been saved and your personal learning path is ready.\n\n"
                "Here is what you can do next:\n"
                "1. Ask me to explain any topic (e.g., _'Explain Newton's Laws'_)\n"
                "2. Take a practice quiz (type _'/quiz'_)\n"
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

        # D) Syllabus Ingestion Trigger
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

        # E) Phase 5: Sample Examination Paper Generation
        elif normalized_text.lower() in ["/exam", "/paper", "generate exam", "sample paper"]:
            logger.info("Generating exam paper blueprint and PDF", sender=sender_phone)
            blueprint, pdf_bytes = await exam_service.generate_exam_paper(
                student_id=student.id,
                session=session,
            )
            exam_summary = (
                f"📄 *{blueprint.title}*\n"
                f"🎯 *Exam:* {blueprint.target_exam} | ⏱️ *Duration:* {blueprint.duration_minutes // 60} hrs\n"
                f"📊 *Total Marks:* {int(blueprint.total_marks)}\n\n"
                "*Structure:*\n"
                "• *Section A:* Multiple Choice (1 Mark each)\n"
                "• *Section B:* Short Answer (3 Marks each)\n"
                "• *Section C:* Numerical Problem (5 Marks)\n\n"
                "Your examination paper PDF has been generated! Solve the questions and type "
                "'/grade [question] [your answer]' or upload a photo of your handwritten sheet to receive instant rubric evaluation."
            )
            exam_buttons = [
                OutgoingReplyButton(id="retest_concept", title="📝 Start Exam"),
                OutgoingReplyButton(id="quiz_this_topic", title="⚡ Quick Quiz"),
            ]
            res = await whatsapp_client.send_interactive_buttons(
                recipient_phone=sender_phone,
                body_text=exam_summary,
                buttons=exam_buttons,
            )
            outbound_results = [res]

        # F) Phase 5: Subjective Answer Grading
        elif normalized_text.lower().startswith("/grade"):
            logger.info("Grading subjective student submission", sender=sender_phone)
            # Format: /grade [Question] --- [Student Answer] or general answer text
            answer_payload = normalized_text[6:].strip()
            if "---" in answer_payload:
                q_text, a_text = answer_payload.split("---", 1)
            else:
                q_text = "Physics Numerical Problem"
                a_text = answer_payload

            report = await grading_service.grade_text_answer(
                question_text=q_text.strip(),
                student_answer=a_text.strip(),
                expected_solution="Work W = F*d = (1/2)*m*v^2 = 100 Joules",
                max_marks=5.0,
            )
            grading_body, grading_buttons = grading_service.format_grading_for_whatsapp(report)
            res = await whatsapp_client.send_interactive_buttons(
                recipient_phone=sender_phone,
                body_text=grading_body,
                buttons=grading_buttons,
            )
            outbound_results = [res]

        # G) Basic System Commands
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
                "• 💡 *Ask Questions*: Ask me to explain any topic.\n"
                "• 📝 *Interactive Quizzes*: Type '/quiz' to test understanding.\n"
                "• 📄 *Exam Papers*: Type '/exam' to generate printable practice papers.\n"
                "• 📊 *Grading*: Type '/grade [answer]' or upload handwritten work for rubric feedback.\n"
                "• 📈 *FSRS Mastery*: Tracks memory retention automatically.\n"
                "• 🏓 */ping*: Check system status."
            )
            outbound_results = await whatsapp_client.send_text_message(
                recipient_phone=sender_phone,
                text=help_text,
            )

        # F) RAG Tutor Agent (Grounded, General Knowledge, Decline/Clarify)
        else:
            logger.info("Routing query to Tutor Agent", query=text_content[:60], sender=sender_phone)
            answer_text, buttons, mode = await tutor_agent.answer_question(
                question=text_content,
                student_id=student.id,
                session=session,
            )
            res = await whatsapp_client.send_interactive_buttons(
                recipient_phone=sender_phone,
                body_text=answer_text,
                buttons=buttons,
            )
            outbound_results = [res]

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
