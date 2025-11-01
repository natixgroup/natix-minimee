"""
Message chunking service
Groups 3-5 consecutive messages into chunks for better context
"""
from typing import List, Dict, Optional
from datetime import datetime


def create_chunks(
    messages: List[Dict],
    min_chunk_size: int = 3,
    max_chunk_size: int = 5
) -> List[Dict]:
    """
    Create chunks from messages
    Groups 3-5 consecutive messages into chunks
    
    Args:
        messages: List of message dicts with timestamp, sender, content
        min_chunk_size: Minimum messages per chunk (default: 3)
        max_chunk_size: Maximum messages per chunk (default: 5)
    
    Returns:
        List of chunk dicts with:
        - messages: list of message indices
        - text: combined text of messages
        - senders: list of unique senders
        - start_timestamp: first message timestamp
        - end_timestamp: last message timestamp
        - message_count: number of messages in chunk
    """
    if not messages:
        return []
    
    chunks = []
    current_chunk_messages = []
    
    for idx, msg in enumerate(messages):
        current_chunk_messages.append(idx)
        
        # Create chunk when max size reached
        if len(current_chunk_messages) >= max_chunk_size:
            chunk = _create_chunk_from_messages(messages, current_chunk_messages)
            chunks.append(chunk)
            current_chunk_messages = []
    
    # Create final chunk if we have at least min_chunk_size messages
    if len(current_chunk_messages) >= min_chunk_size:
        chunk = _create_chunk_from_messages(messages, current_chunk_messages)
        chunks.append(chunk)
    elif len(current_chunk_messages) > 0 and chunks:
        # Merge small remaining chunk with last chunk
        last_chunk = chunks[-1]
        last_chunk['messages'].extend(current_chunk_messages)
        last_chunk = _update_chunk_metadata(messages, last_chunk)
        chunks[-1] = last_chunk
    
    return chunks


def _create_chunk_from_messages(
    all_messages: List[Dict],
    message_indices: List[int]
) -> Dict:
    """Create a chunk from message indices"""
    chunk_messages = [all_messages[i] for i in message_indices]
    
    # Combine text
    text_parts = []
    senders = set()
    timestamps = []
    
    for msg in chunk_messages:
        text_parts.append(f"{msg['sender']}: {msg['content']}")
        senders.add(msg['sender'])
        timestamps.append(msg['timestamp'])
    
    chunk_text = '\n'.join(text_parts)
    
    return {
        'messages': message_indices,
        'text': chunk_text,
        'senders': list(senders),
        'start_timestamp': min(timestamps),
        'end_timestamp': max(timestamps),
        'message_count': len(message_indices),
        'message_ids': [],  # Will be populated after messages are saved to DB
    }


def _update_chunk_metadata(all_messages: List[Dict], chunk: Dict) -> Dict:
    """Update chunk metadata after messages are added"""
    chunk_messages = [all_messages[i] for i in chunk['messages']]
    
    text_parts = []
    senders = set()
    timestamps = []
    
    for msg in chunk_messages:
        text_parts.append(f"{msg['sender']}: {msg['content']}")
        senders.add(msg['sender'])
        timestamps.append(msg['timestamp'])
    
    chunk['text'] = '\n'.join(text_parts)
    chunk['senders'] = list(senders)
    chunk['start_timestamp'] = min(timestamps)
    chunk['end_timestamp'] = max(timestamps)
    chunk['message_count'] = len(chunk['messages'])
    
    return chunk

