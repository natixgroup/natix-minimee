"""
Conversational chunking service
Groups messages into conversational blocks based on temporal windows and logical flow
Replaces the simple chunking.py with intelligent grouping
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re


def create_conversational_blocks(
    messages: List[Dict],
    time_window_minutes: int = 20,
    silence_threshold_hours: float = 1.0
) -> List[Dict]:
    """
    Create conversational blocks from messages
    Groups messages by temporal windows (15-30 min exchanges) or logical breaks (silence > 1h, topic change)
    
    Args:
        messages: List of message dicts with timestamp, sender, content
        time_window_minutes: Maximum time window for a block (default: 20 minutes)
        silence_threshold_hours: Silence threshold to start new block (default: 1.0 hour)
    
    Returns:
        List of block dicts with:
        - messages: list of message indices
        - text: combined text with [Author]: prefix for each message
        - start_timestamp: first message timestamp
        - end_timestamp: last message timestamp
        - duration_minutes: duration of the block in minutes
        - participants: list of unique senders
        - message_count: number of messages in block
    """
    if not messages:
        return []
    
    blocks = []
    current_block_messages = []
    
    for idx, msg in enumerate(messages):
        # Check if we should start a new block
        should_start_new_block = False
        
        if current_block_messages:
            # Get last message in current block
            last_msg_idx = current_block_messages[-1]
            last_msg = messages[last_msg_idx]
            current_msg = msg
            
            # Calculate time difference
            time_diff = current_msg['timestamp'] - last_msg['timestamp']
            time_diff_minutes = time_diff.total_seconds() / 60
            time_diff_hours = time_diff_minutes / 60
            
            # Check for silence (gap > threshold)
            if time_diff_hours > silence_threshold_hours:
                should_start_new_block = True
            
            # Check for time window exceeded
            elif time_diff_minutes > time_window_minutes:
                # Check if current block duration exceeds window
                block_start = messages[current_block_messages[0]]['timestamp']
                block_duration = (current_msg['timestamp'] - block_start).total_seconds() / 60
                if block_duration > time_window_minutes:
                    should_start_new_block = True
            
            # Check for topic change (simple lexical analysis)
            elif _detect_topic_change(last_msg, current_msg):
                should_start_new_block = True
        
        if should_start_new_block and current_block_messages:
            # Create block from current messages
            block = _create_block_from_messages(messages, current_block_messages)
            blocks.append(block)
            current_block_messages = []
        
        # Add message to current block
        current_block_messages.append(idx)
    
    # Create final block if we have messages
    if current_block_messages:
        block = _create_block_from_messages(messages, current_block_messages)
        blocks.append(block)
    
    return blocks


def _create_block_from_messages(
    all_messages: List[Dict],
    message_indices: List[int]
) -> Dict:
    """Create a conversational block from message indices"""
    chunk_messages = [all_messages[i] for i in message_indices]
    
    # Combine text with [Author]: prefix for each message
    text_parts = []
    senders = set()
    timestamps = []
    
    for msg in chunk_messages:
        # Prefix with [Author]: to preserve author context
        author = msg['sender']
        content = msg['content']
        text_parts.append(f"[{author}]: {content}")
        senders.add(author)
        timestamps.append(msg['timestamp'])
    
    block_text = '\n'.join(text_parts)
    
    # Calculate duration
    start_time = min(timestamps)
    end_time = max(timestamps)
    duration_minutes = (end_time - start_time).total_seconds() / 60
    
    return {
        'messages': message_indices,
        'text': block_text,
        'start_timestamp': start_time,
        'end_timestamp': end_time,
        'duration_minutes': duration_minutes,
        'participants': list(senders),
        'message_count': len(message_indices),
        'message_ids': [],  # Will be populated after messages are saved to DB
    }


def _detect_topic_change(msg1: Dict, msg2: Dict) -> bool:
    """
    Detect if there's a topic change between two messages
    Simple lexical analysis based on keywords
    """
    content1 = msg1.get('content', '').lower()
    content2 = msg2.get('content', '').lower()
    
    # Topic keywords (French and common patterns)
    topic_keywords = {
        'travail': ['travail', 'bureau', 'réunion', 'projet', 'client', 'collègue', 'deadline'],
        'famille': ['famille', 'maman', 'papa', 'enfant', 'fils', 'fille', 'parent'],
        'couple': ['amour', 'mon cœur', 'chéri', 'chérie', 'bébé', 'couple', 'mariage'],
        'santé': ['santé', 'médecin', 'docteur', 'malade', 'fatigue', 'douleur', 'médicament'],
        'quotidien': ['manger', 'repas', 'cuisine', 'courses', 'achat', 'magasin'],
        'projet': ['projet', 'idée', 'plan', 'objectif', 'but', 'rêve']
    }
    
    # Find topics in each message
    topics1 = set()
    topics2 = set()
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in content1 for keyword in keywords):
            topics1.add(topic)
        if any(keyword in content2 for keyword in keywords):
            topics2.add(topic)
    
    # If topics are different, it's a topic change
    if topics1 and topics2 and topics1 != topics2:
        return True
    
    # Check for question patterns (often indicate topic change)
    question_patterns = [r'\?', r'pourquoi', r'comment', r'quand', r'où', r'qui', r'quoi']
    has_question1 = any(re.search(pattern, content1) for pattern in question_patterns)
    has_question2 = any(re.search(pattern, content2) for pattern in question_patterns)
    
    # If one is a question and the other isn't, might be topic change
    if has_question1 != has_question2:
        # Additional check: if time gap is significant, more likely topic change
        time_diff = (msg2['timestamp'] - msg1['timestamp']).total_seconds() / 60
        if time_diff > 30:  # 30 minutes gap
            return True
    
    return False

