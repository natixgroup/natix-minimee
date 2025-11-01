"""
Tests for WhatsApp ingestion
"""
import pytest
from sqlalchemy.orm import Session
from services.ingestion import ingest_whatsapp_file
from models import Message, Embedding


@pytest.mark.integration
def test_ingest_whatsapp_file(db: Session):
    """Test WhatsApp file ingestion"""
    whatsapp_content = """[01/01/2024, 10:00:00] Alice: Hello, how are you?
[01/01/2024, 10:00:15] Bob: I'm doing great! Thanks for asking.
[01/01/2024, 10:00:30] Alice: That's wonderful to hear.
[01/01/2024, 10:00:45] Bob: Yes, I'm very excited about the project.
[01/01/2024, 10:01:00] Alice: Me too! Let's discuss the details.
[01/01/2024, 10:01:15] Bob: Sounds good. When can we meet?
"""
    
    stats = ingest_whatsapp_file(db, whatsapp_content, user_id=1)
    
    assert stats['messages_created'] > 0
    assert stats['chunks_created'] > 0
    assert stats['embeddings_created'] > 0
    assert stats['summaries_created'] > 0
    
    # Verify messages were created
    messages = db.query(Message).filter(
        Message.source == "whatsapp",
        Message.user_id == 1
    ).all()
    
    assert len(messages) == stats['messages_created']


@pytest.mark.integration
def test_ingest_whatsapp_emojis(db: Session):
    """Test ingestion preserves emojis"""
    whatsapp_content = """[01/01/2024, 10:00:00] User: Hello! 😊🎉
[01/01/2024, 10:00:15] Friend: Great! 🚀✨
"""
    
    stats = ingest_whatsapp_file(db, whatsapp_content, user_id=1)
    
    # Check messages contain emojis
    messages = db.query(Message).filter(
        Message.source == "whatsapp",
        Message.user_id == 1
    ).all()
    
    assert len(messages) > 0
    # At least one message should contain emoji
    has_emoji = any("😊" in msg.content or "🎉" in msg.content or "🚀" in msg.content for msg in messages)
    assert has_emoji

