"""create_whatsapp_integrations

Revision ID: 005
Revises: 004
Create Date: 2025-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create whatsapp_integrations table
    op.create_table(
        'whatsapp_integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('integration_type', sa.String(), nullable=False),  # 'user' or 'minimee'
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='disconnected'),  # connected/disconnected/pending
        sa.Column('auth_info_path', sa.String(), nullable=True),  # Path to auth_info directory
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'integration_type', name='uq_user_integration_type')  # One integration per type per user
    )
    
    # Create indexes
    op.create_index('ix_whatsapp_integrations_id', 'whatsapp_integrations', ['id'], unique=False)
    op.create_index('ix_whatsapp_integrations_user_id', 'whatsapp_integrations', ['user_id'], unique=False)
    op.create_index('ix_whatsapp_integrations_integration_type', 'whatsapp_integrations', ['integration_type'], unique=False)
    op.create_index('ix_whatsapp_integrations_status', 'whatsapp_integrations', ['status'], unique=False)
    
    # Migration: Create entry for existing user account (if any)
    # We'll detect if auth_info directory exists and create 'user' integration
    # For now, we'll create a default 'user' integration for user_id=1
    op.execute("""
        INSERT INTO whatsapp_integrations (user_id, integration_type, status, display_name)
        VALUES (1, 'user', 'disconnected', 'User WhatsApp')
        ON CONFLICT (user_id, integration_type) DO NOTHING
    """)
    
    # Create empty 'minimee' integration for user_id=1
    op.execute("""
        INSERT INTO whatsapp_integrations (user_id, integration_type, status, display_name)
        VALUES (1, 'minimee', 'disconnected', 'Minimee')
        ON CONFLICT (user_id, integration_type) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index('ix_whatsapp_integrations_status', table_name='whatsapp_integrations')
    op.drop_index('ix_whatsapp_integrations_integration_type', table_name='whatsapp_integrations')
    op.drop_index('ix_whatsapp_integrations_user_id', table_name='whatsapp_integrations')
    op.drop_index('ix_whatsapp_integrations_id', table_name='whatsapp_integrations')
    op.drop_table('whatsapp_integrations')


