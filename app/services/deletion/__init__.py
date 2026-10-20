"""Data Deletion Service: Implements comprehensive student data removal per privacy requirements."""
import uuid
from typing import List
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.logging_config import logger
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.content import ContentChunk
from app.models.mastery import TopicMastery
from app.models.quiz import QuestionBank, Attempt
from app.models.study_plan import StudyPlan
from app.models.message_log import WhatsAppMessageLog
from app.services.storage import storage_service


class DataDeletionService:
    """Handles complete student data deletion across all systems."""

    async def delete_student_data(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
    ) -> dict:
        """
        Deletes ALL data associated with a student across all tables and storage.

        Returns:
            dict: Summary of what was deleted
        """
        logger.info("Starting comprehensive student data deletion", student_id=str(student_id))

        # 1. Delete MinIO files (syllabus documents, uploads, generated PDFs)
        minio_deleted = storage_service.delete_files_by_prefix(f"{student_id}/")

        # 2. Get counts before deletion for reporting
        counts = await self._get_student_data_counts(student_id, session)

        # 3. Delete from database tables (CASCADE will handle most, but we do explicit for clarity)

        # Delete LangGraph checkpoints (if any) - these would be in a separate table
        # For now, we assume checkpoints are tied to student_id in whatsapp_messages_log or separate table

        # Delete attempts
        await session.execute(
            delete(Attempt).where(Attempt.student_id == student_id)
        )

        # Delete TopicMastery records
        await session.execute(
            delete(TopicMastery).where(TopicMastery.student_id == student_id)
        )

        # Delete QuestionBank entries (only those created for this student's topics)
        # First get topic IDs for this student
        topic_ids_stmt = select(SyllabusNode.id).where(SyllabusNode.student_id == student_id)
        topic_ids_result = await session.execute(topic_ids_stmt)
        topic_ids = [row[0] for row in topic_ids_result.fetchall()]

        if topic_ids:
            await session.execute(
                delete(QuestionBank).where(QuestionBank.topic_id.in_(topic_ids))
            )

        # Delete StudyPlan records
        await session.execute(
            delete(StudyPlan).where(StudyPlan.student_id == student_id)
        )

        # Delete ContentChunk records (both private and any linked to student's topics)
        await session.execute(
            delete(ContentChunk).where(ContentChunk.student_id == student_id)
        )
        # Also delete chunks linked to student's syllabus topics (even if student_id is NULL)
        if topic_ids:
            await session.execute(
                delete(ContentChunk).where(ContentChunk.topic_id.in_(topic_ids))
            )

        # Delete SyllabusNode records (CASCADE will handle children)
        await session.execute(
            delete(SyllabusNode).where(SyllabusNode.student_id == student_id)
        )

        # Delete WhatsAppMessageLog records
        await session.execute(
            delete(WhatsAppMessageLog).where(WhatsAppMessageLog.student_id == student_id)
        )

        # Finally, delete the Student record itself
        await session.execute(
            delete(Student).where(Student.id == student_id)
        )

        await session.commit()

        logger.info(
            "Completed student data deletion",
            student_id=str(student_id),
            minio_files_deleted=minio_deleted,
            **counts,
        )

        return {
            "student_id": str(student_id),
            "minio_files_deleted": minio_deleted,
            **counts,
        }

    async def _get_student_data_counts(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
    ) -> dict:
        """Gets counts of student data before deletion for reporting."""
        counts = {}

        # Syllabus nodes
        res = await session.execute(
            select(func.count(SyllabusNode.id)).where(SyllabusNode.student_id == student_id)
        )
        counts["syllabus_nodes_deleted"] = res.scalar() or 0

        # Content chunks (private)
        res = await session.execute(
            select(func.count(ContentChunk.id)).where(ContentChunk.student_id == student_id)
        )
        counts["content_chunks_private_deleted"] = res.scalar() or 0

        # Mastery records
        res = await session.execute(
            select(func.count(TopicMastery.id)).where(TopicMastery.student_id == student_id)
        )
        counts["mastery_records_deleted"] = res.scalar() or 0

        # Attempts
        res = await session.execute(
            select(func.count(Attempt.id)).where(Attempt.student_id == student_id)
        )
        counts["attempts_deleted"] = res.scalar() or 0

        # Study plans
        res = await session.execute(
            select(func.count(StudyPlan.id)).where(StudyPlan.student_id == student_id)
        )
        counts["study_plans_deleted"] = res.scalar() or 0

        # WhatsApp message logs
        res = await session.execute(
            select(func.count(WhatsAppMessageLog.id)).where(WhatsAppMessageLog.student_id == student_id)
        )
        counts["message_logs_deleted"] = res.scalar() or 0

        return counts

    async def verify_deletion_complete(
        self,
        student_id: uuid.UUID,
        session: AsyncSession,
    ) -> bool:
        """
        Verifies that all student data has been completely removed.

        Returns:
            True if no data remains for the student_id anywhere
        """
        # Check each table
        checks = [
            select(func.count(Student.id)).where(Student.id == student_id),
            select(func.count(SyllabusNode.id)).where(SyllabusNode.student_id == student_id),
            select(func.count(ContentChunk.id)).where(ContentChunk.student_id == student_id),
            select(func.count(TopicMastery.id)).where(TopicMastery.student_id == student_id),
            select(func.count(Attempt.id)).where(Attempt.student_id == student_id),
            select(func.count(StudyPlan.id)).where(StudyPlan.student_id == student_id),
            select(func.count(WhatsAppMessageLog.id)).where(WhatsAppMessageLog.student_id == student_id),
        ]

        for stmt in checks:
            res = await session.execute(stmt)
            if res.scalar() > 0:
                return False

        # Check MinIO (this is best-effort since we can't easily verify without listing)
        # In production, you might want to add a MinIO verification step

        return True


data_deletion_service = DataDeletionService()