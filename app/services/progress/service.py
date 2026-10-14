"""Student Progress Reporting Service with visual Unicode charts."""
import uuid
from typing import Tuple, List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mastery import TopicMastery
from app.models.quiz import Attempt
from app.models.syllabus import SyllabusNode
from app.services.whatsapp.schemas import OutgoingReplyButton


def render_progress_bar(percentage: float, total_blocks: int = 12) -> str:
    """Renders a clean Unicode progress bar, e.g. [████████░░░░] 67%."""
    filled = int(round((percentage / 100.0) * total_blocks))
    filled = min(max(filled, 0), total_blocks)
    empty = total_blocks - filled
    return f"[{'█' * filled}{'░' * empty}] {int(percentage)}%"


class ProgressReportService:
    """Computes student mastery analytics, syllabus coverage, and progress reports."""

    async def generate_progress_report(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
    ) -> Tuple[str, List[OutgoingReplyButton]]:
        """
        Calculates student analytics and builds a WhatsApp progress dashboard.
        """
        # 1. Total Topics in syllabus
        topic_stmt = select(func.count(SyllabusNode.id)).where(
            and_(
                SyllabusNode.student_id == student_id,
                SyllabusNode.node_type == "topic",
            )
        )
        t_res = await session.execute(topic_stmt)
        total_topics = t_res.scalar() or 0

        # 2. Mastered Topics (mastery_score >= 0.70)
        mastery_stmt = select(TopicMastery).where(TopicMastery.student_id == student_id)
        m_res = await session.execute(mastery_stmt)
        masteries = m_res.scalars().all()

        mastered_count = sum(1 for m in masteries if m.mastery_score >= 0.70)
        learning_count = sum(1 for m in masteries if m.mastery_score < 0.70)

        # 3. Overall Syllabus Completion
        completion_pct = (mastered_count / max(total_topics, 1)) * 100.0 if total_topics else 0.0
        bar = render_progress_bar(completion_pct)

        # 4. Attempt Statistics
        attempts_all_stmt = select(Attempt).where(Attempt.student_id == student_id)
        attempts_res = await session.execute(attempts_all_stmt)
        attempts_list = attempts_res.scalars().all()
        total_attempts = len(attempts_list)
        correct_attempts = sum(1 for a in attempts_list if a.is_correct)
        accuracy_pct = int((correct_attempts / max(total_attempts, 1)) * 100) if total_attempts else 0

        # 5. Format Message
        lines = [
            "📊 *Student Academic Progress Dashboard*",
            f"📈 *Syllabus Mastery:*",
            f"{bar}",
            "",
            f"📚 *Total Topics in Syllabus:* {total_topics}",
            f"🌟 *Mastered Topics:* {mastered_count}",
            f"⏳ *Topics in Learning:* {learning_count}",
            "",
            "🎯 *Quiz Performance:*",
            f"• Questions Answered: {total_attempts}",
            f"• Overall Accuracy: {accuracy_pct}% ({correct_attempts}/{total_attempts} correct)",
        ]

        if total_topics == 0:
            lines.append("\n💡 *Tip:* Upload your syllabus to unlock tailored topic progress tracking!")

        buttons = [
            OutgoingReplyButton(id="start_first_topic", title="📅 View Study Plan"),
            OutgoingReplyButton(id="quiz_this_topic", title="⚡ Practice Quiz"),
        ]

        return "\n".join(lines), buttons


progress_service = ProgressReportService()
