"""Quiz Generation, Autonomous Verification, and FSRS Mastery Service."""
import uuid
from typing import Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.content import ContentChunk
from app.models.mastery import TopicMastery
from app.models.quiz import QuestionBank, Attempt
from app.models.syllabus import SyllabusNode
from app.services.fsrs.engine import fsrs_engine
from app.services.llm.nvidia import llm_client
from app.services.quiz.schemas import GeneratedMCQ, VerifierEvaluation
from app.services.whatsapp.schemas import OutgoingReplyButton


class QuizService:
    """Manages question generation, dual-pass verification, and answer grading."""

    async def generate_and_verify_question(
        self,
        topic_id: uuid.UUID,
        session: AsyncSession,
    ) -> Optional[QuestionBank]:
        """
        Generates an MCQ grounded in curriculum chunks and verifies it with a blind dual-pass solver.
        """
        # 1. Fetch topic node
        topic_stmt = select(SyllabusNode).where(SyllabusNode.id == topic_id)
        topic_res = await session.execute(topic_stmt)
        topic = topic_res.scalar_one_or_none()
        topic_title = topic.title if topic else "General Physics"

        # 2. Fetch context chunks
        chunk_stmt = select(ContentChunk).where(ContentChunk.topic_id == topic_id).limit(3)
        chunk_res = await session.execute(chunk_stmt)
        chunks = chunk_res.scalars().all()

        context_str = "\n".join(c.content for c in chunks) if chunks else f"Topic concept: {topic_title}"

        # 3. Generate Question Stem
        gen_prompt = (
            f"Generate a rigorous, high-quality multiple choice question on the topic: '{topic_title}'.\n"
            f"Base the question on this study material if available:\n{context_str[:2000]}\n\n"
            "Requirements:\n"
            "1. 3 distinct options labeled 'A', 'B', 'C' (one unambiguously correct, two plausible distractors).\n"
            "2. Design options to be concise (max 15 words per option).\n"
            "3. State the correct answer key ('A', 'B', or 'C').\n"
            "4. Provide a clear educational explanation of why the correct option is right.\n"
            "5. Return valid JSON matching the schema."
        )

        mcq: GeneratedMCQ = await llm_client.extract_structured(
            prompt=gen_prompt,
            schema_class=GeneratedMCQ,
        )

        # 4. Autonomous Verifier (Dual-Pass Blind Solver)
        # The verifier receives the question and options WITHOUT seeing the generator's correct_answer
        opts_str = "\n".join(f"{k}: {v}" for k, v in mcq.options.items())
        verifier_prompt = (
            "You are an independent academic examination verifier.\n"
            "Solve the following multiple choice question blind without any external hint:\n\n"
            f"Question: {mcq.question}\n"
            f"Options:\n{opts_str}\n\n"
            "Determine the correct option ('A', 'B', or 'C') and provide step-by-step reasoning."
        )

        verification: VerifierEvaluation = await llm_client.extract_structured(
            prompt=verifier_prompt,
            schema_class=VerifierEvaluation,
        )

        is_agreed = verification.solved_answer == mcq.correct_answer

        if not is_agreed:
            logger.warning(
                "Verifier disagreed with generated answer key, discarding question",
                generator_ans=mcq.correct_answer,
                verifier_ans=verification.solved_answer,
                verifier_confidence=verification.confidence,
            )
            # When verifier disagrees, discard this question to prevent sending misleading quizzes
            return None

        # 5. Persist Verified Question in DB
        question_record = QuestionBank(
            topic_id=topic_id,
            question_type="MCQ",
            question_text=mcq.question,
            options=mcq.options,
            correct_answer=mcq.correct_answer,
            explanation=mcq.explanation,
            difficulty=mcq.difficulty,
            verifier_score=verification.confidence,
        )
        session.add(question_record)
        await session.commit()
        await session.refresh(question_record)

        logger.info(
            "Question verified and persisted in question bank",
            question_id=str(question_record.id),
            correct_answer=mcq.correct_answer,
            verifier_score=verification.confidence,
        )
        return question_record

    def format_question_for_whatsapp(
        self,
        question: QuestionBank,
        topic_title: str = "Quiz",
    ) -> Tuple[str, List[OutgoingReplyButton]]:
        """
        Formats the MCQ stem, options, and WhatsApp reply buttons.
        """
        lines = [
            f"📝 *Quiz: {topic_title}*\n",
            question.question_text,
            "",
        ]

        buttons: List[OutgoingReplyButton] = []
        for opt_key, opt_text in sorted(question.options.items()):
            lines.append(f"*{opt_key})* {opt_text}")
            # Buttons have a strict 20-character limit on WhatsApp
            short_preview = opt_text[:14].strip()
            btn_title = f"{opt_key}: {short_preview}"[:20]
            buttons.append(
                OutgoingReplyButton(
                    id=f"quiz_ans_{question.id}_{opt_key}",
                    title=btn_title,
                )
            )

        message_body = "\n".join(lines)
        return message_body, buttons

    async def submit_answer(
        self,
        student_id: uuid.UUID,
        question_id: uuid.UUID,
        selected_option: str,
        session: AsyncSession,
    ) -> Tuple[str, List[OutgoingReplyButton]]:
        """
        Evaluates the student's answer, updates FSRS mastery, logs the attempt,
        and constructs educational feedback.
        """
        # Fetch question
        q_stmt = select(QuestionBank).where(QuestionBank.id == question_id)
        q_res = await session.execute(q_stmt)
        question = q_res.scalar_one_or_none()

        if not question:
            return "Question not found.", []

        clean_choice = selected_option.upper().strip()
        is_correct = clean_choice == question.correct_answer.upper().strip()

        # 1. Record Attempt
        attempt = Attempt(
            student_id=student_id,
            question_id=question_id,
            student_response=clean_choice,
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
            feedback=question.explanation,
        )
        session.add(attempt)

        # 2. Fetch or create TopicMastery record
        m_stmt = select(TopicMastery).where(
            TopicMastery.student_id == student_id,
            TopicMastery.topic_id == question.topic_id,
        )
        m_res = await session.execute(m_stmt)
        mastery = m_res.scalar_one_or_none()

        if not mastery:
            mastery = TopicMastery(
                student_id=student_id,
                topic_id=question.topic_id,
            )
            session.add(mastery)
            await session.flush()

        # 3. Calculate new FSRS state
        fsrs_state = fsrs_engine.calculate_next_state(
            current_stability=mastery.stability,
            current_difficulty=mastery.difficulty,
            reps=mastery.reps,
            lapses=mastery.lapses,
            is_correct=is_correct,
        )

        mastery.stability = fsrs_state.stability
        mastery.difficulty = fsrs_state.difficulty
        mastery.reps = fsrs_state.reps
        mastery.lapses = fsrs_state.lapses
        mastery.state = fsrs_state.state
        mastery.next_review = fsrs_state.next_review
        mastery.mastery_score = fsrs_state.mastery_score

        await session.commit()

        # 4. Construct Feedback
        mastery_percent = int(mastery.mastery_score * 100)
        if is_correct:
            feedback_lines = [
                "✅ *Correct! Excellent job!* 🎉\n",
                f"💡 *Explanation:*\n{question.explanation}\n",
                f"📈 *Topic Mastery:* {mastery_percent}%",
                f"📅 *Next Spaced Review:* in {round(mastery.stability, 1)} days",
            ]
        else:
            feedback_lines = [
                f"❌ *Not quite.* The correct answer is *{question.correct_answer}*.\n",
                f"💡 *Explanation:*\n{question.explanation}\n",
                f"📈 *Topic Mastery:* {mastery_percent}%",
                "Don't worry, we'll schedule a quick revision for this soon!",
            ]

        buttons = [
            OutgoingReplyButton(id="quiz_next_question", title="➡️ Next Question"),
            OutgoingReplyButton(id="study_this_topic", title="📖 Study Topic"),
        ]

        return "\n".join(feedback_lines), buttons


quiz_service = QuizService()
