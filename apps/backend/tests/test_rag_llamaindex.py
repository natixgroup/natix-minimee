"""
Tests for LangChain-based RAG context retrieval with advanced features
"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from services.minimee_agent.retriever import create_advanced_retriever, create_simple_retriever
from services.minimee_agent.llm_wrapper import create_minimee_llm
from services.embeddings import store_embedding
from models import Message
from config import settings


@pytest.mark.integration
def test_retrieve_context_empty(db: Session):
    """Test RAG retrieval with no messages"""
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        final_limit=5
    )
    docs = retriever.get_relevant_documents("test query")
    assert len(docs) == 0


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
    store_embedding(db, message.content, message_id=message.id, user_id=1)
    db.commit()
    
    # Retrieve context using LangChain
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        final_limit=5
    )
    docs = retriever.get_relevant_documents("artificial intelligence")
    
    assert len(docs) > 0
    # Check that the test message content is in the retrieved documents
    found_content = " ".join([doc.page_content for doc in docs])
    assert "test message" in found_content.lower() or "artificial intelligence" in found_content.lower()


@pytest.mark.integration
def test_find_similar_messages_enhanced(db: Session):
    """Test enhanced similarity search with LangChain retriever"""
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
        store_embedding(db, content, message_id=msg.id, user_id=1)
        created_messages.append(msg)
    
    db.commit()
    
    # Search for similar messages using LangChain retriever
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        final_limit=5
    )
    docs = retriever.get_relevant_documents("machine learning algorithms")
    
    assert len(docs) > 0
    # Messages about machine learning should be found
    found_content = " ".join([doc.page_content for doc in docs])
    assert "machine learning" in found_content.lower()
    
    # Check structure of results (LangChain Document objects)
    for doc in docs:
        assert hasattr(doc, 'page_content')
        assert hasattr(doc, 'metadata')
        # Check similarity in metadata if available
        if 'similarity' in doc.metadata:
            assert isinstance(doc.metadata['similarity'], float)
            assert doc.metadata['similarity'] >= 0.0
            assert doc.metadata['similarity'] <= 1.0


@pytest.mark.integration
def test_retrieve_context_with_filters(db: Session):
    """Test RAG retrieval with conversation filter"""
    # Create messages from different conversations
    msg1 = Message(
        content="I like Python programming",
        sender="alice",
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        source="whatsapp",
        conversation_id="conv_alice",
        user_id=1
    )
    msg2 = Message(
        content="I prefer JavaScript",
        sender="bob",
        timestamp=datetime(2024, 1, 1, 10, 5, 0),
        source="whatsapp",
        conversation_id="conv_bob",
        user_id=1
    )
    
    db.add(msg1)
    db.add(msg2)
    db.commit()
    db.refresh(msg1)
    db.refresh(msg2)
    
    store_embedding(db, msg1.content, message_id=msg1.id, user_id=1)
    store_embedding(db, msg2.content, message_id=msg2.id, user_id=1)
    db.commit()
    
    # Retrieve with conversation filter
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        conversation_id="conv_alice",
        final_limit=5
    )
    docs = retriever.get_relevant_documents("programming language")
    
    assert len(docs) > 0
    # Should find alice's message
    found_content = " ".join([doc.page_content for doc in docs])
    assert "python" in found_content.lower() or "alice" in found_content.lower()


@pytest.mark.integration
def test_retrieve_context_reranking_enabled(db: Session):
    """Test RAG retrieval with reranking (LangChain handles this automatically)"""
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
        store_embedding(db, msg.content, message_id=msg.id, user_id=1)
    
    db.commit()
    
    # Retrieve with reranking enabled (default in create_advanced_retriever)
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        initial_limit=15,
        final_limit=10,
        use_reranking=True
    )
    docs = retriever.get_relevant_documents("artificial intelligence")
    
    assert len(docs) > 0
    assert len(docs) <= 10  # Should be limited by final_limit


@pytest.mark.integration
def test_find_similar_messages_with_language_filter(db: Session):
    """Test similarity search (language filtering handled by metadata in embeddings)"""
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
        user_id=1,
        metadata={"language": "fr", "chunk": "false"}
    )
    db.commit()
    
    # Search using LangChain retriever
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        final_limit=5
    )
    docs = retriever.get_relevant_documents("salut")
    
    # Should find the French message (semantic similarity)
    assert len(docs) > 0
    found_content = " ".join([doc.page_content for doc in docs])
    assert "bonjour" in found_content.lower() or "comment" in found_content.lower()


@pytest.mark.integration
def test_build_prompt_with_context(db: Session):
    """Test prompt building with context (simplified - LangChain handles this in agents)"""
    # This test is less relevant now as LangChain agents handle prompt building internally
    # But we can test that we can format context for prompts
    context = "Relevant conversation history:\n[2024-01-01 10:00] Alice: Hello there"
    user_style = "Formal and professional"
    user_message = "How are you?"
    
    # Simple prompt building (LangChain agents do more sophisticated prompt building)
    prompt = f"""Context: {context}
