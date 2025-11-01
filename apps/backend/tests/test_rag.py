"""
Tests for RAG context retrieval
"""
import pytest
from sqlalchemy.orm import Session
from services.rag import retrieve_context, find_similar_messages_enhanced
from services.embeddings import store_embedding
from models import Message, Embedding


@pytest.mark.integration
def test_retrieve_context_empty(db: Session):
    """Test RAG retrieval with no messages"""
    context = retrieve_context(db, "test query", user_id=1, limit=5)
    assert "No relevant conversation history found" in context


@pytest.mark.integration
def test_retrieve_context_with_messages(db: Session):
    """Test RAG retrieval with existing messages"""
    # Create a test message
    message = Message(
        content="This is a test message about artificial intelligence",
        sender="test_user",
        timestamp="2024-01-01 10:00:00",
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # Store embedding
    store_embedding(db, message.content, message_id=message.id)
    db.commit()
    
    # Retrieve context
    context = retrieve_context(db, "artificial intelligence", user_id=1, limit=5)
    
    assert "Relevant conversation history" in context
    assert "test message" in context.lower()


@pytest.mark.integration
def test_find_similar_messages_enhanced(db: Session):
    """Test enhanced similarity search"""
    from datetime import datetime
    # Create test messages
    messages_data = [
        ("I love machine learning", "user1"),
        ("Machine learning is fascinating", "user2"),
        ("The weather is nice today", "user3"),
    ]
    
    created_messages = []
    for content, sender in messages_data:
        msg = Message(
            content=content,
            sender=sender,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            source="whatsapp",
            conversation_id="test_conv",
            user_id=1
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        store_embedding(db, content, message_id=msg.id)
        created_messages.append(msg)
    
    db.commit()
    
    # Search for similar messages
    results = find_similar_messages_enhanced(
        db,
        "machine learning algorithms",
        limit=5,
        user_id=1
    )
    
    assert len(results) > 0
    # Messages about machine learning should be found
    found_content = " ".join([r['message'].content for r in results if r['message']])
    assert "machine learning" in found_content.lower()

