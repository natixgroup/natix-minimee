"""add_category_to_contacts

Revision ID: 015
Revises: 014
Create Date: 2025-01-23 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add contact_category_id column to contacts table
    op.add_column('contacts', sa.Column('contact_category_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_contacts_contact_category_id',
        'contacts',
        'contact_categories',
        ['contact_category_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # Create index
    op.create_index('ix_contacts_contact_category_id', 'contacts', ['contact_category_id'], unique=False)
    
    # Try to classify existing contacts based on their relation_types
    connection = op.get_bind()
    
    # Map relation_type categories to contact_categories
    category_mapping = {
        'personnel': 'contacts_perso',
        'professionnel': 'contacts_pro',
    }
    
    # Get relation_types and their categories
    rt_result = connection.execute(
        sa.text("""
            SELECT DISTINCT rt.category, c.id as contact_id
            FROM contacts c
            JOIN contact_relation_types crt ON c.id = crt.contact_id
            JOIN relation_types rt ON crt.relation_type_id = rt.id
            WHERE c.contact_category_id IS NULL
        """)
    )
    
    contacts_to_update = rt_result.fetchall()
    
    for category, contact_id in contacts_to_update:
        if category in category_mapping:
            category_code = category_mapping[category]
            # Get contact_category_id for this code
            cat_result = connection.execute(
                sa.text("SELECT id FROM contact_categories WHERE code = :code AND is_system = true"),
                {'code': category_code}
            )
            cat_row = cat_result.fetchone()
            if cat_row:
                cat_id = cat_row[0]
                # Update contact
                connection.execute(
                    sa.text("UPDATE contacts SET contact_category_id = :cat_id WHERE id = :contact_id"),
                    {'cat_id': cat_id, 'contact_id': contact_id}
                )
    
    # Set default category 'autres' for contacts without category
    autres_result = connection.execute(
        sa.text("SELECT id FROM contact_categories WHERE code = 'autres' AND is_system = true")
    )
    autres_row = autres_result.fetchone()
    if autres_row:
        autres_id = autres_row[0]
        connection.execute(
            sa.text("UPDATE contacts SET contact_category_id = :cat_id WHERE contact_category_id IS NULL"),
            {'cat_id': autres_id}
        )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_contacts_contact_category_id', table_name='contacts')
    
    # Drop foreign key
    op.drop_constraint('fk_contacts_contact_category_id', 'contacts', type_='foreignkey')
    
    # Drop column
    op.drop_column('contacts', 'contact_category_id')


