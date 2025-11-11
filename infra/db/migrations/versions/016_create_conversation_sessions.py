"""create_conversation_sessions

Revision ID: 016
Revises: 015
Create Date: 2025-01-23 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversation_sessions table
    op.create_table(
        'conversation_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_type', sa.String(), nullable=False),  # 'normal', 'getting_to_know'
        sa.Column('title', sa.String(), nullable=True),  # User-defined or auto-generated title
        sa.Column('conversation_id', sa.String(), nullable=False),  # Links to messages.conversation_id
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),  # Soft delete
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_conversation_sessions_user_id', 'conversation_sessions', ['user_id'], unique=False)
    op.create_index('ix_conversation_sessions_session_type', 'conversation_sessions', ['session_type'], unique=False)
    op.create_index('ix_conversation_sessions_deleted_at', 'conversation_sessions', ['deleted_at'], unique=False)
    op.create_index('ix_conversation_sessions_conversation_id', 'conversation_sessions', ['conversation_id'], unique=False)
    op.create_index('ix_conversation_sessions_user_type', 'conversation_sessions', ['user_id', 'session_type'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_conversation_sessions_user_type', table_name='conversation_sessions')
    op.drop_index('ix_conversation_sessions_conversation_id', table_name='conversation_sessions')
    op.drop_index('ix_conversation_sessions_deleted_at', table_name='conversation_sessions')
    op.drop_index('ix_conversation_sessions_session_type', table_name='conversation_sessions')
    op.drop_index('ix_conversation_sessions_user_id', table_name='conversation_sessions')
    
    # Drop table
    op.drop_table('conversation_sessions')


