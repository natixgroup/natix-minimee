"""add_recipients_to_messages

Revision ID: 003
Revises: 002
Create Date: 2025-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add recipient column for 1-1 conversations
    op.add_column('messages', sa.Column('recipient', sa.String(), nullable=True))
    
    # Add recipients JSONB column for group conversations
    op.add_column('messages', sa.Column('recipients', postgresql.JSONB, nullable=True))
    
    # Add index on recipient for filtering
    op.create_index('ix_messages_recipient', 'messages', ['recipient'], unique=False)
    
    # Add index on recipients using GIN for JSONB queries
    op.execute("CREATE INDEX ix_messages_recipients ON messages USING GIN (recipients);")


def downgrade() -> None:
    op.drop_index('ix_messages_recipients', table_name='messages')
    op.drop_index('ix_messages_recipient', table_name='messages')
    op.drop_column('messages', 'recipients')
    op.drop_column('messages', 'recipient')

