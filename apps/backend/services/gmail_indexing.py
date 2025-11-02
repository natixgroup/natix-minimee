"""
Gmail indexing service
Handles indexing of Gmail messages with embeddings, chunking, and summarization
"""
import base64
import email
import email.utils
from email.header import decode_header
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
from models import Message, Embedding, Summary
from services.embeddings import store_embedding
from services.language_detector import detect_language
from services.chunking import create_chunks
from services.summarizer import generate_summaries_sync
from services.logs_service import log_to_db


def extract_email_body(payload: Dict) -> str:
    """
    Extract email body from Gmail API payload
    Handles multipart MIME messages properly
    """
    body = ""
    
    # Check if it's a multipart message
    if 'parts' in payload:
        for part in payload.get('parts', []):
            mime_type = part.get('mimeType', '')
            
            # Prefer text/plain, fallback to text/html
            if mime_type == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    break
            elif mime_type == 'text/html' and not body:
                data = part.get('body', {}).get('data', '')
                if data:
                    # For HTML, we could strip tags, but for now just decode
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    
    # Single part message
    elif payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    elif payload.get('mimeType') == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    
    return body.strip() or "[Email body not parsed]"


def decode_header_value(value: str) -> str:
    """Decode email header value (handles encoding)"""
    if not value:
        return ""
    
    try:
        decoded_parts = decode_header(value)
        decoded = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(encoding or 'utf-8'))
            else:
                decoded.append(part)
        return ''.join(decoded)
    except:
        return value


def index_gmail_thread(
    db: Session,
    thread_id: str,
    messages_data: List[Dict],
    user_id: int
) -> Dict:
    """
    Index a Gmail thread with embeddings and chunks
    Returns stats: messages_indexed, chunks_created, embeddings_created
    """
    stats = {
        'messages_indexed': 0,
        'chunks_created': 0,
        'embeddings_created': 0,
        'summaries_created': 0,
    }
    
    try:
        log_to_db(db, "INFO", f"Indexing Gmail thread {thread_id}", service="gmail_indexing")
        
        # Extract and format messages for indexing
        parsed_messages = []
        message_records = []
        
        for msg_data in messages_data:
            headers = msg_data.get('payload', {}).get('headers', [])
            
            # Extract headers
            from_addr = next((h['value'] for h in headers if h['name'] == 'From'), None)
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), None)
            
            # Decode headers
            from_addr = decode_header_value(from_addr) if from_addr else "unknown"
            subject = decode_header_value(subject) if subject else ""
            
            # Extract body
            payload = msg_data.get('payload', {})
            body = extract_email_body(payload)
            
            # Parse date
            try:
                if date_str:
                    # Parse RFC 2822 date
                    date_tuple = email.utils.parsedate_tz(date_str)
                    if date_tuple:
                        msg_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    else:
                        msg_date = datetime.fromtimestamp(int(msg_data['internalDate']) / 1000)
                else:
                    msg_date = datetime.fromtimestamp(int(msg_data['internalDate']) / 1000)
            except:
                msg_date = datetime.now()
            
            # Find or create message in DB
            message = db.query(Message).filter(
                Message.conversation_id == thread_id,
                Message.source == "gmail",
                Message.timestamp == msg_date
            ).first()
            
            if not message:
                # Create message record
                message = Message(
                    content=body,
                    sender=from_addr,
                    timestamp=msg_date,
                    source="gmail",
                    conversation_id=thread_id,
                    user_id=user_id
                )
                db.add(message)
                db.flush()
            
            # Prepare for chunking
            parsed_messages.append({
                'timestamp': msg_date,
                'sender': from_addr,
                'content': f"Subject: {subject}\n\n{body}" if subject else body,
            })
            
            message_records.append({
                'db_message': message,
                'parsed': {
                    'content': body,
                    'subject': subject,
                },
                'language': detect_language(body),
            })
            
            stats['messages_indexed'] += 1
        
        # Create chunks (3-5 emails per chunk)
        chunks = create_chunks(parsed_messages, min_chunk_size=3, max_chunk_size=5)
        stats['chunks_created'] = len(chunks)
        
        # Update chunks with message IDs
        for chunk in chunks:
            chunk['message_ids'] = [
                message_records[idx]['db_message'].id 
                for idx in chunk['messages']
            ]
        
        # Generate summaries for chunks
        chunks_with_summaries = generate_summaries_sync(chunks, db)
        stats['summaries_created'] = len(chunks_with_summaries)
        
        # Store summaries and generate embeddings
        for chunk in chunks_with_summaries:
            # Store summary in DB
            summary = Summary(
                conversation_id=thread_id,
                summary_text=f"TL;DR: {chunk.get('summary', '')}\nTags: {chunk.get('tags', '')}"
            )
            db.add(summary)
            db.flush()
            
            # Generate embedding for chunk
            chunk_language = detect_language(chunk['text'])
            metadata = {
                'chunk': True,
                'language': chunk_language,
                'message_count': chunk['message_count'],
                'senders': chunk['senders'],
                'tags': chunk.get('tags', ''),
                'source': 'gmail',
                'thread_id': thread_id,
                'conversation_id': thread_id,  # For Gmail, conversation_id = thread_id
            }
            
            embedding = store_embedding(
                db,
                chunk['text'],
                message_id=None,
                metadata=metadata
            )
            db.flush()
            stats['embeddings_created'] += 1
            
            # Create embeddings for individual messages (for backward compatibility)
            # Include sender in text for better RAG search
            chunk_message_ids = chunk.get('message_ids', [])
            for msg_record in message_records:
                if msg_record['db_message'].id in chunk_message_ids:
                    parsed = msg_record['parsed']
                    sender = msg_record['db_message'].sender
                    content = parsed.get('content', '')
                    
                    # Include sender in text for better semantic search
                    text_with_sender = f"{sender}: {content}" if sender else content
                    
                    msg_metadata = {
                        'language': msg_record['language'],
                        'chunk_id': embedding.id,
                        'source': 'gmail',
                        'thread_id': thread_id,
                        'subject': parsed.get('subject', ''),
                    }
                    store_embedding(
                        db,
                        text_with_sender,  # Include sender in vectorized text
                        message_id=msg_record['db_message'].id,
                        metadata=msg_metadata
                    )
                    db.flush()
                    stats['embeddings_created'] += 1
        
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Indexed Gmail thread {thread_id}: {stats['messages_indexed']} messages, "
            f"{stats['chunks_created']} chunks, {stats['embeddings_created']} embeddings",
            service="gmail_indexing"
        )
        
        return stats
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Gmail indexing error: {str(e)}", service="gmail_indexing")
        raise

