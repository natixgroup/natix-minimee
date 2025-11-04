"""
Tests for LlamaIndex-based RAG context retrieval with reranking
"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from services.rag_llamaindex import retrieve_context, find_similar_messages_enhanced, build_prompt_with_context
from services.embeddings import store_embedding
from models import Message
from config import settings


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
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
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
    """Test enhanced similarity search with filters"""
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
    
    # Check structure of results
    for result in results:
        assert 'message' in result
        assert 'similarity' in result
        assert isinstance(result['similarity'], float)
        assert result['similarity'] >= 0.0
        assert result['similarity'] <= 1.0


@pytest.mark.integration
def test_retrieve_context_with_filters(db: Session):
    """Test RAG retrieval with sender filter"""
    # Create messages from different senders
    msg1 = Message(
        content="I like Python programming",
        sender="alice",
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    msg2 = Message(
        content="I prefer JavaScript",
        sender="bob",
        timestamp=datetime(2024, 1, 1, 10, 5, 0),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    
    db.add(msg1)
    db.add(msg2)
    db.commit()
    db.refresh(msg1)
    db.refresh(msg2)
    
    store_embedding(db, msg1.content, message_id=msg1.id)
    store_embedding(db, msg2.content, message_id=msg2.id)
    db.commit()
    
    # Retrieve with sender filter
    context, details = retrieve_context(
        db,
        "programming language",
        user_id=1,
        limit=5,
        sender="alice",
        return_details=True
    )
    
    assert "Relevant conversation history" in context
    assert "alice" in context.lower()
    assert details["results_count"] > 0


@pytest.mark.integration
def test_retrieve_context_reranking_enabled(db: Session):
    """Test RAG retrieval with reranking when limit > 10"""
    # Create multiple test messages
    for i in range(15):
        msg = Message(
            content=f"Test message {i} about artificial intelligence and machine learning",
            sender=f"user{i}",
            timestamp=datetime(2024, 1, 1, 10, i, 0),
            source="whatsapp",
            conversation_id="test_conv",
            user_id=1
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        store_embedding(db, msg.content, message_id=msg.id)
    
    db.commit()
    
    # Retrieve with limit > 10 to trigger reranking
    context, details = retrieve_context(
        db,
        "artificial intelligence",
        user_id=1,
        limit=15,
        return_details=True
    )
    
    assert "Relevant conversation history" in context
    assert details["results_count"] > 0
    # Check if reranking was applied (if enabled)
    if settings.rag_rerank_enabled:
        assert details.get("reranked", False) is True


@pytest.mark.integration
def test_find_similar_messages_with_language_filter(db: Session):
    """Test similarity search with language filter"""
    # Create messages with language metadata
    msg1 = Message(
        content="Bonjour, comment allez-vous?",
        sender="user1",
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    
    db.add(msg1)
    db.commit()
    db.refresh(msg1)
    
    # Store embedding with language metadata
    store_embedding(
        db,
        msg1.content,
        message_id=msg1.id,
        metadata={"language": "fr", "chunk": "false"}
    )
    db.commit()
    
    # Search with language filter
    results = find_similar_messages_enhanced(
        db,
        "salut",
        limit=5,
        user_id=1,
        language="fr"
    )
    
    # Should find the French message
    assert len(results) > 0


@pytest.mark.integration
def test_build_prompt_with_context(db: Session):
    """Test prompt building with context"""
    context = "Relevant conversation history:\n[2024-01-01 10:00] Alice: Hello there"
    user_style = "Formal and professional"
    
    prompt = build_prompt_with_context("How are you?", context, user_style)
    
    assert context in prompt
    assert user_style in prompt
    assert "How are you?" in prompt
    assert "Current message to respond to" in prompt


@pytest.mark.integration
def test_retrieve_context_return_details(db: Session):
    """Test retrieve_context with return_details=True"""
    # Create test message
    msg = Message(
        content="Test message about AI",
        sender="user1",
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    store_embedding(db, msg.content, message_id=msg.id)
    db.commit()
    
    # Retrieve with details
    context, details = retrieve_context(
        db,
        "AI",
        user_id=1,
        limit=5,
        return_details=True
    )
    
    assert isinstance(context, str)
    assert isinstance(details, dict)
    assert "results_count" in details
    assert "top_similarity" in details
    assert "avg_similarity" in details
    assert "results" in details
    assert isinstance(details["results"], list)


@pytest.mark.integration
def test_find_similar_messages_use_chunks(db: Session):
    """Test similarity search with chunk filtering"""
    # Create a regular message and a chunk
    msg1 = Message(
        content="Regular message",
        sender="user1",
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    
    db.add(msg1)
    db.commit()
    db.refresh(msg1)
    
    # Regular message embedding
    store_embedding(
        db,
        msg1.content,
        message_id=msg1.id,
        metadata={"chunk": "false"}
    )
    
    # Chunk embedding (no message_id)
    store_embedding(
        db,
        "Chunk content about AI",
        message_id=None,
        metadata={"chunk": "true", "conversation_id": "test_conv"}
    )
    
    db.commit()
    
    # Search with use_chunks=True (should find both)
    results_with_chunks = find_similar_messages_enhanced(
        db,
        "AI",
        limit=10,
        user_id=1,
        use_chunks=True
    )
    
    # Search with use_chunks=False (should only find regular messages)
    results_no_chunks = find_similar_messages_enhanced(
        db,
        "AI",
        limit=10,
        user_id=1,
        use_chunks=False
    )
    
    # With chunks, we should get more or equal results
    assert len(results_with_chunks) >= len(results_no_chunks)


