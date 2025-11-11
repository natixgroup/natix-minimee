"""add_gender_to_contacts

Revision ID: 009
Revises: 008
Create Date: 2025-01-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add gender column to contacts table
    op.add_column('contacts', sa.Column('gender', sa.String(), nullable=True))  # masculin, féminin, autre


def downgrade() -> None:
    op.drop_column('contacts', 'gender')

