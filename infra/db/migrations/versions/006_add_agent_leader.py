"""add_agent_leader

Revision ID: 006
Revises: 005
Create Date: 2025-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to agents table
    op.add_column('agents', sa.Column('is_minimee_leader', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('agents', sa.Column('whatsapp_integration_id', sa.Integer(), nullable=True))
    op.add_column('agents', sa.Column('whatsapp_display_name', sa.String(), nullable=True))
    op.add_column('agents', sa.Column('approval_rules', postgresql.JSONB(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_agents_whatsapp_integration',
        'agents', 'whatsapp_integrations',
        ['whatsapp_integration_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create indexes
    op.create_index('ix_agents_is_minimee_leader', 'agents', ['is_minimee_leader'], unique=False)
    op.create_index('ix_agents_whatsapp_integration_id', 'agents', ['whatsapp_integration_id'], unique=False)
    
    # Create unique constraint: only one leader per user (partial unique constraint)
    # Using unique index with WHERE clause (PostgreSQL partial unique constraint)
    op.execute("""
        CREATE UNIQUE INDEX uq_user_minimee_leader 
        ON agents (user_id) 
        WHERE is_minimee_leader = true
    """)
    
    # Migration: Mark existing "Minimee" agent as leader if exists
    op.execute("""
        UPDATE agents
        SET is_minimee_leader = true,
            whatsapp_display_name = 'Minimee'
        WHERE name = 'Minimee' AND is_minimee_leader = false
        AND NOT EXISTS (
            SELECT 1 FROM agents a2 
            WHERE a2.user_id = agents.user_id 
            AND a2.is_minimee_leader = true
        )
    """)
    
    # Link Minimee agent to minimee WhatsApp integration if exists
    op.execute("""
        UPDATE agents
        SET whatsapp_integration_id = (
            SELECT id FROM whatsapp_integrations
            WHERE user_id = agents.user_id
            AND integration_type = 'minimee'
            LIMIT 1
        )
        WHERE is_minimee_leader = true
        AND whatsapp_integration_id IS NULL
    """)


def downgrade() -> None:
    op.drop_index('uq_user_minimee_leader', table_name='agents')
    op.drop_index('ix_agents_whatsapp_integration_id', table_name='agents')
    op.drop_index('ix_agents_is_minimee_leader', table_name='agents')
    op.drop_constraint('fk_agents_whatsapp_integration', 'agents', type_='foreignkey')
    op.drop_column('agents', 'approval_rules')
    op.drop_column('agents', 'whatsapp_display_name')
    op.drop_column('agents', 'whatsapp_integration_id')
    op.drop_column('agents', 'is_minimee_leader')