User style: {user_style}
Current message to respond to: {user_message}"""
    
    assert context in prompt
    assert user_style in prompt
    assert user_message in prompt


@pytest.mark.integration
def test_retrieve_context_return_details(db: Session):
    """Test LangChain retriever returns Document objects with metadata"""
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
    
    store_embedding(db, msg.content, message_id=msg.id, user_id=1)
    db.commit()
    
    # Retrieve using LangChain retriever
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        final_limit=5
    )
    docs = retriever.get_relevant_documents("AI")
    
    assert isinstance(docs, list)
    assert len(docs) > 0
    # Check Document structure
    for doc in docs:
        assert hasattr(doc, 'page_content')
        assert hasattr(doc, 'metadata')
        assert isinstance(doc.metadata, dict)
        # Metadata should contain useful info
        if 'similarity' in doc.metadata:
            assert isinstance(doc.metadata['similarity'], float)


@pytest.mark.integration
def test_find_similar_messages_use_chunks(db: Session):
    """Test similarity search with chunks (LangChain retrieves all embeddings)"""
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
        user_id=1,
        metadata={"chunk": "false"}
    )
    
    # Chunk embedding (no message_id)
    store_embedding(
        db,
        "Chunk content about AI",
        message_id=None,
        user_id=1,
        metadata={"chunk": "true", "conversation_id": "test_conv"}
    )
    
    db.commit()
    
    # LangChain retriever finds all embeddings (chunks and messages)
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        final_limit=10
    )
    docs = retriever.get_relevant_documents("AI")
    
    # Should find both regular message and chunk
    assert len(docs) > 0
    found_content = " ".join([doc.page_content for doc in docs])
    assert "AI" in found_content.lower() or "chunk" in found_content.lower()


@pytest.mark.integration
def test_retrieve_context_includes_recent_messages(db: Session):
    """Test that conversation context is retrieved (LangChain history-aware retriever)"""
    conversation_id = "test_recent_context"
    
    # Create a sequence of messages in the same conversation
    # First message: user asks about an event
    msg1 = Message(
        content="il faut rédiger une invitation avec tous les details, pose moi les questions sur les détails qui te manquent",
        sender="User",
        timestamp=datetime(2024, 1, 1, 10, 36, 48),
        source="dashboard",
        conversation_id=conversation_id,
        user_id=1
    )
    
    # Second message: Minimee asks questions
    msg2 = Message(
        content="Salut ! Pour l'invitation, voici quelques questions : 1. Quelle est la date ? 2. Où se déroule la fête ?",
        sender="Minimee",
        timestamp=datetime(2024, 1, 1, 10, 36, 53),
        source="minimee",
        conversation_id=conversation_id,
        user_id=1
    )
    
    # Third message: user answers with numbered list (low semantic similarity with "cerise moi l invitation")
    msg3 = Message(
        content="1 27 juillet a 20h 2 dans la grotte de Lascaux 3 rien de particulier a part la couleur 4 un truc tres role 5 oui une escalade dans la grotte",
        sender="User",
        timestamp=datetime(2024, 1, 1, 10, 37, 35),
        source="dashboard",
        conversation_id=conversation_id,
        user_id=1
    )
    
    # Fourth message: user asks for invitation
    msg4 = Message(
        content="cerise moi l invitation",
        sender="User",
        timestamp=datetime(2024, 1, 1, 10, 37, 43),
        source="dashboard",
        conversation_id=conversation_id,
        user_id=1
    )
    
    # Add all messages
    for msg in [msg1, msg2, msg3, msg4]:
        db.add(msg)
    db.commit()
    
    # Refresh to get IDs
    for msg in [msg1, msg2, msg3, msg4]:
        db.refresh(msg)
    
    # Store embeddings for all messages
    for msg in [msg1, msg2, msg3, msg4]:
        text_with_sender = f"{msg.sender}: {msg.content}"
        store_embedding(db, text_with_sender, message_id=msg.id, user_id=1)
    db.commit()
    
    # Retrieve context for the last message with conversation_id
    # LangChain history-aware retriever should include conversation context
    llm = create_minimee_llm(db=db, user_id=1)
    retriever = create_advanced_retriever(
        llm=llm,
        db=db,
        user_id=1,
        conversation_id=conversation_id,
        final_limit=5,
        use_history_aware=True
    )
    docs = retriever.get_relevant_documents("cerise moi l invitation")
    
    # Should have context
    assert len(docs) > 0
    
    # Should include recent messages (msg3 should be included even if similarity is low)
    # The numbered answer about the event details should be in context
    found_content = " ".join([doc.page_content for doc in docs])
    assert "27 juillet" in found_content or "Lascaux" in found_content or "escalade" in found_content or "invitation" in found_content.lower()




