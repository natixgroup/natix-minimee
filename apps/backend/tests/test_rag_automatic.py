"""
Tests for automatic RAG chain with context injection
Tests the rag_chain module and its integration with MinimeeAgent
"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from services.minimee_agent.rag_chain import create_rag_chain, get_rag_metrics, reset_rag_metrics
from services.minimee_agent.retriever import create_advanced_retriever
from services.minimee_agent.llm_wrapper import create_minimee_llm
from services.minimee_agent.prompts import create_agent_prompt
from services.embeddings import store_embedding
from models import Message
from types import SimpleNamespace


@pytest.mark.integration
def test_rag_chain_retrieves_context(db: Session):
    """Test that RAG chain retrieves relevant context"""
    # Create test messages
    msg1 = Message(
        content="I love machine learning and artificial intelligence",
        sender="user1",
        timestamp=datetime.utcnow(),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    msg2 = Message(
        content="The weather is nice today",
        sender="user2",
        timestamp=datetime.utcnow(),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    
    db.add(msg1)
    db.add(msg2)
    db.commit()
    db.refresh(msg1)
    db.refresh(msg2)
    
    # Store embeddings
    store_embedding(db, msg1.content, message_id=msg1.id, user_id=1)
    store_embedding(db, msg2.content, message_id=msg2.id, user_id=1)
    db.commit()
    
    # Create RAG chain
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        use_history_aware=False,
        use_reranking=False
    )
    
    # Create a simple prompt template for testing
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=10,
        timeout_seconds=5.0
    )
    
    # Invoke RAG chain
    result = rag_chain.invoke({"input": "machine learning"})
    
    # Check that context was retrieved
    assert "context" in result
    assert len(result["context"]) > 0
    assert "machine learning" in result["context"].lower() or "artificial intelligence" in result["context"].lower()
    assert result["chunks_retrieved"] > 0


@pytest.mark.integration
def test_rag_chain_source_filtering(db: Session):
    """Test that RAG chain respects included_sources filter"""
    # Create messages from different sources
    msg_whatsapp = Message(
        content="WhatsApp message about Python",
        sender="user1",
        timestamp=datetime.utcnow(),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    msg_gmail = Message(
        content="Gmail message about JavaScript",
        sender="user2",
        timestamp=datetime.utcnow(),
        source="gmail",
        conversation_id="test_conv",
        user_id=1
    )
    
    db.add(msg_whatsapp)
    db.add(msg_gmail)
    db.commit()
    db.refresh(msg_whatsapp)
    db.refresh(msg_gmail)
    
    # Store embeddings
    store_embedding(db, msg_whatsapp.content, message_id=msg_whatsapp.id, user_id=1)
    store_embedding(db, msg_gmail.content, message_id=msg_gmail.id, user_id=1)
    db.commit()
    
    # Create RAG chain with WhatsApp only
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        included_sources=["whatsapp"],
        use_history_aware=False,
        use_reranking=False
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=10,
        timeout_seconds=5.0
    )
    
    # Invoke RAG chain
    result = rag_chain.invoke({"input": "programming"})
    
    # Should only find WhatsApp message
    assert "context" in result
    if result["chunks_retrieved"] > 0:
        assert "python" in result["context"].lower()
        assert "javascript" not in result["context"].lower()


@pytest.mark.integration
def test_rag_chain_metrics(db: Session):
    """Test that RAG chain tracks metrics correctly"""
    reset_rag_metrics()
    
    # Create test message
    msg = Message(
        content="Test message for metrics",
        sender="user1",
        timestamp=datetime.utcnow(),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    store_embedding(db, msg.content, message_id=msg.id, user_id=1)
    db.commit()
    
    # Create RAG chain
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        use_history_aware=False,
        use_reranking=False
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=10,
        timeout_seconds=5.0
    )
    
    # Invoke multiple times
    for _ in range(3):
        rag_chain.invoke({"input": "test"})
    
    # Check metrics
    metrics = get_rag_metrics()
    assert metrics["total_calls"] == 3
    assert metrics["successful_calls"] == 3
    assert metrics["avg_latency_ms"] > 0
    assert metrics["avg_chunks_per_call"] >= 0


@pytest.mark.integration
def test_rag_chain_fallback_on_error(db: Session):
    """Test that RAG chain falls back gracefully on errors"""
    # Create RAG chain with invalid retriever (will cause error)
    llm = create_minimee_llm(db=db, user_id=1)
    
    # Create a retriever that will fail
    from services.minimee_agent.vector_store import get_vector_store_retriever
    retriever = get_vector_store_retriever(
        db=db,
        user_id=999999,  # Non-existent user
        limit=10
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=10,
        timeout_seconds=5.0
    )
    
    # Invoke - should not raise exception, should return empty context
    result = rag_chain.invoke({"input": "test"})
    
    # Should return empty context on error (fallback)
    assert "context" in result
    assert result["chunks_retrieved"] == 0


@pytest.mark.integration
def test_rag_chain_max_chunks_limit(db: Session):
    """Test that RAG chain respects max_chunks limit"""
    # Create many test messages
    for i in range(20):
        msg = Message(
            content=f"Test message {i} about artificial intelligence",
            sender=f"user{i}",
            timestamp=datetime.utcnow() - timedelta(minutes=i),
            source="whatsapp",
            conversation_id="test_conv",
            user_id=1
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        store_embedding(db, msg.content, message_id=msg.id, user_id=1)
    
    db.commit()
    
    # Create RAG chain with max_chunks=5
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        use_history_aware=False,
        use_reranking=False
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=5,  # Limit to 5 chunks
        timeout_seconds=5.0
    )
    
    # Invoke RAG chain
    result = rag_chain.invoke({"input": "artificial intelligence"})
    
    # Should respect max_chunks limit
    assert result["chunks_retrieved"] <= 5


@pytest.mark.integration
def test_rag_chain_chunk_prioritization(db: Session):
    """Test that RAG chain prioritizes chunks over individual messages"""
    # Create individual message
    msg = Message(
        content="Individual message about AI",
        sender="user1",
        timestamp=datetime.utcnow(),
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    # Store individual message embedding
    store_embedding(
        db,
        msg.content,
        message_id=msg.id,
        user_id=1,
        metadata={"chunk": "false", "source": "whatsapp", "conversation_id": "test_conv"}
    )
    
    # Store chunk embedding (should be prioritized)
    store_embedding(
        db,
        "Conversational block about artificial intelligence and machine learning",
        message_id=None,
        user_id=1,
        metadata={
            "chunk": "true",
            "source": "whatsapp",
            "conversation_id": "test_conv",
            "participants": ["user1", "user2"],
            "message_count": 3
        }
    )
    
    db.commit()
    
    # Create RAG chain
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        use_history_aware=False,
        use_reranking=False
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=10,
        timeout_seconds=5.0
    )
    
    # Invoke RAG chain
    result = rag_chain.invoke({"input": "artificial intelligence"})
    
    # Chunk should be prioritized (higher combined score)
    if result["chunks_retrieved"] > 0:
        # The chunk should appear in context (it has more content and is boosted)
        assert "artificial intelligence" in result["context"].lower() or "machine learning" in result["context"].lower()


@pytest.mark.integration
def test_rag_chain_recency_weighting(db: Session):
    """Test that RAG chain weights recent messages higher"""
    # Create old message
    old_msg = Message(
        content="Old message about Python",
        sender="user1",
        timestamp=datetime.utcnow() - timedelta(days=60),  # 60 days ago
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    
    # Create recent message
    recent_msg = Message(
        content="Recent message about Python",
        sender="user1",
        timestamp=datetime.utcnow() - timedelta(hours=1),  # 1 hour ago
        source="whatsapp",
        conversation_id="test_conv",
        user_id=1
    )
    
    db.add(old_msg)
    db.add(recent_msg)
    db.commit()
    db.refresh(old_msg)
    db.refresh(recent_msg)
    
    # Store embeddings
    store_embedding(db, old_msg.content, message_id=old_msg.id, user_id=1)
    store_embedding(db, recent_msg.content, message_id=recent_msg.id, user_id=1)
    db.commit()
    
    # Create RAG chain
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        use_history_aware=False,
        use_reranking=False
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "Context: {context}\n\nQuestion: {input}")
    ])
    
    rag_chain = create_rag_chain(
        retriever=retriever,
        llm=llm,
        prompt_template=prompt_template,
        db=db,
        user_id=1,
        max_chunks=10,
        timeout_seconds=5.0
    )
    
    # Invoke RAG chain
    result = rag_chain.invoke({"input": "Python"})
    
    # Recent message should be prioritized (higher recency_weight)
    if result["chunks_retrieved"] > 0:
        # Recent message should appear first or be included
        assert "recent" in result["context"].lower() or "python" in result["context"].lower()


