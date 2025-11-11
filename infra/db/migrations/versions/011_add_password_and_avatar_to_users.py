"""add_password_and_avatar_to_users

Revision ID: 011
Revises: 010
Create Date: 2024-11-11 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # Add password_hash column if it doesn't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'password_hash' not in columns:
        op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))
    
    # Add avatar_url column if it doesn't exist
    if 'avatar_url' not in columns:
        op.add_column('users', sa.Column('avatar_url', sa.String(), nullable=True))


def downgrade():
    # Remove avatar_url column
    op.drop_column('users', 'avatar_url')
    
    # Remove password_hash column
    op.drop_column('users', 'password_hash')

