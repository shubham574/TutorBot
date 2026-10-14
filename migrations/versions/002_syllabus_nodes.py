"""Phase 2 migration: create syllabus_nodes table

Revision ID: 002_syllabus_nodes
Revises: 001_initial_phase1
Create Date: 2026-10-15 00:02:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_syllabus_nodes'
down_revision: Union[str, None] = '001_initial_phase1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'syllabus_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='CASCADE'), nullable=True),
        sa.Column('node_type', sa.String(length=32), nullable=False, comment='subject, unit, topic, subtopic'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('order_index', sa.Integer(), server_default='0', nullable=False),
        sa.Column('exam_date', sa.Date(), nullable=True),
        sa.Column('marks_weightage', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('estimated_minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_syllabus_nodes_student_id'), 'syllabus_nodes', ['student_id'], unique=False)
    op.create_index(op.f('ix_syllabus_nodes_parent_id'), 'syllabus_nodes', ['parent_id'], unique=False)
    op.create_index(op.f('ix_syllabus_nodes_node_type'), 'syllabus_nodes', ['node_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_syllabus_nodes_node_type'), table_name='syllabus_nodes')
    op.drop_index(op.f('ix_syllabus_nodes_parent_id'), table_name='syllabus_nodes')
    op.drop_index(op.f('ix_syllabus_nodes_student_id'), table_name='syllabus_nodes')
    op.drop_table('syllabus_nodes')
