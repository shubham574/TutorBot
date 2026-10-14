"""Study plan generator distributing syllabus topics across an adaptive timeline."""
import datetime
import uuid
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.study_plan import StudyPlan
from app.models.syllabus import SyllabusNode
from app.services.whatsapp.schemas import OutgoingReplyButton


class StudyPlannerService:
    """Creates balanced, topic-level revision and study schedules."""

    async def generate_study_plan(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
        start_date: Optional[datetime.date] = None,
        target_exam_date: Optional[datetime.date] = None,
    ) -> StudyPlan:
        """
        Distributes all topics from student's syllabus across days until the target exam.
        """
        today = start_date or datetime.date.today()

        # 1. Fetch topics
        stmt = select(SyllabusNode).where(
            SyllabusNode.student_id == student_id,
            SyllabusNode.node_type == "topic",
        ).order_by(SyllabusNode.order_index)
        res = await session.execute(stmt)
        topics = res.scalars().all()

        # If exam date not provided, check if stored on subject root
        if not target_exam_date:
            subj_stmt = select(SyllabusNode).where(
                SyllabusNode.student_id == student_id,
                SyllabusNode.node_type == "subject",
            )
            subj_res = await session.execute(subj_stmt)
            subj = subj_res.scalar_one_or_none()
            if subj and subj.exam_date:
                target_exam_date = subj.exam_date
            else:
                # Default to 30 days
                target_exam_date = today + datetime.timedelta(days=30)

        total_days = max(1, (target_exam_date - today).days)
        # Allocate 85% of days to covering topics, last 15% as revision buffer
        learning_days = max(1, int(total_days * 0.85))

        schedule: List[Dict[str, Any]] = []

        if not topics:
            # Fallback placeholder if no syllabus yet
            schedule.append({
                "day": 1,
                "date": today.isoformat(),
                "topic_id": None,
                "topic_name": "Syllabus Overview & Foundation",
                "target_minutes": 45,
                "status": "pending",
            })
        else:
            # Distribute topics across learning days
            for idx, topic in enumerate(topics):
                day_offset = int((idx / max(len(topics), 1)) * learning_days)
                session_date = today + datetime.timedelta(days=day_offset)
                schedule.append({
                    "day": idx + 1,
                    "date": session_date.isoformat(),
                    "topic_id": str(topic.id),
                    "topic_name": topic.title,
                    "target_minutes": topic.estimated_minutes,
                    "status": "pending",
                })

            # Add final buffer revision session
            revision_date = today + datetime.timedelta(days=learning_days + 1)
            schedule.append({
                "day": len(topics) + 1,
                "date": revision_date.isoformat(),
                "topic_id": None,
                "topic_name": "Full Syllabus Review & Practice Exam",
                "target_minutes": 90,
                "status": "pending",
            })

        # Save to database
        plan = StudyPlan(
            student_id=student_id,
            plan_schedule=schedule,
            status="active",
            start_date=today,
            target_exam_date=target_exam_date,
        )
        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        logger.info(
            "Created personalized study plan",
            student_id=str(student_id),
            total_sessions=len(schedule),
            exam_date=str(target_exam_date),
        )
        return plan

    def format_study_plan_for_whatsapp(
        self,
        plan: StudyPlan,
        subject_name: str = "Curriculum",
    ) -> Tuple[str, List[OutgoingReplyButton]]:
        """Formats the study plan timeline into a clear WhatsApp message."""
        exam_date_str = str(plan.target_exam_date) if plan.target_exam_date else "Flexible"
        total_sessions = len(plan.plan_schedule)

        lines = [
            f"📅 *Personalized Study Plan: {subject_name}*",
            f"🎯 *Exam Date:* {exam_date_str} | 🗓️ *Total Sessions:* {total_sessions}",
            "\n*Upcoming Study Sessions:*",
        ]

        # Display first 6 sessions
        for item in plan.plan_schedule[:6]:
            status_emoji = "✅" if item.get("status") == "completed" else "⏳"
            lines.append(
                f"• {status_emoji} *Day {item['day']} ({item['date']}):* {item['topic_name']} "
                f"({item['target_minutes']} mins)"
            )

        if total_sessions > 6:
            remaining = total_sessions - 6
            lines.append(f"...plus {remaining} more scheduled sessions & revision buffers.")

        lines.append("\nConsistency is the key to memory retention. Tap below to begin your first session!")

        buttons = [
            OutgoingReplyButton(id="start_first_topic", title="🚀 Start Day 1"),
            OutgoingReplyButton(id="quiz_this_topic", title="⚡ Practice Quiz"),
        ]

        return "\n".join(lines), buttons


study_planner = StudyPlannerService()
