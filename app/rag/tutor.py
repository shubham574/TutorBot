"""Tutor Agent implementing the 3 answer modes with page citations and guardrails."""
import uuid
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.rag.retriever import retriever, AnswerMode, RetrievalResult
from app.services.llm.nvidia import llm_client
from app.services.whatsapp.schemas import OutgoingReplyButton


GENERAL_KNOWLEDGE_DISCLAIMER = (
    "ℹ️ *Note:* This explanation is based on general curriculum knowledge, "
    "as this specific topic was not directly found in your uploaded study notes."
)


class CapabilityManifest:
    """Machine-readable manifest of TutorBot supported intents, tools, and safety boundaries."""
    SUPPORTED_INTENTS = [
        "explain_topic",
        "generate_quiz",
        "generate_exam_paper",
        "grade_subjective_answer",
        "create_study_plan",
        "show_progress_dashboard",
        "syllabus_ingestion",
    ]
    SUPPORTED_TOOLS = [
        "hybrid_retriever",
        "sympy_math_solver",
        "llama_vision_grader",
        "reportlab_exam_pdf_generator",
        "fsrs_spaced_repetition",
    ]
    UNSUPPORTED_INTENTS = [
        "medical_advice",
        "legal_advice",
        "exam_score_guarantees",
        "academic_dishonesty_or_hacking",
        "non_educational_tasks",
    ]

    @classmethod
    def is_intent_supported(cls, intent: str) -> bool:
        return intent in cls.SUPPORTED_INTENTS


class TutorAgent:
    """Agent that synthesizes answers across the 3 strict answer modes."""

    async def answer_question(
        self,
        question: str,
        student_id: Optional[uuid.UUID],
        session: AsyncSession,
        subject_hint: Optional[str] = None,
        topic_id_hint: Optional[uuid.UUID] = None,
    ) -> Tuple[str, List[OutgoingReplyButton], AnswerMode]:
        """
        Executes hybrid retrieval, decides the answer mode, and generates the tutor response.
        """
        retrieval_res: RetrievalResult = await retriever.retrieve(
            query=question,
            student_id=student_id,
            session=session,
            subject_filter=subject_hint,
            topic_id_filter=topic_id_hint,
        )

        mode = retrieval_res.mode

        # ---------------------------------------------------------------------
        # Mode 1: GROUNDED (Cited from student / curriculum material)
        # ---------------------------------------------------------------------
        if mode == AnswerMode.GROUNDED:
            context_blocks = []
            citations = []
            for c in retrieval_res.chunks:
                context_blocks.append(
                    f"[{c.source_title}, Page {c.page_number}]:\n{c.content}"
                )
                cite_str = f"• {c.source_title} (Page {c.page_number})"
                if cite_str not in citations:
                    citations.append(cite_str)

            context_str = "\n\n".join(context_blocks)
            citations_footer = "\n\n📖 *Sources & Page Citations:*\n" + "\n".join(citations)

            prompt = (
                "You are an encouraging, expert academic tutor for students.\n"
                "Answer the student's question clearly and step-by-step using ONLY the provided study material.\n"
                "Explain core concepts, formulas, and examples clearly. Do not use raw LaTeX math ($ or $$); "
                "use plain math symbols like x², √x, (a/b).\n\n"
                f"--- STUDY MATERIAL ---\n{context_str}\n--- END MATERIAL ---\n\n"
                f"Student Question: {question}"
            )

            explanation = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=900,
                temperature=0.2,
            )

            full_reply = explanation.strip() + citations_footer

            buttons = [
                OutgoingReplyButton(id="quiz_this_topic", title="📝 Quiz This Topic"),
                OutgoingReplyButton(id="more_examples", title="💡 More Examples"),
            ]
            return full_reply, buttons, AnswerMode.GROUNDED

        # ---------------------------------------------------------------------
        # Mode 2: GENERAL_KNOWLEDGE (Not found in material, clearly labeled)
        # ---------------------------------------------------------------------
        elif mode == AnswerMode.GENERAL_KNOWLEDGE:
            prompt = (
                "You are an encouraging, expert academic tutor.\n"
                "The student asked an academic question, but it was not found in their specific uploaded notes. "
                "Provide a clear, accurate educational explanation from general curriculum knowledge.\n"
                "Do not use raw LaTeX math ($ or $$); use plain text notations like x², √x, (a/b).\n\n"
                f"Student Question: {question}"
            )

            explanation = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.2,
            )

            disclaimer = (
                "\n\nℹ️ *Note:* This explanation is based on general curriculum knowledge, "
                "as this specific topic was not directly found in your uploaded study notes."
            )
            full_reply = explanation.strip() + disclaimer

            buttons = [
                OutgoingReplyButton(id="reupload_syllabus", title="📤 Upload Notes"),
                OutgoingReplyButton(id="quiz_this_topic", title="📝 Take a Quiz"),
            ]
            return full_reply, buttons, AnswerMode.GENERAL_KNOWLEDGE

        # ---------------------------------------------------------------------
        # Mode 3: DECLINE_OR_CLARIFY (Low confidence / out of scope)
        # ---------------------------------------------------------------------
        else:
            decline_message = (
                "🤔 I couldn't find enough reliable material in your uploaded syllabus notes "
                f"to answer *'{question}'* accurately, and I want to avoid guessing.\n\n"
                "*How would you like to proceed?*\n"
                "1. Send me the PDF or photo of the chapter notes.\n"
                "2. Try rephrasing your question with the specific chapter name."
            )

            buttons = [
                OutgoingReplyButton(id="reupload_syllabus", title="📤 Upload Notes"),
                OutgoingReplyButton(id="help_menu", title="❓ Help Menu"),
            ]
            return decline_message, buttons, AnswerMode.DECLINE_OR_CLARIFY


tutor_agent = TutorAgent()
