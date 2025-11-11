"""
Real-time chunking service for new messages
Creates embeddings for new messages and groups them with recent messages into conversational blocks
Uses BackgroundTasks for async processing to avoid blocking the API
"""
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from models import Message, Embedding
from services.embeddings import store_embedding, build_embedding_metadata
from services.conversational_chunking import create_conversational_blocks
from services.language_detector import detect_language
from services.logs_service import log_to_db


def create_realtime_chunk_for_message(
    db: Session,
    message: Message,
    user_id: int,
    time_window_minutes: int = 20,
    silence_threshold_hours: float = 1.0
) -> Optional[Dict]:
    """
    Create a conversational chunk for a new message by grouping it with recent messages
    
    Args:
        db: Database session
        message: New message that just arrived
        user_id: User ID
        time_window_minutes: Time window for grouping messages (default: 20 minutes)
        silence_threshold_hours: Silence threshold to start new block (default: 1.0 hour)
    
    Returns:
        Dict with chunk info if created, None if message should remain standalone
    """
    try:
        # First, create individual embedding for the new message (for immediate RAG availability)
        text_with_sender = f"{message.sender}: {message.content}" if message.sender else message.content
        message_language = detect_language(message.content)
        
        message_metadata = build_embedding_metadata(
            message=message,
            language=message_language,
            chunk=False,
            user_id=user_id
        )
        
        # Store individual message embedding
        store_embedding(
            db=db,
            text=text_with_sender,
            message_id=message.id,
            metadata=message_metadata,
            user_id=user_id,
            message=message
        )
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Created individual embedding for new message {message.id} (source: {message.source})",
            service="realtime_chunking",
            user_id=user_id,
            metadata={"message_id": message.id, "source": message.source, "conversation_id": message.conversation_id}
        )
        
        # Now, try to group with recent messages in the same conversation
        # Get recent messages from the same conversation (within time window)
        time_threshold = message.timestamp - timedelta(minutes=time_window_minutes)
        
        recent_messages = db.query(Message).filter(
            Message.conversation_id == message.conversation_id,
            Message.source == message.source,
            Message.user_id == user_id,
            Message.timestamp >= time_threshold,
            Message.id != message.id  # Exclude current message
        ).order_by(Message.timestamp.asc()).all()
        
        if not recent_messages:
            # No recent messages, keep as standalone
            return None
        
        # Check if any of the recent messages already have chunk embeddings
        # If so, we might want to extend the existing chunk or create a new one
        recent_message_ids = [msg.id for msg in recent_messages]
        
        # Get embeddings for recent messages to check if they're in chunks
        recent_embeddings = db.query(Embedding).filter(
            Embedding.message_id.in_(recent_message_ids),
            Embedding.meta_data['chunk'].astext == 'false'  # Only individual message embeddings
        ).all()
        
        # If we have recent messages without chunks, create a conversational block
        if len(recent_messages) >= 2:  # Need at least 2 messages to create a block
            # Prepare messages for chunking
            messages_for_chunking = []
            for msg in recent_messages:
                messages_for_chunking.append({
                    'timestamp': msg.timestamp,
                    'sender': msg.sender or 'unknown',
                    'content': msg.content
                })
            
            # Add current message
            messages_for_chunking.append({
                'timestamp': message.timestamp,
                'sender': message.sender or 'unknown',
                'content': message.content
            })
            
            # Create conversational blocks
            blocks = create_conversational_blocks(
                messages_for_chunking,
                time_window_minutes=time_window_minutes,
                silence_threshold_hours=silence_threshold_hours
            )
            
            # Find the block that contains the new message (should be the last one)
            new_message_block = None
            for block in blocks:
                if len(block['messages']) > 0:
                    last_msg_idx = block['messages'][-1]
                    if last_msg_idx == len(messages_for_chunking) - 1:  # New message is last
                        new_message_block = block
                        break
            
            if new_message_block and new_message_block['message_count'] >= 2:
                # Create embedding for the conversational block
                block_language = detect_language(new_message_block['text'])
                
                # Get participants from the block
                participants = new_message_block.get('participants', [])
                
                # Build metadata for block
                block_metadata = {
                    'chunk': True,
                    'language': block_language,
                    'message_count': new_message_block['message_count'],
                    'participants': participants,
                    'source': message.source,
                    'conversation_id': message.conversation_id,
                    'start_timestamp': new_message_block.get('start_timestamp').isoformat() if new_message_block.get('start_timestamp') else None,
                    'end_timestamp': new_message_block.get('end_timestamp').isoformat() if new_message_block.get('end_timestamp') else None,
                    'duration_minutes': new_message_block.get('duration_minutes'),
                    'user_id': user_id,
                    'topic': 'conversation',  # Default topic, can be enhanced later
                }
                
                # Add temporal context
                if new_message_block.get('start_timestamp'):
                    from services.embeddings import _calculate_temporal_metadata
                    temporal_meta = _calculate_temporal_metadata(new_message_block['start_timestamp'])
                    block_metadata['temporal_context'] = temporal_meta
                
                # Store block embedding
                block_embedding = store_embedding(
                    db=db,
                    text=new_message_block['text'],
                    message_id=None,  # Blocks don't have a single message_id
                    metadata=block_metadata,
                    user_id=user_id
                )
                db.commit()
                
                log_to_db(
                    db,
                    "INFO",
                    f"Created conversational block embedding for {new_message_block['message_count']} messages "
                    f"(including new message {message.id})",
                    service="realtime_chunking",
                    user_id=user_id,
                    metadata={
                        "message_id": message.id,
                        "block_id": block_embedding.id,
                        "message_count": new_message_block['message_count'],
                        "source": message.source,
                        "conversation_id": message.conversation_id
                    }
                )
                
                return {
                    'block_id': block_embedding.id,
                    'message_count': new_message_block['message_count'],
                    'participants': participants
                }
        
        return None
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error creating real-time chunk for message {message.id}: {str(e)}",
            service="realtime_chunking",
            user_id=user_id,
            metadata={"message_id": message.id, "error": str(e)}
        )
        db.rollback()
        return None


def schedule_realtime_chunking(
    background_tasks: BackgroundTasks,
    db: Session,
    message: Message,
    user_id: int
):
    """
    Schedule real-time chunking as a background task
    
    Args:
        background_tasks: FastAPI BackgroundTasks instance
        db: Database session (will create new session in background task)
        message: New message (will be re-queried in background task)
        user_id: User ID
    """
    # Store message ID to re-query in background task (session may be closed)
    message_id = message.id
    conversation_id = message.conversation_id
    source = message.source
    
    def _background_chunking():
        """Background task that creates a new DB session"""
        from db.database import SessionLocal
        bg_db = SessionLocal()
        try:
            # Re-query message in new session
            bg_message = bg_db.query(Message).filter(Message.id == message_id).first()
            if bg_message:
                create_realtime_chunk_for_message(
                    db=bg_db,
                    message=bg_message,
                    user_id=user_id
                )
        finally:
            bg_db.close()
    
    background_tasks.add_task(_background_chunking)

