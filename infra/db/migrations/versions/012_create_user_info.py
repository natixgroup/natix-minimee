"""create_user_info

Revision ID: 012
Revises: 011
Create Date: 2025-01-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_info table
    op.create_table(
        'user_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('info_type', sa.String(), nullable=False),  # first_name, last_name, birth_date, etc.
        sa.Column('info_value', sa.Text(), nullable=True),  # For simple text values
        sa.Column('info_value_json', postgresql.JSONB(), nullable=True),  # For complex values (arrays, objects)
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_user_info_user_id', 'user_info', ['user_id'], unique=False)
    op.create_index('ix_user_info_info_type', 'user_info', ['info_type'], unique=False)
    op.create_index('ix_user_info_user_type', 'user_info', ['user_id', 'info_type'], unique=True)  # One info per type per user


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_user_info_user_type', table_name='user_info')
    op.drop_index('ix_user_info_info_type', table_name='user_info')
    op.drop_index('ix_user_info_user_id', table_name='user_info')
    
    # Drop table
    op.drop_table('user_info')


