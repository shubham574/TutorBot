"""Syllabus Ingestion Service: Tree extraction, DB persistence, and WhatsApp formatting."""
import datetime
import uuid
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.syllabus import SyllabusNode
from app.services.llm.nvidia import llm_client
from app.services.syllabus.schemas import SyllabusExtractionResult
from app.services.whatsapp.schemas import OutgoingReplyButton


class SyllabusIngestionService:
    """Handles extracting, saving, and formatting structured student syllabi."""

    async def extract_tree_from_text(self, text_content: str) -> SyllabusExtractionResult:
        """
        Uses LLM to parse raw syllabus text into a structured SyllabusExtractionResult tree.
        """
        prompt = (
            "Analyze the following academic syllabus text and extract the complete curriculum tree.\n\n"
            f"--- SYLLABUS CONTENT ---\n{text_content[:8000]}\n--- END CONTENT ---\n\n"
            "Requirements:\n"
            "1. Identify the subject name.\n"
            "2. Identify the target exam or grade if mentioned.\n"
            "3. Extract all units/chapters in order.\n"
            "4. Extract marks weightage if provided (as a float or null).\n"
            "5. Extract topics and subtopics for each unit.\n"
            "6. Estimate study minutes (default 30-45 mins per topic).\n"
            "7. Return the data strictly conforming to the requested JSON schema."
        )

        result: SyllabusExtractionResult = await llm_client.extract_structured(
            prompt=prompt,
            schema_class=SyllabusExtractionResult,
        )
        return result

    async def save_tree_to_db(
        self,
        student_id: uuid.UUID,
        tree: SyllabusExtractionResult,
        session: AsyncSession,
    ) -> SyllabusNode:
        """
        Recursively persists the structured syllabus tree into PostgreSQL syllabus_nodes.
        """
        # Parse exam date if present
        parsed_exam_date = None
        if tree.exam_date:
            try:
                parsed_exam_date = datetime.date.fromisoformat(tree.exam_date)
            except ValueError:
                pass

        # 1. Create Root Subject Node
        root_node = SyllabusNode(
            student_id=student_id,
            parent_id=None,
            node_type="subject",
            title=tree.subject,
            order_index=0,
            exam_date=parsed_exam_date,
            marks_weightage=100.0,
        )
        session.add(root_node)
        await session.flush()  # Generate root_node.id

        total_nodes = 1

        # 2. Iterate Units
        for u_idx, unit in enumerate(tree.units):
            unit_node = SyllabusNode(
                student_id=student_id,
                parent_id=root_node.id,
                node_type="unit",
                title=unit.title,
                order_index=u_idx,
                marks_weightage=unit.marks_weightage or 0.0,
            )
            session.add(unit_node)
            await session.flush()
            total_nodes += 1

            # 3. Iterate Topics
            for t_idx, topic in enumerate(unit.topics):
                topic_node = SyllabusNode(
                    student_id=student_id,
                    parent_id=unit_node.id,
                    node_type="topic",
                    title=topic.title,
                    order_index=t_idx,
                    estimated_minutes=topic.estimated_minutes,
                )
                session.add(topic_node)
                await session.flush()
                total_nodes += 1

                # 4. Iterate Subtopics
                for s_idx, subtopic in enumerate(topic.subtopics):
                    subtopic_node = SyllabusNode(
                        student_id=student_id,
                        parent_id=topic_node.id,
                        node_type="subtopic",
                        title=subtopic.title,
                        order_index=s_idx,
                        estimated_minutes=subtopic.estimated_minutes,
                    )
                    session.add(subtopic_node)
                    total_nodes += 1

        await session.flush()
        logger.info(
            "Persisted syllabus tree into database",
            student_id=str(student_id),
            subject=tree.subject,
            total_nodes=total_nodes,
        )
        return root_node

    def format_confirmation_message(
        self, tree: SyllabusExtractionResult
    ) -> Tuple[str, list[OutgoingReplyButton]]:
        """
        Builds a readable WhatsApp summary with confirmation reply buttons.
        """
        lines = [
            f"📚 *Syllabus Ingested: {tree.subject}*",
        ]
        if tree.target_exam:
            lines.append(f"🎯 *Target Exam:* {tree.target_exam}")
        if tree.exam_date:
            lines.append(f"📅 *Exam Date:* {tree.exam_date}")

        lines.append("\n*Curriculum Outline:*")
        total_topics = 0
        total_minutes = 0

        for idx, unit in enumerate(tree.units[:8], 1):  # Show up to first 8 units
            topic_count = len(unit.topics)
            total_topics += topic_count
            marks_str = f" ({unit.marks_weightage:.0f} marks)" if unit.marks_weightage else ""
            lines.append(f"{idx}. *{unit.title}*{marks_str} • {topic_count} topics")

            for topic in unit.topics:
                total_minutes += topic.estimated_minutes

        if len(tree.units) > 8:
            lines.append(f"...and {len(tree.units) - 8} more units.")

        hours = round(total_minutes / 60, 1)
        lines.append(f"\n📊 *Total Units:* {len(tree.units)} | *Topics:* {total_topics} | *Est. Study Time:* ~{hours} hrs")
        lines.append("\nPlease review and confirm if this syllabus looks accurate!")

        message_body = "\n".join(lines)

        buttons = [
            OutgoingReplyButton(id="confirm_syllabus", title="✅ Confirm Outline"),
            OutgoingReplyButton(id="reupload_syllabus", title="🔄 Re-upload"),
        ]

        return message_body, buttons


syllabus_service = SyllabusIngestionService()
