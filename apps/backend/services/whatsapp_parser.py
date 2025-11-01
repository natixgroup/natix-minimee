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


def parse_whatsapp_export(content: str) -> List[Dict]:
    """
    Parse complete WhatsApp export file
    Returns list of message dictionaries with: timestamp, sender, content
    Handles multi-line messages properly
    """
    lines = content.split('\n')
    messages = []
    current_message = None
    current_content_lines = []
    
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
    
    return messages

