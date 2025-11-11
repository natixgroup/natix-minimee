"""create_relation_types

Revision ID: 010
Revises: 009
Create Date: 2025-01-22 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create relation_types table
    op.create_table(
        'relation_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False, unique=True),  # Unique code like 'epoux', 'client'
        sa.Column('label_masculin', sa.String(), nullable=False),
        sa.Column('label_feminin', sa.String(), nullable=False),
        sa.Column('label_autre', sa.String(), nullable=True),  # For "autre" gender
        sa.Column('category', sa.String(), nullable=False),  # 'personnel' or 'professionnel'
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),  # For icons, colors, descriptions
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create contact_relation_types junction table
    op.create_table(
        'contact_relation_types',
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('relation_type_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['relation_type_id'], ['relation_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('contact_id', 'relation_type_id')
    )
    
    # Create indexes
    op.create_index('ix_relation_types_category', 'relation_types', ['category'], unique=False)
    op.create_index('ix_relation_types_category_order', 'relation_types', ['category', 'display_order'], unique=False)
    op.create_index('ix_relation_types_code', 'relation_types', ['code'], unique=True)
    op.create_index('ix_relation_types_is_active', 'relation_types', ['is_active'], unique=False)
    op.create_index('ix_contact_relation_types_contact', 'contact_relation_types', ['contact_id'], unique=False)
    op.create_index('ix_contact_relation_types_type', 'contact_relation_types', ['relation_type_id'], unique=False)
    op.create_index('ix_contact_relation_types_composite', 'contact_relation_types', ['contact_id', 'relation_type_id'], unique=True)
    
    # Seed relation types
    connection = op.get_bind()
    
    # Personnel category
    personnel_types = [
        {'code': 'epoux', 'label_masculin': 'époux', 'label_feminin': 'épouse', 'label_autre': 'époux/épouse', 'category': 'personnel', 'display_order': 1},
        {'code': 'fiance', 'label_masculin': 'fiancé', 'label_feminin': 'fiancée', 'label_autre': 'fiancé/fiancée', 'category': 'personnel', 'display_order': 2},
        {'code': 'ami', 'label_masculin': 'ami', 'label_feminin': 'amie', 'label_autre': 'ami/amie', 'category': 'personnel', 'display_order': 3},
        {'code': 'famille', 'label_masculin': 'famille', 'label_feminin': 'famille', 'label_autre': 'famille', 'category': 'personnel', 'display_order': 4},
        {'code': 'voisin', 'label_masculin': 'voisin', 'label_feminin': 'voisine', 'label_autre': 'voisin/voisine', 'category': 'personnel', 'display_order': 5},
        {'code': 'connaissance', 'label_masculin': 'connaissance', 'label_feminin': 'connaissance', 'label_autre': 'connaissance', 'category': 'personnel', 'display_order': 6},
        {'code': 'autre_personnel', 'label_masculin': 'autre', 'label_feminin': 'autre', 'label_autre': 'autre', 'category': 'personnel', 'display_order': 7},
    ]
    
    # Professionnel category
    professionnel_types = [
        {'code': 'collegue', 'label_masculin': 'collègue', 'label_feminin': 'collègue', 'label_autre': 'collègue', 'category': 'professionnel', 'display_order': 1},
        {'code': 'client', 'label_masculin': 'client', 'label_feminin': 'client', 'label_autre': 'client', 'category': 'professionnel', 'display_order': 2},
        {'code': 'fournisseur', 'label_masculin': 'fournisseur', 'label_feminin': 'fournisseur', 'label_autre': 'fournisseur', 'category': 'professionnel', 'display_order': 3},
        {'code': 'autre_pro', 'label_masculin': 'autre', 'label_feminin': 'autre', 'label_autre': 'autre', 'category': 'professionnel', 'display_order': 4},
    ]
    
    all_types = personnel_types + professionnel_types
    
    for rt in all_types:
        connection.execute(
            sa.text("""
                INSERT INTO relation_types (code, label_masculin, label_feminin, label_autre, category, display_order, is_active)
                VALUES (:code, :label_masculin, :label_feminin, :label_autre, :category, :display_order, true)
            """),
            rt
        )
    
    # Migrate existing relation_type data from contacts table
    # Map old string values to new relation_type IDs
    mapping = {
        'époux': 'epoux',
        'épouse': 'epoux',  # épouse maps to epoux (same relation type)
        'fiancé': 'fiance',
        'fiancée': 'fiance',
        'ami': 'ami',
        'amie': 'ami',
        'famille': 'famille',
        'collègue': 'collegue',
        'collegue': 'collegue',  # Handle without accent
        'connaissance': 'connaissance',
        'voisin': 'voisin',
        'voisine': 'voisin',
        'autre': 'autre_personnel',  # Default to personnel
    }
    
    # Get all contacts with relation_type
    result = connection.execute(sa.text("SELECT id, relation_type FROM contacts WHERE relation_type IS NOT NULL"))
    contacts = result.fetchall()
    
    for contact_id, old_relation_type in contacts:
        # Find matching code (case-insensitive, handle variations)
        old_lower = old_relation_type.lower().strip()
        code = None
        
        # Try exact match first
        if old_lower in mapping:
            code = mapping[old_lower]
        else:
            # Try partial matches
            for old_key, new_code in mapping.items():
                if old_key in old_lower or old_lower in old_key:
                    code = new_code
                    break
        
        if code:
            # Get relation_type_id for this code
            rt_result = connection.execute(
                sa.text("SELECT id FROM relation_types WHERE code = :code"),
                {'code': code}
            )
            rt_row = rt_result.fetchone()
            if rt_row:
                rt_id = rt_row[0]
                # Insert into junction table
                try:
                    connection.execute(
                        sa.text("""
                            INSERT INTO contact_relation_types (contact_id, relation_type_id)
                            VALUES (:contact_id, :relation_type_id)
                        """),
                        {'contact_id': contact_id, 'relation_type_id': rt_id}
                    )
                except Exception:
                    # Ignore duplicates
                    pass


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_contact_relation_types_composite', table_name='contact_relation_types')
    op.drop_index('ix_contact_relation_types_type', table_name='contact_relation_types')
    op.drop_index('ix_contact_relation_types_contact', table_name='contact_relation_types')
    op.drop_index('ix_relation_types_is_active', table_name='relation_types')
    op.drop_index('ix_relation_types_code', table_name='relation_types')
    op.drop_index('ix_relation_types_category_order', table_name='relation_types')
    op.drop_index('ix_relation_types_category', table_name='relation_types')
    
    # Drop tables
    op.drop_table('contact_relation_types')
    op.drop_table('relation_types')

