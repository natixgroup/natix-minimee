"""create_pending_approvals

Revision ID: 004
Revises: 003
Create Date: 2025-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pending_approvals table
    op.create_table(
        'pending_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),  # NULL for email drafts
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('sender', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),  # 'whatsapp' or 'gmail'
        sa.Column('recipient_jid', sa.String(), nullable=True),  # For WhatsApp
        sa.Column('recipient_email', sa.String(), nullable=True),  # For Gmail
        sa.Column('option_a', sa.Text(), nullable=False),
        sa.Column('option_b', sa.Text(), nullable=False),
        sa.Column('option_c', sa.Text(), nullable=False),
        sa.Column('context_summary', sa.Text(), nullable=True),
        sa.Column('original_content_preview', sa.Text(), nullable=True),
        sa.Column('email_subject', sa.String(), nullable=True),  # For Gmail emails
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),  # pending/approved/rejected/expired
        sa.Column('group_message_id', sa.String(), nullable=True),  # WhatsApp message ID in group
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),  # Foreign key can be NULL for email drafts
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_pending_approvals_id', 'pending_approvals', ['id'], unique=False)
    op.create_index('ix_pending_approvals_message_id', 'pending_approvals', ['message_id'], unique=False)
    op.create_index('ix_pending_approvals_status', 'pending_approvals', ['status'], unique=False)
    op.create_index('ix_pending_approvals_expires_at', 'pending_approvals', ['expires_at'], unique=False)
    op.create_index('ix_pending_approvals_user_id', 'pending_approvals', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_pending_approvals_user_id', table_name='pending_approvals')
    op.drop_index('ix_pending_approvals_expires_at', table_name='pending_approvals')
    op.drop_index('ix_pending_approvals_status', table_name='pending_approvals')
    op.drop_index('ix_pending_approvals_message_id', table_name='pending_approvals')
    op.drop_index('ix_pending_approvals_id', table_name='pending_approvals')
    op.drop_table('pending_approvals')

