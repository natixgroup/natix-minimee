"""create_user_info_visibility

Revision ID: 013
Revises: 012
Create Date: 2025-01-23 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_info_visibility table
    op.create_table(
        'user_info_visibility',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_info_id', sa.Integer(), nullable=False),
        sa.Column('relation_type_id', sa.Integer(), nullable=True),  # NULL = global rule
        sa.Column('contact_id', sa.Integer(), nullable=True),  # NULL = rule for category, not specific contact
        sa.Column('can_use_for_response', sa.Boolean(), nullable=False, default=False),  # Utilisé pour répondre à
        sa.Column('can_say_explicitly', sa.Boolean(), nullable=False, default=False),  # Dit explicitement à
        sa.Column('forbidden_for_response', sa.Boolean(), nullable=False, default=False),  # Interdit pour répondre
        sa.Column('forbidden_to_say', sa.Boolean(), nullable=False, default=False),  # Interdit de dire explicitement
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_info_id'], ['user_info.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['relation_type_id'], ['relation_types.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_user_info_visibility_user_info', 'user_info_visibility', ['user_info_id'], unique=False)
    op.create_index('ix_user_info_visibility_relation_type', 'user_info_visibility', ['relation_type_id'], unique=False)
    op.create_index('ix_user_info_visibility_contact', 'user_info_visibility', ['contact_id'], unique=False)
    op.create_index('ix_user_info_visibility_composite', 'user_info_visibility', ['user_info_id', 'relation_type_id', 'contact_id'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_user_info_visibility_composite', table_name='user_info_visibility')
    op.drop_index('ix_user_info_visibility_contact', table_name='user_info_visibility')
    op.drop_index('ix_user_info_visibility_relation_type', table_name='user_info_visibility')
    op.drop_index('ix_user_info_visibility_user_info', table_name='user_info_visibility')
    
    # Drop table
    op.drop_table('user_info_visibility')


