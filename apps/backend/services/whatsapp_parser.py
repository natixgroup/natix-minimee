"""
Enhanced WhatsApp message parser
Handles proper date parsing, emoji preservation, multi-line messages
"""
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple


def parse_whatsapp_date(date_str: str) -> Optional[datetime]:
    """
    Parse WhatsApp date format: DD/MM/YYYY, HH:MM:SS or DD/M/YY, HH:MM:SS
    Also handles: DD/MM/YYYY, HH:MM or DD/M/YY, HH:MM
    Handles both 4-digit years (YYYY) and 2-digit years (YY, interpreted as 20YY for years >= 50, 21YY for years < 50)
    Returns datetime or None if parsing fails
    """
    # Pattern: [DD/MM/YYYY, HH:MM:SS] or [DD/MM/YYYY, HH:MM] or [DD/M/YY, HH:MM:SS]
    patterns = [
        r'(\d{1,2})/(\d{1,2})/(\d{4}),\s*(\d{1,2}):(\d{2}):(\d{2})',  # With seconds, 4-digit year
        r'(\d{1,2})/(\d{1,2})/(\d{4}),\s*(\d{1,2}):(\d{2})',  # Without seconds, 4-digit year
        r'(\d{1,2})/(\d{1,2})/(\d{2}),\s*(\d{1,2}):(\d{2}):(\d{2})',  # With seconds, 2-digit year
        r'(\d{1,2})/(\d{1,2})/(\d{2}),\s*(\d{1,2}):(\d{2})',  # Without seconds, 2-digit year
    ]
    
    for pattern in patterns:
        match = re.match(pattern, date_str.strip())
        if match:
            try:
                parts = match.groups()
                if len(parts) == 6:
                    day, month, year_str, hour, minute, second = parts
                    year_str = year_str.strip()
                    second = int(second)
                else:
                    day, month, year_str, hour, minute = parts
                    year_str = year_str.strip()
                    second = 0
                
                day, month, hour, minute = map(int, (day, month, hour, minute))
                
                # Handle 2-digit years (convert to 4-digit)
                if len(year_str) == 2:
                    year = int(year_str)
                    # Assume years 00-49 are 2000-2049, years 50-99 are 1950-1999
                    # But for WhatsApp exports, it's more likely recent years, so use 2000+ for all
                    # Actually, looking at the example: 24 = 2024, 25 = 2025, so use 2000+
                    year = 2000 + year
                else:
                    year = int(year_str)
                
                return datetime(year, month, day, hour, minute, second)
            except (ValueError, TypeError):
                continue
    
    return None


def parse_whatsapp_line(line: str) -> Optional[Tuple[datetime, str, str]]:
    """
    Parse a single WhatsApp line
    Returns: (timestamp, sender, content) or None if not a message line
    Handles:
    - Regular messages: [DD/MM/YY, HH:MM:SS] Sender: Message
    - System messages: [DD/MM/YY, HH:MM:SS] WhatsApp System Message (no sender)
    - Media references: messages with "document manquant", "image absente", "audio omis"
    """
    line = line.strip()
    if not line:
        return None
    
    # Pattern: [DD/MM/YYYY or DD/MM/YY, HH:MM:SS or HH:MM] Sender: Message
    # Or: [DD/MM/YYYY or DD/MM/YY, HH:MM:SS or HH:MM] System message (no colon, no sender)
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
        
        # Filter out WhatsApp system messages that are not useful for RAG
        # Common system messages in French/English
        system_message_patterns = [
            r'Les messages et les appels sont chiffrés',
            r'Messages and calls are end-to-end encrypted',
            r'Ce message a été supprimé',
            r'This message was deleted',
        ]
        
        # Check if it's a system message (optional - we can keep them for context)
        # For now, we keep all messages including system ones
        
        return (timestamp, sender, content)
    
    # Handle lines that start with date but have no sender (system messages)
    # Pattern: [DD/MM/YY, HH:MM:SS] System message without sender
    date_only_pattern = r'^\[([^\]]+)\]\s*(.+)$'
    date_match = re.match(date_only_pattern, line)
    if date_match:
        date_str, content = date_match.groups()
        timestamp = parse_whatsapp_date(date_str)
        if timestamp:
            # Treat as system message from "WhatsApp"
            return (timestamp, "WhatsApp", content.strip())
    
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

