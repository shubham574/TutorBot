"""Integration tests for student data deletion (/delete my data)."""
import pytest
import datetime
from unittest.mock import patch
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
from app.models.student import Student
from app.models.syllabus import SyllabusNode
from app.models.content import ContentChunk
from app.models.mastery import TopicMastery
from app.models.quiz import QuestionBank, Attempt
from app.models.study_plan import StudyPlan
from app.models.message_log import WhatsAppMessageLog
from app.services.deletion import data_deletion_service
import uuid


@pytest.fixture
async def test_db_session():
    """Sets up an in-memory SQLite database for data deletion testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    # Patch the session factory used by the worker tasks
    with patch("app.workers.tasks.async_session_factory", session_factory):
        yield session_factory

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_delete_my_data_removes_all_student_data(test_db_session, mock_storage):
    """Tests that /delete my data removes all student data across all tables and MinIO."""
    # Patch storage service globally for this test
    with patch("app.services.deletion.storage_service", mock_storage):
        async with test_db_session() as session:
            # 1. Create a student with full data
            student = Student(
                phone_number="919876543210",
                name="Test Student",
                consent_given=True,
            )
            session.add(student)
            await session.flush()

            # Create syllabus nodes
            root_node = SyllabusNode(
                student_id=student.id,
                node_type="subject",
                title="Physics",
                order_index=0,
            )
            session.add(root_node)
            await session.flush()

            topic_node = SyllabusNode(
                student_id=student.id,
                parent_id=root_node.id,
                node_type="topic",
                title="Kinematics",
                order_index=0,
                estimated_minutes=30,
            )
            session.add(topic_node)
            await session.flush()

            # Create content chunks (private)
            chunk1 = ContentChunk(
                student_id=student.id,
                topic_id=topic_node.id,
                subject="Physics",
                source_doc_id="doc_001",
                source_title="NCERT Physics",
                page_number=1,
                doc_type="textbook",
                difficulty="medium",
                content="Kinematics is the study of motion...",
            )
            chunk2 = ContentChunk(
                student_id=student.id,
                topic_id=topic_node.id,
                subject="Physics",
                source_doc_id="doc_001",
                source_title="NCERT Physics",
                page_number=2,
                doc_type="textbook",
                difficulty="medium",
                content="Velocity is the rate of change...",
            )
            session.add_all([chunk1, chunk2])

            # Create mastery record
            mastery = TopicMastery(
                student_id=student.id,
                topic_id=topic_node.id,
                stability=2.5,
                difficulty=4.0,
                reps=3,
                lapses=0,
                state="review",
                mastery_score=0.75,
            )
            session.add(mastery)

            # Create question bank entry
            question = QuestionBank(
                topic_id=topic_node.id,
                question_type="MCQ",
                question_text="What is velocity?",
                options={"A": "Rate of change of position", "B": "Rate of change of speed", "C": "Distance per time"},
                correct_answer="A",
                explanation="Velocity is the rate of change of position with respect to time.",
                difficulty="medium",
                verifier_score=0.95,
            )
            session.add(question)
            await session.flush()

            # Create attempt
            attempt = Attempt(
                student_id=student.id,
                question_id=question.id,
                student_response="A",
                is_correct=True,
                score=1.0,
                feedback="Correct!",
                time_taken_seconds=30,
            )
            session.add(attempt)

            # Create study plan
            study_plan = StudyPlan(
                student_id=student.id,
                plan_schedule=[
                    {"date": "2026-10-20", "topic_id": str(topic_node.id), "topic_name": "Kinematics", "minutes": 30, "status": "pending"}
                ],
                status="active",
                start_date=datetime.date(2026, 10, 20),
            )
            session.add(study_plan)

            # Create message logs
            inbound_log = WhatsAppMessageLog(
                wamid="wamid.test_001",
                student_id=student.id,
                phone_number="919876543210",
                direction="INBOUND",
                message_type="text",
                raw_payload={},
                status="PROCESSED",
            )
            outbound_log = WhatsAppMessageLog(
                wamid="wamid.test_002",
                student_id=student.id,
                phone_number="919876543210",
                direction="OUTBOUND",
                message_type="text",
                raw_payload={},
                status="SENT",
            )
            session.add_all([inbound_log, outbound_log])

            # Upload mock files to MinIO
            mock_storage.upload_file(b"fake pdf content", f"{student.id}/syllabus.pdf")
            mock_storage.upload_file(b"fake exam pdf", f"{student.id}/exam_001.pdf")

            await session.commit()

            # Verify all data exists before deletion
            assert await _count_student_data(session, student.id) > 0
            assert mock_storage.file_exists(f"{student.id}/syllabus.pdf")
            assert mock_storage.file_exists(f"{student.id}/exam_001.pdf")

            # 2. Call the data deletion service
            deletion_summary = await data_deletion_service.delete_student_data(
                student_id=student.id,
                session=session,
            )

            # 3. Verify deletion summary
            assert deletion_summary["student_id"] == str(student.id)
            assert deletion_summary["syllabus_nodes_deleted"] == 2  # root + topic
            assert deletion_summary["content_chunks_private_deleted"] == 2
            assert deletion_summary["mastery_records_deleted"] == 1
            assert deletion_summary["attempts_deleted"] == 1
            assert deletion_summary["study_plans_deleted"] == 1
            assert deletion_summary["message_logs_deleted"] == 2
            assert deletion_summary["minio_files_deleted"] == 2

            # 4. Verify all data is gone from database
            assert await _count_student_data(session, student.id) == 0

            # 5. Verify MinIO files are deleted
            assert not mock_storage.file_exists(f"{student.id}/syllabus.pdf")
            assert not mock_storage.file_exists(f"{student.id}/exam_001.pdf")

            # 6. Verify verification method returns True
            verified = await data_deletion_service.verify_deletion_complete(
                student_id=student.id,
                session=session,
            )
            assert verified is True


@pytest.mark.asyncio
async def test_delete_my_data_handles_empty_student(test_db_session, mock_storage):
    """Tests that deleting a student with no data works correctly."""
    with patch("app.services.deletion.storage_service", mock_storage):
        async with test_db_session() as session:
            # Create student with no additional data
            student = Student(
                phone_number="919999999999",
                name="Empty Student",
            )
            session.add(student)
            await session.commit()

            # Delete
            deletion_summary = await data_deletion_service.delete_student_data(
                student_id=student.id,
                session=session,
            )

            # Verify summary shows zeros
            assert deletion_summary["syllabus_nodes_deleted"] == 0
            assert deletion_summary["content_chunks_private_deleted"] == 0
            assert deletion_summary["mastery_records_deleted"] == 0
            assert deletion_summary["attempts_deleted"] == 0
            assert deletion_summary["study_plans_deleted"] == 0
            assert deletion_summary["message_logs_deleted"] == 0

            # Verify student is gone
            stmt = select(Student).where(Student.id == student.id)
            res = await session.execute(stmt)
            assert res.scalar_one_or_none() is None

            verified = await data_deletion_service.verify_deletion_complete(
                student_id=student.id,
                session=session,
            )
            assert verified is True


async def _count_student_data(session, student_id: uuid.UUID) -> int:
    """Helper to count all student data across tables."""
    total = 0
    for model in [Student, SyllabusNode, ContentChunk, TopicMastery, Attempt, StudyPlan, WhatsAppMessageLog]:
        if model == Student:
            stmt = select(func.count(model.id)).where(model.id == student_id)
        else:
            stmt = select(func.count(model.id)).where(model.student_id == student_id)
        res = await session.execute(stmt)
        total += res.scalar() or 0
    return total