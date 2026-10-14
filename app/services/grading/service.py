"""Subjective answer grading with rubric evaluation, SymPy math tool, and Vision OCR."""
import json
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from app.config.logging_config import logger
from app.services.llm.nvidia import llm_client
from app.tools.math_solver import verify_mathematical_equivalence
from app.services.whatsapp.schemas import OutgoingReplyButton


class StepScore(BaseModel):
    step_name: str
    max_marks: float
    marks_awarded: float
    feedback: str


class GradingReport(BaseModel):
    max_marks: float
    total_awarded: float
    percentage: float
    step_breakdown: List[StepScore]
    strengths: List[str]
    areas_for_improvement: List[str]
    sympy_verified: bool = False
    overall_summary: str


class SubjectiveGradingService:
    """Grades subjective answers, handwritten photos, and verifies mathematical equivalence."""

    async def grade_text_answer(
        self,
        question_text: str,
        student_answer: str,
        expected_solution: Optional[str] = None,
        max_marks: float = 5.0,
    ) -> GradingReport:
        """
        Grades student's written response using a 3-step rubric and SymPy math checking.
        """
        sympy_match = False
        sympy_note = ""

        # Run SymPy math tool if both student answer and expected solution contain numbers/equations
        if expected_solution and any(char.isdigit() for char in student_answer):
            sympy_match, sympy_note = verify_mathematical_equivalence(
                expected_expr_str=expected_solution,
                student_expr_str=student_answer,
            )

        rubric_prompt = (
            "You are an expert academic examiner. Grade the student's subjective answer based on this strict 3-step rubric:\n"
            f"Total Marks: {max_marks}\n"
            "- Step 1: Core Concepts & Formula Identified (40% of marks)\n"
            "- Step 2: Derivation / Reasoning / Calculation Steps (40% of marks)\n"
            "- Step 3: Final Answer & Appropriate Units (20% of marks)\n\n"
            f"Question:\n{question_text}\n\n"
            f"Student Answer:\n{student_answer}\n\n"
        )
        if expected_solution:
            rubric_prompt += f"Reference Solution:\n{expected_solution}\n"
        if sympy_note:
            rubric_prompt += f"SymPy Math Solver Verification: {sympy_note}\n"

        rubric_prompt += "\nEvaluate each step, allocate marks, provide feedback, and return ONLY JSON matching the schema."

        report: GradingReport = await llm_client.extract_structured(
            prompt=rubric_prompt,
            schema_class=GradingReport,
        )
        report.sympy_verified = sympy_match
        return report

    async def grade_handwritten_photo(
        self,
        question_text: str,
        image_bytes: bytes,
        expected_solution: Optional[str] = None,
        max_marks: float = 5.0,
        mime_type: str = "image/jpeg",
    ) -> Tuple[str, GradingReport]:
        """
        Transcribes handwritten student work via Vision LLM and grades against rubric.
        """
        transcription_prompt = (
            "Transcribe this student's handwritten answer sheet line-by-line. "
            "Preserve all equations, intermediate calculation steps, and final boxed answer."
        )

        transcribed_text = await llm_client.extract_from_image(
            image_bytes=image_bytes,
            prompt=transcription_prompt,
            mime_type=mime_type,
        )
        logger.info("Transcribed handwritten answer photo", char_count=len(transcribed_text))

        report = await self.grade_text_answer(
            question_text=question_text,
            student_answer=transcribed_text,
            expected_solution=expected_solution,
            max_marks=max_marks,
        )
        return transcribed_text, report

    def format_grading_for_whatsapp(
        self,
        report: GradingReport,
        question_text: Optional[str] = None,
    ) -> Tuple[str, List[OutgoingReplyButton]]:
        """Formats the rubric evaluation into a clear WhatsApp report."""
        lines = [
            f"📊 *Assessment & Grading Report*",
            f"🏆 *Score Awarded:* {report.total_awarded:.1f} / {report.max_marks:.1f} ({report.percentage:.0f}%)",
        ]
        if report.sympy_verified:
            lines.append("🧮 *Math Check:* SymPy Verified Symbolic Equivalence ✅")

        lines.append("\n*Rubric Step Breakdown:*")
        for step in report.step_breakdown:
            lines.append(f"• *{step.step_name}:* {step.marks_awarded:.1f}/{step.max_marks:.1f} Marks")
            lines.append(f"  _{step.feedback}_")

        if report.strengths:
            lines.append("\n💪 *Key Strengths:*")
            for s in report.strengths[:3]:
                lines.append(f"• {s}")

        if report.areas_for_improvement:
            lines.append("\n🎯 *Areas for Improvement:*")
            for a in report.areas_for_improvement[:3]:
                lines.append(f"• {a}")

        lines.append(f"\n📝 *Overall Feedback:*\n{report.overall_summary}")

        buttons = [
            OutgoingReplyButton(id="retest_concept", title="🔄 Retry Question"),
            OutgoingReplyButton(id="quiz_this_topic", title="📝 Take a Quiz"),
        ]

        return "\n".join(lines), buttons


grading_service = SubjectiveGradingService()
