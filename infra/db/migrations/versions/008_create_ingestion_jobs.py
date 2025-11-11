"""create_ingestion_jobs

Revision ID: 008
Revises: 007
Create Date: 2025-01-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ingestion_jobs table
    op.create_table(
        'ingestion_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),  # pending/running/completed/failed
        sa.Column('progress', postgresql.JSONB(), nullable=True),  # Progress data
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_ingestion_jobs_user_id', 'ingestion_jobs', ['user_id'], unique=False)
    op.create_index('ix_ingestion_jobs_status', 'ingestion_jobs', ['status'], unique=False)
    op.create_index('ix_ingestion_jobs_conversation_id', 'ingestion_jobs', ['conversation_id'], unique=False)
    op.create_index('ix_ingestion_jobs_created_at', 'ingestion_jobs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ingestion_jobs_created_at', table_name='ingestion_jobs')
    op.drop_index('ix_ingestion_jobs_conversation_id', table_name='ingestion_jobs')
    op.drop_index('ix_ingestion_jobs_status', table_name='ingestion_jobs')
    op.drop_index('ix_ingestion_jobs_user_id', table_name='ingestion_jobs')
    op.drop_table('ingestion_jobs')

