"""
Enhanced WhatsApp message parser
Handles proper date parsing, emoji preservation, multi-line messages
"""
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple


def parse_whatsapp_date(date_str: str) -> Optional[datetime]:
    """
    Parse WhatsApp date format: DD/MM/YYYY, HH:MM:SS
    Also handles: DD/MM/YYYY, HH:MM
    Returns datetime or None if parsing fails
    """
    # Pattern: [DD/MM/YYYY, HH:MM:SS] or [DD/MM/YYYY, HH:MM]
    patterns = [
        r'(\d{1,2})/(\d{1,2})/(\d{4}),\s*(\d{1,2}):(\d{2}):(\d{2})',  # With seconds
        r'(\d{1,2})/(\d{1,2})/(\d{4}),\s*(\d{1,2}):(\d{2})',  # Without seconds
    ]
    
    for pattern in patterns:
        match = re.match(pattern, date_str.strip())
        if match:
            try:
                parts = match.groups()
                if len(parts) == 6:
                    day, month, year, hour, minute, second = map(int, parts)
                else:
                    day, month, year, hour, minute = map(int, parts)
                    second = 0
                
                return datetime(year, month, day, hour, minute, second)
            except ValueError:
                continue
    
    return None


def parse_whatsapp_line(line: str) -> Optional[Tuple[datetime, str, str]]:
    """
    Parse a single WhatsApp line
    Returns: (timestamp, sender, content) or None if not a message line
    """
    line = line.strip()
    if not line:
        return None
    
    # Pattern: [DD/MM/YYYY, HH:MM:SS] Sender: Message
    # Or: [DD/MM/YYYY, HH:MM] Sender: Message
    pattern = r'\[([^\]]+)\]\s*(.+?):\s*(.+)'
    match = re.match(pattern, line)
    
    if match:
        date_str, sender, content = match.groups()
        
        # Parse date
        timestamp = parse_whatsapp_date(date_str)
        if not timestamp:
            timestamp = datetime.now()  # Fallback to current time
        
        # Preserve emojis and content as-is
        sender = sender.strip()
        content = content.strip()
        
        return (timestamp, sender, content)
    
    return None


def parse_whatsapp_export(content: str, user_whatsapp_id: Optional[str] = None) -> List[Dict]:
    """
    Parse complete WhatsApp export file
    Returns list of message dictionaries with: timestamp, sender, content, recipient, recipients
    Handles multi-line messages properly
    Intelligently determines if conversation is 1-1 or group and extracts participants
    
    Args:
        content: WhatsApp export file content
        user_whatsapp_id: Optional WhatsApp ID of the user (to identify recipient in 1-1 chats)
    
    Returns:
        List of message dicts with recipient/recipients populated
    """
    lines = content.split('\n')
    messages = []
    current_message = None
    current_content_lines = []
    
    # First pass: parse all messages
    for line in lines:
        parsed = parse_whatsapp_line(line)
        
        if parsed:
            # Save previous message if exists
            if current_message:
                current_message['content'] = '\n'.join(current_content_lines)
                messages.append(current_message)
            
            # Start new message
            timestamp, sender, content = parsed
            current_message = {
                'timestamp': timestamp,
                'sender': sender,
                'content': content,
            }
            current_content_lines = [content]
        else:
            # Continuation of previous message
            if current_message and line.strip():
                # Preserve emojis and formatting
                current_content_lines.append(line.strip())
    
    # Save last message
    if current_message:
        current_message['content'] = '\n'.join(current_content_lines)
        messages.append(current_message)
    
    if not messages:
        return messages
    
    # Second pass: Analyze conversation to determine participants
    # Collect all unique senders
    unique_senders = set(msg['sender'] for msg in messages)
    
    # Determine if 1-1 or group
    is_group = len(unique_senders) > 2
    
    if is_group:
        # Group conversation: store all participants in recipients array
        participants = sorted(list(unique_senders))
        for msg in messages:
            msg['recipients'] = participants
            msg['recipient'] = None
    else:
        # 1-1 conversation: determine recipient
        if len(unique_senders) == 2 and user_whatsapp_id:
            # User is one of the senders, recipient is the other
            other_sender = next((s for s in unique_senders if s != user_whatsapp_id), None)
            if other_sender:
                for msg in messages:
                    # Recipient is the other person (not the sender of this message)
                    if msg['sender'] == user_whatsapp_id:
                        msg['recipient'] = other_sender
                    else:
                        msg['recipient'] = user_whatsapp_id
                    msg['recipients'] = None
            else:
                # Couldn't determine, leave recipient as None
                for msg in messages:
                    msg['recipient'] = None
                    msg['recipients'] = None
        elif len(unique_senders) == 1:
            # Only one sender (might be user's own messages or incomplete export)
            for msg in messages:
                msg['recipient'] = None
                msg['recipients'] = None
        else:
            # Default: use conversation_id as recipient hint if available
            # This will be handled in ingestion based on conversation_id
            for msg in messages:
                msg['recipient'] = None
                msg['recipients'] = None
    
    return messages

