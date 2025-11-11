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
from models import Message, Embedding
from services.embeddings import store_embedding
from services.language_detector import detect_language
from services.conversational_chunking import create_conversational_blocks
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
        
        # Create conversational blocks (temporal/logical grouping)
        blocks = create_conversational_blocks(
            parsed_messages,
            time_window_minutes=20,
            silence_threshold_hours=1.0
        )
        stats['chunks_created'] = len(blocks)
        
        # Update blocks with message IDs
        for block in blocks:
            block['message_ids'] = [
                message_records[idx]['db_message'].id 
                for idx in block['messages']
            ]
        
        # Generate embeddings for conversational blocks (no summaries for now - can be added later if needed)
        blocks_with_embeddings = blocks
        
        # Store embeddings for blocks
        _emit_progress("indexing", {
            "step": "indexing",
            "message": f"Generating embeddings for {len(blocks_with_embeddings)} conversational blocks...",
            "indexing_log": {
                "thread_id": thread_id,
                "blocks_count": len(blocks_with_embeddings),
                "status": "embedding"
            }
        })
        log_to_db(db, "INFO", f"Generating embeddings for {len(blocks_with_embeddings)} conversational blocks in thread {thread_id}...", service="gmail_indexing")
        for block_idx, block in enumerate(blocks_with_embeddings):
            # Emit progress for each block
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Embedding block {block_idx + 1}/{len(blocks_with_embeddings)}...",
                "indexing_log": {
                    "thread_id": thread_id,
                    "block_index": block_idx + 1,
                    "total_blocks": len(blocks_with_embeddings),
                    "message_count": block.get('message_count', 0),
                    "status": "embedding_block"
                }
            })
            if block_idx % 5 == 0:  # Log every 5 blocks
                log_to_db(db, "INFO", f"Processing block {block_idx + 1}/{len(blocks_with_embeddings)} for thread {thread_id}...", service="gmail_indexing")
            
            # Generate embedding for conversational block
            block_language = detect_language(block['text'])
            
            # Build standardized metadata
            metadata = {
                'chunk': True,
                'language': block_language,
                'message_count': block['message_count'],
                'participants': block.get('participants', []),
                'source': 'gmail',
                'thread_id': thread_id,
                'conversation_id': thread_id,  # For Gmail, conversation_id = thread_id
                'start_timestamp': block.get('start_timestamp').isoformat() if block.get('start_timestamp') else None,
                'end_timestamp': block.get('end_timestamp').isoformat() if block.get('end_timestamp') else None,
                'duration_minutes': block.get('duration_minutes'),
                'user_id': user_id,
            }
            
            embedding = store_embedding(
                db,
                block['text'],
                message_id=None,
                metadata=metadata,
                user_id=user_id
            )
            db.flush()
            stats['embeddings_created'] += 1
            
            # Emit progress for block embedding completion
            _emit_progress("indexing", {
                "step": "indexing",
                "message": f"Block {block_idx + 1}/{len(blocks_with_embeddings)} embedded",
                "indexing_log": {
                    "thread_id": thread_id,
                    "block_index": block_idx + 1,
                    "total_blocks": len(blocks_with_embeddings),
                    "embeddings_created": stats['embeddings_created'],
                    "status": "block_embedded"
                }
            })
            
            # NOTE: We no longer create individual message embeddings to avoid redundancy
            # The conversational blocks contain all the context needed for RAG
        
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

