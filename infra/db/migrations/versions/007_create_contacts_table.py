"""create_contacts_table

Revision ID: 007
Revises: 006
Create Date: 2025-01-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('nickname', sa.String(), nullable=True),
        sa.Column('relation_type', sa.String(), nullable=True),  # épouse, ami, famille, collègue, etc.
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('languages', postgresql.JSONB(), nullable=True),  # Array of languages
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('importance_rating', sa.Integer(), nullable=True),  # 1-5
        sa.Column('dominant_themes', postgresql.JSONB(), nullable=True),  # Array of themes
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'conversation_id', name='uq_user_conversation_contact')
    )
    
    # Create indexes
    op.create_index('ix_contacts_user_id', 'contacts', ['user_id'], unique=False)
    op.create_index('ix_contacts_conversation_id', 'contacts', ['conversation_id'], unique=False)
    op.create_index('ix_contacts_relation_type', 'contacts', ['relation_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_contacts_relation_type', table_name='contacts')
    op.drop_index('ix_contacts_conversation_id', table_name='contacts')
    op.drop_index('ix_contacts_user_id', table_name='contacts')
    op.drop_table('contacts')


