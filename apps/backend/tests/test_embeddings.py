"""
Tests for embedding generation and storage
"""
import pytest
from sqlalchemy.orm import Session
from services.embeddings import generate_embedding, store_embedding
from db.database import get_db
from models import Embedding


def test_generate_embedding():
    """Test embedding generation"""
    text = "This is a test message"
    embedding = generate_embedding(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) == 384  # Default dimension
    assert all(isinstance(x, float) for x in embedding)


@pytest.mark.integration
def test_store_embedding(db: Session):
    """Test storing embedding in database"""
    text = "Test message for embedding storage"
    embedding = store_embedding(db, text, message_id=None)
    
    assert embedding.id is not None
    assert embedding.text == text
    assert embedding.vector is not None
    
    # Verify it can be retrieved
    stored = db.query(Embedding).filter(Embedding.id == embedding.id).first()
    assert stored is not None
    assert stored.text == text


def test_embedding_similarity():
    """Test that similar texts produce similar embeddings"""
    text1 = "Hello, how are you?"
    text2 = "Hi, how are you doing?"
    text3 = "What is the weather today?"
    
    emb1 = generate_embedding(text1, db=None)
    emb2 = generate_embedding(text2, db=None)
    emb3 = generate_embedding(text3, db=None)
    
    # Calculate cosine similarity (simplified)
    def cosine_similarity(a, b):
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot_product / (norm_a * norm_b)
    
    sim_12 = cosine_similarity(emb1, emb2)
    sim_13 = cosine_similarity(emb1, emb3)
    
    # Similar texts should have higher similarity
    assert sim_12 > sim_13

