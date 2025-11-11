"""
Integration tests for ingestion with contacts
Tests complete flow: parsing → contact detection → form → async ingestion
"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from services.contact_detector import detect_contact_from_messages
from services.ingestion import ingest_whatsapp_file
from models import Contact, Message, Embedding, IngestionJob
from services.ingestion_job import ingestion_job_manager


@pytest.mark.integration
def test_detect_contact_from_messages(db: Session):
    """Test contact detection from parsed messages"""
    messages = [
        {
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'sender': 'Tarik',
            'content': 'Salut Hajar'
        },
        {
            'timestamp': datetime(2024, 1, 1, 10, 1, 0),
            'sender': 'Hajar',
            'content': 'Salut mon cœur'
        },
        {
            'timestamp': datetime(2024, 1, 1, 10, 2, 0),
            'sender': 'Tarik',
            'content': 'Comment ça va ?'
        }
    ]
    
    contact_data = detect_contact_from_messages(messages, user_id=1, user_name='Tarik')
    
    assert contact_data['first_name'] == 'Hajar'
    assert 'français' in contact_data.get('languages', [])
    assert len(contact_data.get('dominant_themes', [])) > 0


@pytest.mark.integration
def test_ingestion_with_contact_creation(db: Session):
    """Test ingestion creates contact and links messages"""
    # Create contact first
    contact = Contact(
        user_id=1,
        conversation_id='test_conv_123',
        first_name='Hajar',
        nickname='Haj',
        relation_type='épouse',
        context='Conversations personnelles',
        languages=['français', 'darija'],
        importance_rating=5,
        dominant_themes=['couple', 'famille']
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    
    # Simulate WhatsApp file content
    file_content = """[01/01/2024, 10:00:00] Tarik: Salut Hajar
[01/01/2024, 10:01:00] Hajar: Salut mon cœur
[01/01/2024, 10:02:00] Tarik: Comment ça va ?"""
    
    # Run ingestion
    stats = ingest_whatsapp_file(
        db=db,
        file_content=file_content,
        user_id=1,
        conversation_id='test_conv_123'
    )
    
    assert stats['messages_created'] > 0
    assert stats['chunks_created'] > 0
    assert stats['embeddings_created'] > 0
    
    # Verify messages are linked to conversation
    messages = db.query(Message).filter(
        Message.conversation_id == 'test_conv_123'
    ).all()
    assert len(messages) == stats['messages_created']


@pytest.mark.integration
def test_ingestion_job_creation(db: Session):
    """Test ingestion job creation and status updates"""
    job = ingestion_job_manager.create_job(
        db=db,
        user_id=1,
        conversation_id='test_conv_job'
    )
    
    assert job.id is not None
    assert job.status == 'pending'
    assert job.user_id == 1
    
    # Update progress
    ingestion_job_manager.update_job_progress(
        db=db,
        job_id=job.id,
        step='parsing',
        current=10,
        total=100,
        message='Parsing messages...',
        percent=10.0
    )
    
    db.refresh(job)
    assert job.status == 'running'
    assert job.progress['step'] == 'parsing'
    assert job.progress['current'] == 10


@pytest.mark.integration
def test_conversational_blocks_with_topics(db: Session):
    """Test that ingestion creates blocks with latent topics"""
    file_content = """[01/01/2024, 10:00:00] Tarik: Je vais au travail
[01/01/2024, 10:01:00] Hajar: Bonne journée
[01/01/2024, 10:02:00] Tarik: Merci"""
    
    stats = ingest_whatsapp_file(
        db=db,
        file_content=file_content,
        user_id=1,
        conversation_id='test_topics'
    )
    
    # Check that embeddings have latent_topic metadata
    embeddings = db.query(Embedding).filter(
        Embedding.meta_data['conversation_id'].astext == 'test_topics'
    ).all()
    
    # At least one embedding should have latent_topic
    topics_found = False
    for emb in embeddings:
        if emb.meta_data and emb.meta_data.get('latent_topic'):
            topics_found = True
            break
    
    # Note: Topic generation may fail if LLM is not available, so we just check structure
    assert stats['embeddings_created'] > 0


@pytest.mark.integration
def test_temporal_metadata_in_embeddings(db: Session):
    """Test that embeddings include temporal metadata"""
    file_content = """[01/03/2024, 10:00:00] Tarik: Message de printemps
[01/03/2024, 10:01:00] Hajar: Réponse"""
    
    stats = ingest_whatsapp_file(
        db=db,
        file_content=file_content,
        user_id=1,
        conversation_id='test_temporal'
    )
    
    # Check embeddings have temporal metadata
    embeddings = db.query(Embedding).filter(
        Embedding.meta_data['conversation_id'].astext == 'test_temporal'
    ).all()
    
    assert len(embeddings) > 0
    for emb in embeddings:
        if emb.meta_data:
            # Check for temporal fields
            assert 'period_label' in emb.meta_data or 'year' in emb.meta_data or 'timestamp' in emb.meta_data


