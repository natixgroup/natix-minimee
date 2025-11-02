"""
Enhanced ingestion service
Orchestrates the full ingestion pipeline: parse → chunk → embed → summarize
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Optional, Callable
from models import Message, Summary, Embedding
from services.whatsapp_parser import parse_whatsapp_export
from services.language_detector import detect_language
from services.chunking import create_chunks
from services.embeddings import store_embedding
from services.summarizer import generate_summaries_sync
from services.logs_service import log_to_db


def _calculate_progress_percent(step: str, current: int, total: int) -> float:
    """
    Calculate overall progress percentage based on step and current/total
    Step weights:
    - parsing: 0-5%
    - saving_messages: 5-15%
    - chunking: 15-20%
    - summarizing: 20-30%
    - embedding: 30-100%
    """
    step_ranges = {
        "parsing": (0, 5),
        "saving_messages": (5, 15),
        "chunking": (15, 20),
        "summarizing": (20, 30),
        "embedding": (30, 100),
    }
    
    if step not in step_ranges:
        return 0.0
    
    start_percent, end_percent = step_ranges[step]
    step_range = end_percent - start_percent
    
    if total > 0 and current >= 0:
        step_progress = min(1.0, max(0.0, current / total))
    else:
        # If no total, use midpoint of range
        step_progress = 0.5 if current == 0 else 1.0
    
    percent = start_percent + (step_range * step_progress)
    return round(percent, 1)


def ingest_whatsapp_file(
    db: Session,
    file_content: str,
    user_id: int,
    conversation_id: Optional[str] = None,
    progress_callback: Optional[Callable[[str, Dict], None]] = None
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
    
    def _emit_progress(step: str, data: Dict):
        """Helper to emit progress with calculated percentage"""
        if progress_callback:
            current = data.get('current', 0)
            total = data.get('total', 0)
            percent = _calculate_progress_percent(step, current, total)
            data['percent'] = percent
            progress_callback(step, data)
    
    if not conversation_id:
        conversation_id = f"whatsapp_{datetime.now().timestamp()}"
    
    stats = {
        'messages_created': 0,
        'chunks_created': 0,
        'summaries_created': 0,
        'embeddings_created': 0,
        'embeddings_skipped': 0,
        'summaries_skipped': 0,
        'conversation_id': conversation_id,
    }
    
    try:
        log_to_db(db, "INFO", "Starting WhatsApp ingestion", service="ingestion")
        
        _emit_progress("parsing", {"step": "parsing", "message": "Parsing WhatsApp file...", "current": 0, "total": 0})
        
        # Step 1: Parse WhatsApp file
        # Try to get user WhatsApp ID from conversation_id if it matches pattern
        # For WhatsApp exports, conversation_id often contains the contact ID
        user_whatsapp_id = None
        if conversation_id and '@' not in conversation_id:
            # conversation_id might be a phone number, try to construct WhatsApp ID
            # This is a heuristic - in production, get this from user settings or auth
            pass
        
        parsed_messages = parse_whatsapp_export(file_content, user_whatsapp_id=user_whatsapp_id)
        log_to_db(db, "INFO", f"Parsed {len(parsed_messages)} messages", service="ingestion")
        
        # Emit parsing complete immediately
        _emit_progress("parsing", {
            "step": "parsing", 
            "message": f"Parsed {len(parsed_messages)} messages. Starting to save...", 
            "current": len(parsed_messages), 
            "total": len(parsed_messages)
        })
        
        if not parsed_messages:
            return stats
        
        # If conversation_id is a phone number, try to use it as recipient for 1-1 chats
        # This is a fallback if parser couldn't determine recipient
        if conversation_id and '@' not in conversation_id:
            # Check if it's a 1-1 conversation (2 unique senders)
            unique_senders = set(msg['sender'] for msg in parsed_messages)
            if len(unique_senders) == 2:
                # Use conversation_id as recipient hint
                for msg in parsed_messages:
                    if not msg.get('recipient'):
                        # If sender is not the conversation_id, recipient might be conversation_id
                        if conversation_id not in msg['sender']:
                            msg['recipient'] = f"{conversation_id}@s.whatsapp.net"
        
        # Step 2: Detect language and create message records
        _emit_progress("saving_messages", {"step": "saving_messages", "message": "Saving messages to database...", "current": 0, "total": len(parsed_messages)})
        
        message_records = []
        total_messages = len(parsed_messages)
        for idx, parsed_msg in enumerate(parsed_messages):
            language = detect_language(parsed_msg['content'])
            
            msg = Message(
                content=parsed_msg['content'],
                sender=parsed_msg['sender'],
                recipient=parsed_msg.get('recipient'),
                recipients=parsed_msg.get('recipients'),  # JSONB array
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
            
            if progress_callback and (idx + 1) % 10 == 0:  # Update every 10 messages
                _emit_progress("saving_messages", {"step": "saving_messages", "message": f"Saving messages...", "current": idx + 1, "total": total_messages})
        
        db.commit()
        log_to_db(db, "INFO", f"Created {stats['messages_created']} messages in DB", service="ingestion")
        
        _emit_progress("saving_messages", {"step": "saving_messages", "message": f"Saved {stats['messages_created']} messages", "current": stats['messages_created'], "total": stats['messages_created']})
        
        # Step 3: Create chunks (3-5 messages per chunk)
        _emit_progress("chunking", {"step": "chunking", "message": "Creating chunks...", "current": 0, "total": 0})
        
        chunks = create_chunks(parsed_messages, min_chunk_size=3, max_chunk_size=5)
        
        # Update chunks with message IDs
        for chunk in chunks:
            chunk['message_ids'] = [
                message_records[idx]['db_message'].id 
                for idx in chunk['messages']
            ]
        
        stats['chunks_created'] = len(chunks)
        log_to_db(db, "INFO", f"Created {len(chunks)} chunks", service="ingestion")
        
        _emit_progress("chunking", {"step": "chunking", "message": f"Created {stats['chunks_created']} chunks", "current": stats['chunks_created'], "total": stats['chunks_created']})
        
        # Step 4: Generate summaries for chunks (resilient to LLM failures)
        _emit_progress("summarizing", {"step": "summarizing", "message": "Generating summaries...", "current": 0, "total": len(chunks)})
        
        chunks_with_summaries = []
        try:
            chunks_with_summaries = generate_summaries_sync(chunks, db)
            stats['summaries_created'] = len(chunks_with_summaries)
            log_to_db(db, "INFO", f"Generated {stats['summaries_created']} summaries", service="ingestion")
            
            _emit_progress("summarizing", {"step": "summarizing", "message": f"Generated {stats['summaries_created']} summaries", "current": stats['summaries_created'], "total": len(chunks)})
        except Exception as e:
            log_to_db(
                db,
                "WARNING",
                f"Summary generation failed (LLM may not be ready): {str(e)}. Continuing without summaries.",
                service="ingestion"
            )
            # Continue with chunks without summaries
            chunks_with_summaries = chunks.copy()
            stats['summaries_skipped'] = len(chunks)
        
        # Step 5: Store summaries and generate embeddings for chunks (resilient to embedding failures)
        chunks_to_process = chunks_with_summaries if chunks_with_summaries else chunks
        total_chunks = len(chunks_to_process)
        
        _emit_progress("embedding", {"step": "embedding", "message": "Generating embeddings...", "current": 0, "total": total_chunks, "embeddings_created": 0})
        
        chunk_idx = 0
        for chunk in chunks_to_process:
            # Store summary in DB (only if we have one)
            if chunk.get('summary') or chunk.get('tags'):
                try:
                    summary = Summary(
                        conversation_id=conversation_id,
                        summary_text=f"TL;DR: {chunk.get('summary', '')}\nTags: {chunk.get('tags', '')}"
                    )
                    db.add(summary)
                    db.flush()
                except Exception as e:
                    log_to_db(
                        db,
                        "WARNING",
                        f"Failed to store summary for chunk: {str(e)}",
                        service="ingestion"
                    )
            
            # Generate embedding for chunk with metadata (resilient to model failures)
            try:
                chunk_language = detect_language(chunk['text'])
                
                # Extract unique recipients/participants from chunk messages
                chunk_messages = [parsed_messages[idx] for idx in chunk.get('messages', [])]
                chunk_recipients = set()
                chunk_recipient_lists = []
                for msg in chunk_messages:
                    if msg.get('recipient'):
                        chunk_recipients.add(msg['recipient'])
                    if msg.get('recipients'):
                        chunk_recipient_lists.extend(msg['recipients'])
                
                metadata = {
                    'chunk': True,
                    'language': chunk_language,
                    'message_count': chunk['message_count'],
                    'senders': chunk['senders'],
                    'recipients': list(chunk_recipients) if chunk_recipients else None,
                    'recipients_list': sorted(list(set(chunk_recipient_lists))) if chunk_recipient_lists else None,
                    'tags': chunk.get('tags', ''),
                    'source': 'whatsapp',
                }
                
                # Store chunk embedding
                embedding = store_embedding(
                    db,
                    chunk['text'],
                    message_id=None,  # Chunks don't link to single message
                    metadata=metadata
                )
                stats['embeddings_created'] += 1
                
                # Update progress for chunk embedding
                _emit_progress("embedding", {
                    "step": "embedding",
                    "message": f"Vectorizing chunks...",
                    "current": chunk_idx + 1,
                    "total": total_chunks,
                    "embeddings_created": stats['embeddings_created']
                })
                
                # Also create embeddings for individual messages (for backward compatibility)
                msg_embedding_count = 0
                for msg_record in message_records:
                    if msg_record['db_message'].id in chunk.get('message_ids', []):
                        try:
                            parsed = msg_record['parsed']
                            msg_metadata = {
                                'language': msg_record['language'],
                                'chunk_id': embedding.id,  # Link to chunk
                                'sender': parsed.get('sender'),
                                'recipient': parsed.get('recipient'),
                                'recipients': parsed.get('recipients'),
                                'source': 'whatsapp',
                            }
                            store_embedding(
                                db,
                                parsed['content'],
                                message_id=msg_record['db_message'].id,
                                metadata=msg_metadata
                            )
                            stats['embeddings_created'] += 1
                            msg_embedding_count += 1
                            
                            # Update progress for message embeddings (every 5 messages)
                            if progress_callback and msg_embedding_count % 5 == 0:
                                _emit_progress("embedding", {
                                    "step": "embedding",
                                    "message": f"Vectorizing messages...",
                                    "current": chunk_idx + 1,
                                    "total": total_chunks,
                                    "embeddings_created": stats['embeddings_created']
                                })
                        except Exception as e:
                            log_to_db(
                                db,
                                "WARNING",
                                f"Failed to create embedding for message {msg_record['db_message'].id}: {str(e)}",
                                service="ingestion"
                            )
                            stats['embeddings_skipped'] += 1
            
                chunk_idx += 1
                
            except Exception as e:
                log_to_db(
                    db,
                    "WARNING",
                    f"Failed to create embedding for chunk (embedding model may not be ready): {str(e)}",
                    service="ingestion"
                )
                stats['embeddings_skipped'] += 1
                # Count skipped message embeddings for this chunk
                chunk_message_count = len(chunk.get('message_ids', []))
                stats['embeddings_skipped'] += chunk_message_count
                chunk_idx += 1
        
        db.commit()
        
        _emit_progress("complete", {
            "step": "complete",
            "message": "Import complete!",
            "stats": stats,
            "percent": 100.0
        })
        
        log_to_db(
            db,
            "INFO",
            f"Ingestion complete: {stats['messages_created']} messages, "
            f"{stats['chunks_created']} chunks, {stats['summaries_created']} summaries, "
            f"{stats['embeddings_created']} embeddings. "
            f"Skipped: {stats.get('summaries_skipped', 0)} summaries, {stats.get('embeddings_skipped', 0)} embeddings",
            service="ingestion"
        )
        
        return stats
    
    except Exception as e:
        db.rollback()
        error_msg = f"WhatsApp ingestion error: {str(e)}"
        log_to_db(db, "ERROR", error_msg, service="ingestion")
        raise

