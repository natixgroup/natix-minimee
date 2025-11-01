"""
Enhanced ingestion service
Orchestrates the full ingestion pipeline: parse → chunk → embed → summarize
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Optional
from models import Message, Summary, Embedding
from services.whatsapp_parser import parse_whatsapp_export
from services.language_detector import detect_language
from services.chunking import create_chunks
from services.embeddings import store_embedding
from services.summarizer import generate_summaries_sync
from services.logs_service import log_to_db


def ingest_whatsapp_file(
    db: Session,
    file_content: str,
    user_id: int,
    conversation_id: Optional[str] = None
) -> Dict:
    """
    Complete ingestion pipeline for WhatsApp file
    
    Returns:
        {
            'messages_created': int,
            'chunks_created': int,
            'summaries_created': int,
            'embeddings_created': int,
            'conversation_id': str
        }
    """
    if not conversation_id:
        conversation_id = f"whatsapp_{datetime.now().timestamp()}"
    
    stats = {
        'messages_created': 0,
        'chunks_created': 0,
        'summaries_created': 0,
        'embeddings_created': 0,
        'conversation_id': conversation_id,
    }
    
    try:
        log_to_db(db, "INFO", "Starting WhatsApp ingestion", service="ingestion")
        
        # Step 1: Parse WhatsApp file
        parsed_messages = parse_whatsapp_export(file_content)
        log_to_db(db, "INFO", f"Parsed {len(parsed_messages)} messages", service="ingestion")
        
        if not parsed_messages:
            return stats
        
        # Step 2: Detect language and create message records
        message_records = []
        for parsed_msg in parsed_messages:
            language = detect_language(parsed_msg['content'])
            
            msg = Message(
                content=parsed_msg['content'],
                sender=parsed_msg['sender'],
                timestamp=parsed_msg['timestamp'],
                source="whatsapp",
                conversation_id=conversation_id,
                user_id=user_id
            )
            db.add(msg)
            db.flush()
            
            # Store language in embedding metadata later
            message_records.append({
                'db_message': msg,
                'parsed': parsed_msg,
                'language': language,
            })
            stats['messages_created'] += 1
        
        db.commit()
        log_to_db(db, "INFO", f"Created {stats['messages_created']} messages in DB", service="ingestion")
        
        # Step 3: Create chunks (3-5 messages per chunk)
        chunks = create_chunks(parsed_messages, min_chunk_size=3, max_chunk_size=5)
        
        # Update chunks with message IDs
        for chunk in chunks:
            chunk['message_ids'] = [
                message_records[idx]['db_message'].id 
                for idx in chunk['messages']
            ]
        
        stats['chunks_created'] = len(chunks)
        log_to_db(db, "INFO", f"Created {len(chunks)} chunks", service="ingestion")
        
        # Step 4: Generate summaries for chunks
        chunks_with_summaries = generate_summaries_sync(chunks, db)
        stats['summaries_created'] = len(chunks_with_summaries)
        
        # Step 5: Store summaries and generate embeddings for chunks
        for chunk in chunks_with_summaries:
            # Store summary in DB
            summary = Summary(
                conversation_id=conversation_id,
                summary_text=f"TL;DR: {chunk.get('summary', '')}\nTags: {chunk.get('tags', '')}"
            )
            db.add(summary)
            db.flush()
            
            # Generate embedding for chunk with metadata
            chunk_language = detect_language(chunk['text'])
            metadata = {
                'chunk': True,
                'language': chunk_language,
                'message_count': chunk['message_count'],
                'senders': chunk['senders'],
                'tags': chunk.get('tags', ''),
            }
            
            # Store chunk embedding
            embedding = store_embedding(
                db,
                chunk['text'],
                message_id=None,  # Chunks don't link to single message
                metadata=metadata
            )
            stats['embeddings_created'] += 1
            
            # Also create embeddings for individual messages (for backward compatibility)
            for msg_record in message_records:
                if msg_record['db_message'].id in chunk.get('message_ids', []):
                    msg_metadata = {
                        'language': msg_record['language'],
                        'chunk_id': embedding.id,  # Link to chunk
                    }
                    store_embedding(
                        db,
                        msg_record['parsed']['content'],
                        message_id=msg_record['db_message'].id,
                        metadata=msg_metadata
                    )
                    stats['embeddings_created'] += 1
        
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Ingestion complete: {stats['messages_created']} messages, "
            f"{stats['chunks_created']} chunks, {stats['summaries_created']} summaries, "
            f"{stats['embeddings_created']} embeddings",
            service="ingestion"
        )
        
        return stats
    
    except Exception as e:
        db.rollback()
        error_msg = f"WhatsApp ingestion error: {str(e)}"
        log_to_db(db, "ERROR", error_msg, service="ingestion")
        raise

