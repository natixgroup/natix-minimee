"""create_contact_categories

Revision ID: 014
Revises: 013
Create Date: 2025-01-23 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create contact_categories table
    op.create_table(
        'contact_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),  # Unique code like 'famille', 'amis'
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('category_type', sa.String(), nullable=False),  # 'personnel', 'professionnel', 'autre'
        sa.Column('is_system', sa.Boolean(), nullable=False, default=False),  # System categories vs user-created
        sa.Column('user_id', sa.Integer(), nullable=True),  # NULL for system categories
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),  # For icons, colors, descriptions
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique constraint: code must be unique per user (or globally for system categories)
    op.create_unique_constraint('uq_contact_categories_code_user', 'contact_categories', ['code', 'user_id'])
    
    # Create indexes
    op.create_index('ix_contact_categories_code', 'contact_categories', ['code'], unique=False)
    op.create_index('ix_contact_categories_user_id', 'contact_categories', ['user_id'], unique=False)
    op.create_index('ix_contact_categories_category_type', 'contact_categories', ['category_type'], unique=False)
    op.create_index('ix_contact_categories_is_system', 'contact_categories', ['is_system'], unique=False)
    
    # Seed system categories
    connection = op.get_bind()
    
    system_categories = [
        {'code': 'famille', 'label': 'Famille', 'category_type': 'personnel', 'display_order': 1},
        {'code': 'amis', 'label': 'Amis', 'category_type': 'personnel', 'display_order': 2},
        {'code': 'collegues', 'label': 'Collègues', 'category_type': 'professionnel', 'display_order': 3},
        {'code': 'clients', 'label': 'Clients', 'category_type': 'professionnel', 'display_order': 4},
        {'code': 'fournisseurs', 'label': 'Fournisseurs', 'category_type': 'professionnel', 'display_order': 5},
        {'code': 'contacts_pro', 'label': 'Contacts Professionnels', 'category_type': 'professionnel', 'display_order': 6},
        {'code': 'contacts_perso', 'label': 'Contacts Personnels', 'category_type': 'personnel', 'display_order': 7},
        {'code': 'autres', 'label': 'Autres', 'category_type': 'autre', 'display_order': 8},
    ]
    
    for cat in system_categories:
        connection.execute(
            sa.text("""
                INSERT INTO contact_categories (code, label, category_type, is_system, user_id, display_order)
                VALUES (:code, :label, :category_type, true, NULL, :display_order)
            """),
            cat
        )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_contact_categories_is_system', table_name='contact_categories')
    op.drop_index('ix_contact_categories_category_type', table_name='contact_categories')
    op.drop_index('ix_contact_categories_user_id', table_name='contact_categories')
    op.drop_index('ix_contact_categories_code', table_name='contact_categories')
    
    # Drop unique constraint
    op.drop_constraint('uq_contact_categories_code_user', 'contact_categories', type_='unique')
    
    # Drop table
    op.drop_table('contact_categories')


