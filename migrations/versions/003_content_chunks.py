"""Phase 3 migration: create content_chunks table

Revision ID: 003_content_chunks
Revises: 002_syllabus_nodes
Create Date: 2026-10-15 00:08:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_content_chunks'
down_revision: Union[str, None] = '002_syllabus_nodes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('subject', sa.String(length=128), nullable=False),
        sa.Column('source_doc_id', sa.String(length=255), nullable=False),
        sa.Column('source_title', sa.String(length=255), nullable=False),
        sa.Column('page_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('doc_type', sa.String(length=64), server_default='notes', nullable=False),
        sa.Column('difficulty', sa.String(length=32), server_default='medium', nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_content_chunks_student_id'), 'content_chunks', ['student_id'], unique=False)
    op.create_index(op.f('ix_content_chunks_topic_id'), 'content_chunks', ['topic_id'], unique=False)
    op.create_index(op.f('ix_content_chunks_subject'), 'content_chunks', ['subject'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_content_chunks_subject'), table_name='content_chunks')
    op.drop_index(op.f('ix_content_chunks_topic_id'), table_name='content_chunks')
    op.drop_index(op.f('ix_content_chunks_student_id'), table_name='content_chunks')
    op.drop_table('content_chunks')
