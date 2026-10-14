"""Exam Generation Service following curriculum blueprints and PDF export."""
import uuid
from typing import Tuple, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.syllabus import SyllabusNode
from app.services.exam.schemas import ExamBlueprint, ExamSection, ExamQuestion
from app.services.exam.pdf_generator import exam_pdf_generator


class ExamService:
    """Generates standardized examination papers mimicking curriculum blueprint."""

    async def generate_exam_paper(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
        subject_name: Optional[str] = None,
    ) -> Tuple[ExamBlueprint, bytes]:
        """
        Creates an ExamBlueprint from student syllabus nodes and exports the PDF.
        """
        # Fetch student's syllabus nodes
        stmt = select(SyllabusNode).where(SyllabusNode.student_id == student_id)
        res = await session.execute(stmt)
        nodes = res.scalars().all()

        subject_node = next((n for n in nodes if n.node_type == "subject"), None)
        subject = subject_name or (subject_node.title if subject_node else "General Science")
        topics = [n.title for n in nodes if n.node_type == "topic"]
        if not topics:
            topics = ["Kinematics & Dynamics", "Thermodynamics", "Optics & Waves"]

        # Construct Blueprint adhering to Section blueprint
        section_a_questions = [
            ExamQuestion(
                question_num=1,
                question_text=f"Which of the following principles governs energy conservation in {topics[0]}?",
                question_type="mcq",
                marks=1.0,
                topic_name=topics[0],
            ),
            ExamQuestion(
                question_num=2,
                question_text=f"Define the SI base unit associated with {topics[1 % len(topics)]}.",
                question_type="mcq",
                marks=1.0,
                topic_name=topics[1 % len(topics)],
            ),
            ExamQuestion(
                question_num=3,
                question_text="State whether work done by a conservative force along a closed path is zero.",
                question_type="mcq",
                marks=1.0,
                topic_name=topics[0],
            ),
        ]

        section_b_questions = [
            ExamQuestion(
                question_num=4,
                question_text=f"Derive the relationship between force and rate of change of momentum for {topics[0]}.",
                question_type="short_answer",
                marks=3.0,
                topic_name=topics[0],
            ),
            ExamQuestion(
                question_num=5,
                question_text=f"Explain two practical applications of {topics[-1]} in modern engineering.",
                question_type="short_answer",
                marks=3.0,
                topic_name=topics[-1],
            ),
        ]

        section_c_questions = [
            ExamQuestion(
                question_num=6,
                question_text=(
                    f"A body of mass 2 kg moving initially at 10 m/s experiences a constant retarding force. "
                    f"Calculate the total work done to bring the body to rest and find the stopping distance."
                ),
                question_type="numerical",
                marks=5.0,
                topic_name=topics[0],
            )
        ]

        sections = [
            ExamSection(
                section_name="Section A: Multiple Choice Questions",
                instructions="Questions 1 to 3 carry 1 mark each. Select the correct option.",
                marks_per_question=1.0,
                questions=section_a_questions,
            ),
            ExamSection(
                section_name="Section B: Short Answer Questions",
                instructions="Questions 4 and 5 carry 3 marks each. Answer in approximately 30-50 words.",
                marks_per_question=3.0,
                questions=section_b_questions,
            ),
            ExamSection(
                section_name="Section C: Long Answer / Numerical Problem",
                instructions="Question 6 carries 5 marks. Show complete step-by-step calculations with units.",
                marks_per_question=5.0,
                questions=section_c_questions,
            ),
        ]

        total_marks = sum(q.marks for s in sections for q in s.questions)

        blueprint = ExamBlueprint(
            title=f"{subject} Examination Paper",
            subject=subject,
            target_exam="Board Assessment Preparation",
            total_marks=total_marks,
            duration_minutes=90,
            sections=sections,
        )

        pdf_bytes = exam_pdf_generator.generate_exam_pdf(blueprint)
        return blueprint, pdf_bytes


exam_service = ExamService()
