"""add_action_logs

Revision ID: 002
Revises: 001
Create Date: 2024-12-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create action_logs table if it doesn't exist
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'action_logs' not in inspector.get_table_names():
        op.create_table(
        'action_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),  # message_arrived, vectorization, semantic_search, prompt_building, llm_call, response_options, user_presentation, user_response, action_executed
        sa.Column('duration_ms', sa.Float(), nullable=True),  # Temps pris en millisecondes
        sa.Column('model', sa.String(), nullable=True),  # Modèle utilisé (embedding model, LLM model, etc.)
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Données d'entrée (message, query, prompt, etc.)
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Données de sortie (embedding, results, response, etc.)
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Métadonnées supplémentaires
        sa.Column('message_id', sa.Integer(), nullable=True),  # ID du message associé
        sa.Column('conversation_id', sa.String(), nullable=True),  # ID de la conversation
        sa.Column('request_id', sa.String(), nullable=True),  # ID de la requête (pour tracer un flux complet)
        sa.Column('user_id', sa.Integer(), nullable=True),  # ID de l'utilisateur
        sa.Column('source', sa.String(), nullable=True),  # 'whatsapp', 'gmail', etc.
        sa.Column('status', sa.String(), nullable=True),  # 'success', 'error', 'pending'
        sa.Column('error_message', sa.Text(), nullable=True),  # Message d'erreur si status=error
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_action_logs_id'), 'action_logs', ['id'], unique=False)
        op.create_index(op.f('ix_action_logs_action_type'), 'action_logs', ['action_type'], unique=False)
        op.create_index(op.f('ix_action_logs_message_id'), 'action_logs', ['message_id'], unique=False)
        op.create_index(op.f('ix_action_logs_conversation_id'), 'action_logs', ['conversation_id'], unique=False)
        op.create_index(op.f('ix_action_logs_request_id'), 'action_logs', ['request_id'], unique=False)
        op.create_index(op.f('ix_action_logs_user_id'), 'action_logs', ['user_id'], unique=False)
        op.create_index(op.f('ix_action_logs_timestamp'), 'action_logs', ['timestamp'], unique=False)
        # Index composite pour requêtes fréquentes
        op.create_index('ix_action_logs_request_timestamp', 'action_logs', ['request_id', 'timestamp'], unique=False)


def downgrade() -> None:
    op.drop_table('action_logs')

