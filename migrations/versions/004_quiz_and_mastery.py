"""Phase 4 migration: question_bank, attempts, and mastery tables

Revision ID: 004_quiz_and_mastery
Revises: 003_content_chunks
Create Date: 2026-10-15 00:12:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_quiz_and_mastery'
down_revision: Union[str, None] = '003_content_chunks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. question_bank table
    op.create_table(
        'question_bank',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_type', sa.String(length=32), server_default='MCQ', nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('correct_answer', sa.String(length=16), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.String(length=32), server_default='medium', nullable=False),
        sa.Column('verifier_score', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_question_bank_topic_id'), 'question_bank', ['topic_id'], unique=False)

    # 2. attempts table
    op.create_table(
        'attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('question_bank.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_response', sa.String(length=64), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('time_taken_seconds', sa.Integer(), server_default='30', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_attempts_student_id'), 'attempts', ['student_id'], unique=False)
    op.create_index(op.f('ix_attempts_question_id'), 'attempts', ['question_id'], unique=False)

    # 3. mastery table
    op.create_table(
        'mastery',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stability', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('difficulty', sa.Float(), server_default='5.0', nullable=False),
        sa.Column('reps', sa.Integer(), server_default='0', nullable=False),
        sa.Column('lapses', sa.Integer(), server_default='0', nullable=False),
        sa.Column('state', sa.String(length=32), server_default='new', nullable=False),
        sa.Column('last_reviewed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_review', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mastery_score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_mastery_student_id'), 'mastery', ['student_id'], unique=False)
    op.create_index(op.f('ix_mastery_topic_id'), 'mastery', ['topic_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mastery_topic_id'), table_name='mastery')
    op.drop_index(op.f('ix_mastery_student_id'), table_name='mastery')
    op.drop_table('mastery')
    op.drop_index(op.f('ix_attempts_question_id'), table_name='attempts')
    op.drop_index(op.f('ix_attempts_student_id'), table_name='attempts')
    op.drop_table('attempts')
    op.drop_index(op.f('ix_question_bank_topic_id'), table_name='question_bank')
    op.drop_table('question_bank')
