"""
Gmail indexing service
Handles indexing of Gmail messages with embeddings, chunking, and summarization
"""
import base64
import email
import email.utils
from email.header import decode_header
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Callable
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
    user_id: int,
    progress_callback: Optional[Callable[[str, Dict], None]] = None
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
    
    def _emit_progress(step: str, data: Dict):
        """Helper to emit progress via callback"""
        if progress_callback:
            progress_callback(step, data)
    
    try:
        log_to_db(db, "INFO", f"Indexing Gmail thread {thread_id}", service="gmail_indexing")
        
        total_messages = len(messages_data)
        
        # Extract and format messages for indexing
        parsed_messages = []
        message_records = []
        
        for msg_idx, msg_data in enumerate(messages_data):
            headers = msg_data.get('payload', {}).get('headers', [])
            
            # Extract headers
            from_addr = next((h['value'] for h in headers if h['name'] == 'From'), None)
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), None)
            
            # Decode headers
            from_addr = decode_header_value(from_addr) if from_addr else "unknown"
            subject = decode_header_value(subject) if subject else ""
            
            # Emit progress for message being processed
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Processing message {msg_idx + 1}/{total_messages}...",
                "indexing_log": {
                    "thread_id": thread_id,
                    "message_index": msg_idx + 1,
                    "total_messages": total_messages,
                    "from": from_addr,
                    "subject": subject or "(No subject)",
                    "status": "processing"
                }
            })
            
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
            
            # Emit completion for message
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Processed message {msg_idx + 1}/{total_messages}",
                "indexing_log": {
                    "thread_id": thread_id,
                    "message_index": msg_idx + 1,
                    "total_messages": total_messages,
                    "from": from_addr,
                    "subject": subject or "(No subject)",
                    "status": "processed"
                }
            })
        
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
        import time
        summary_start_time = time.time()
        _emit_progress("indexing", {
            "step": "indexing",
            "message": f"Generating summaries for {len(chunks)} chunks...",
            "indexing_log": {
                "thread_id": thread_id,
                "chunks_count": len(chunks),
                "status": "summarizing",
                "start_time": summary_start_time
            }
        })
        log_to_db(db, "INFO", f"Generating summaries for {len(chunks)} chunks in thread {thread_id}...", service="gmail_indexing")
        
        # Track summary progress with timer
        def summary_progress_callback(current: int, total: int):
            elapsed = time.time() - summary_start_time
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Generating summaries for {len(chunks)} chunks... ({current}/{total})",
                "indexing_log": {
                    "thread_id": thread_id,
                    "chunks_count": len(chunks),
                    "current_summary": current,
                    "total_summaries": total,
                    "elapsed_seconds": int(elapsed),
                    "status": "summarizing"
                }
            })
        
        try:
            chunks_with_summaries = generate_summaries_sync(chunks, db, progress_callback=summary_progress_callback)
            stats['summaries_created'] = len(chunks_with_summaries)
            log_to_db(db, "INFO", f"Generated {len(chunks_with_summaries)} summaries for thread {thread_id}", service="gmail_indexing")
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Generated {len(chunks_with_summaries)} summaries",
                "indexing_log": {
                    "thread_id": thread_id,
                    "summaries_count": len(chunks_with_summaries),
                    "status": "summaries_complete"
                }
            })
        except Exception as e:
            log_to_db(db, "ERROR", f"Failed to generate summaries for thread {thread_id}: {str(e)}", service="gmail_indexing")
            # Continue without summaries - embeddings are more important
            chunks_with_summaries = chunks
            stats['summaries_created'] = 0
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Summary generation failed, continuing without summaries",
                "indexing_log": {
                    "thread_id": thread_id,
                    "status": "summaries_skipped",
                    "error": str(e)[:100]  # Truncate error message
                }
            })
        
        # Store summaries and generate embeddings
        _emit_progress("indexing", {
            "step": "indexing",
            "message": f"Generating embeddings for {len(chunks_with_summaries)} chunks...",
            "indexing_log": {
                "thread_id": thread_id,
                "chunks_count": len(chunks_with_summaries),
                "status": "embedding"
            }
        })
        log_to_db(db, "INFO", f"Generating embeddings for {len(chunks_with_summaries)} chunks in thread {thread_id}...", service="gmail_indexing")
        for chunk_idx, chunk in enumerate(chunks_with_summaries):
            # Emit progress for each chunk
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Embedding chunk {chunk_idx + 1}/{len(chunks_with_summaries)}...",
                "indexing_log": {
                    "thread_id": thread_id,
                    "chunk_index": chunk_idx + 1,
                    "total_chunks": len(chunks_with_summaries),
                    "message_count": chunk.get('message_count', 0),
                    "status": "embedding_chunk"
                }
            })
            if chunk_idx % 5 == 0:  # Log every 5 chunks
                log_to_db(db, "INFO", f"Processing chunk {chunk_idx + 1}/{len(chunks_with_summaries)} for thread {thread_id}...", service="gmail_indexing")
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
            
            # Emit progress for chunk embedding completion
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Chunk {chunk_idx + 1}/{len(chunks_with_summaries)} embedded",
                "indexing_log": {
                    "thread_id": thread_id,
                    "chunk_index": chunk_idx + 1,
                    "total_chunks": len(chunks_with_summaries),
                    "embeddings_created": stats['embeddings_created'],
                    "status": "chunk_embedded"
                }
            })
            
            # Create embeddings for individual messages (for backward compatibility)
            # Include sender in text for better RAG search
            chunk_message_ids = chunk.get('message_ids', [])
            for msg_idx_in_chunk, msg_record in enumerate(message_records):
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
                    
                    # Emit progress for message embedding (every 3rd message to avoid spam)
                    if msg_idx_in_chunk % 3 == 0:
                        _emit_progress("indexing", {
                            "step": "indexing",
                            "message": f"Embedding messages in chunk {chunk_idx + 1}...",
                            "indexing_log": {
                                "thread_id": thread_id,
                                "chunk_index": chunk_idx + 1,
                                "message_in_chunk": msg_idx_in_chunk + 1,
                                "sender": sender[:50] if sender else "unknown",
                                "status": "embedding_message"
                            }
                        })
        
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

