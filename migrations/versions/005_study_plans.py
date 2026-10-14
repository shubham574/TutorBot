"""Phase 6 migration: study_plans table

Revision ID: 005_study_plans
Revises: 004_quiz_and_mastery
Create Date: 2026-10-15 00:24:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_study_plans'
down_revision: Union[str, None] = '004_quiz_and_mastery'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'study_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_schedule', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='active', nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('target_exam_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_study_plans_student_id'), 'study_plans', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_study_plans_student_id'), table_name='study_plans')
    op.drop_table('study_plans')
