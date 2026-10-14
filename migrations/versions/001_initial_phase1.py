"""Initial Phase 1 migration: students and whatsapp_messages_log tables

Revision ID: 001_initial_phase1
Revises: 
Create Date: 2026-10-14 23:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_phase1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create students table
    op.create_table(
        'students',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('phone_number', sa.String(length=32), nullable=False, comment='E.164 formatted phone number'),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('grade_level', sa.String(length=64), nullable=True),
        sa.Column('target_exam', sa.String(length=128), nullable=True),
        sa.Column('timezone', sa.String(length=64), server_default='Asia/Kolkata', nullable=False),
        sa.Column('consent_given', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('consent_given_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('quiet_hours_start', sa.Time(), server_default='22:00:00', nullable=False),
        sa.Column('quiet_hours_end', sa.Time(), server_default='07:00:00', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_students_phone_number'), 'students', ['phone_number'], unique=True)

    # 2. Create whatsapp_messages_log table
    op.create_table(
        'whatsapp_messages_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('wamid', sa.String(length=128), nullable=False, comment='Meta WhatsApp message ID used for deduplication'),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='SET NULL'), nullable=True),
        sa.Column('phone_number', sa.String(length=32), nullable=False, comment='Sender or recipient phone number'),
        sa.Column('direction', sa.String(length=16), nullable=False, comment='INBOUND or OUTBOUND'),
        sa.Column('message_type', sa.String(length=32), server_default='text', nullable=False, comment='text, interactive, document, audio, etc.'),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Raw incoming or outgoing JSON payload'),
        sa.Column('status', sa.String(length=32), server_default='RECEIVED', nullable=False, comment='RECEIVED, QUEUED, PROCESSED, FAILED, SENT'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_whatsapp_messages_log_wamid'), 'whatsapp_messages_log', ['wamid'], unique=True)
    op.create_index(op.f('ix_whatsapp_messages_log_phone_number'), 'whatsapp_messages_log', ['phone_number'], unique=False)
    op.create_index(op.f('ix_whatsapp_messages_log_student_id'), 'whatsapp_messages_log', ['student_id'], unique=False)
    op.create_index(op.f('ix_whatsapp_messages_log_status'), 'whatsapp_messages_log', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_whatsapp_messages_log_status'), table_name='whatsapp_messages_log')
    op.drop_index(op.f('ix_whatsapp_messages_log_student_id'), table_name='whatsapp_messages_log')
    op.drop_index(op.f('ix_whatsapp_messages_log_phone_number'), table_name='whatsapp_messages_log')
    op.drop_index(op.f('ix_whatsapp_messages_log_wamid'), table_name='whatsapp_messages_log')
    op.drop_table('whatsapp_messages_log')
    op.drop_index(op.f('ix_students_phone_number'), table_name='students')
    op.drop_table('students')
