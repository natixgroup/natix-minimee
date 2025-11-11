"""
Script to regenerate embeddings for messages that don't have them
Usage: python3 scripts/regenerate_embeddings_for_messages.py [--user-id USER_ID] [--filter FILTER] [--limit LIMIT]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from db.database import SessionLocal
from models import Message, Embedding
from services.embeddings import store_embedding
from services.logs_service import log_to_db
import argparse
from tqdm import tqdm


def regenerate_embeddings_for_messages(
    db: Session,
    user_id: int = None,
    filter_text: str = None,
    limit: int = None,
    batch_size: int = 100
):
    """
    Regenerate embeddings for messages that don't have them
    
    Args:
        db: Database session
        user_id: Optional user ID filter
        filter_text: Optional text filter (e.g., "hajar")
        limit: Optional limit on number of messages to process
        batch_size: Number of messages to process before committing
    """
    # Build query for messages without embeddings
    query = db.query(Message).filter(
        ~Message.id.in_(db.query(Embedding.message_id).filter(Embedding.message_id.isnot(None)))
    )
    
    if user_id:
        query = query.filter(Message.user_id == user_id)
    
    if filter_text:
        query = query.filter(Message.content.ilike(f'%{filter_text}%'))
    
    if limit:
        query = query.limit(limit)
    
    messages = query.all()
    total = len(messages)
    
    print(f"Found {total} messages without embeddings")
    if filter_text:
        print(f"Filter: text contains '{filter_text}'")
    if user_id:
        print(f"User ID: {user_id}")
    if limit:
        print(f"Limit: {limit}")
    
    if total == 0:
        print("No messages to process")
        return
    
    print(f"\nProcessing {total} messages...")
    
    created = 0
    errors = 0
    
    # Process in batches
    for i in tqdm(range(0, total, batch_size), desc="Processing batches"):
        batch = messages[i:i+batch_size]
        
        for message in batch:
            try:
                # Create embedding with sender prefix
                text_with_sender = f"{message.sender}: {message.content}" if message.sender else message.content
                
                # Store embedding
                embedding = store_embedding(
                    db=db,
                    text=text_with_sender,
                    message_id=message.id,
                    message=message,
                    user_id=message.user_id
                )
                created += 1
                
            except Exception as e:
                errors += 1
                log_to_db(
                    db,
                    "ERROR",
                    f"Failed to create embedding for message {message.id}: {str(e)}",
                    service="regenerate_embeddings",
                    user_id=message.user_id,
                    metadata={"message_id": message.id, "error": str(e)}
                )
                print(f"\nError for message {message.id}: {str(e)}")
        
        # Commit batch
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"\nError committing batch: {str(e)}")
            errors += len(batch)
    
    print(f"\n✓ Completed: {created} embeddings created, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate embeddings for messages")
    parser.add_argument("--user-id", type=int, default=1, help="User ID filter (default: 1)")
    parser.add_argument("--filter", type=str, help="Text filter (e.g., 'hajar')")
    parser.add_argument("--limit", type=int, help="Limit number of messages to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing (default: 100)")
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        regenerate_embeddings_for_messages(
            db=db,
            user_id=args.user_id,
            filter_text=args.filter,
            limit=args.limit,
            batch_size=args.batch_size
        )
    finally:
        db.close()


