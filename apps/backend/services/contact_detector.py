"""
Contact detection service
Automatically detects contact information from parsed WhatsApp messages
"""
from typing import List, Dict, Optional, Set
from collections import Counter
from services.language_detector import detect_language


def detect_contact_from_messages(messages: List[Dict], user_id: int, user_name: Optional[str] = None) -> Dict:
    """
    Detect contact information from parsed WhatsApp messages
    
    Args:
        messages: List of message dicts with timestamp, sender, content
        user_id: User ID to identify user's messages
        user_name: Optional user name to exclude from contact detection
    
    Returns:
        Dict with pre-filled contact information:
        - first_name: Detected contact name
        - nickname: None (to be filled by user)
        - relation_type: None (to be filled by user)
        - context: Auto-detected context
        - languages: Detected languages
        - location: None (to be filled by user)
        - importance_rating: None (to be filled by user)
        - dominant_themes: Detected themes
    """
    if not messages:
        return {}
    
    # Extract unique senders (excluding user)
    all_senders = [msg['sender'] for msg in messages]
    sender_counts = Counter(all_senders)
    
    # Identify user's sender name (most common if user_name not provided)
    if user_name:
        user_sender = user_name
    else:
        # Assume user is the most common sender (usually true for personal conversations)
        user_sender = sender_counts.most_common(1)[0][0] if sender_counts else None
    
    # Get contact name (other sender in 1-1, or most common non-user in groups)
    contact_senders = [s for s in sender_counts.keys() if s != user_sender]
    
    if not contact_senders:
        # Fallback: use first non-user sender or first sender
        contact_senders = [s for s in all_senders if s != user_sender] if user_sender else all_senders[:1]
    
    # Extract contact name (clean up common patterns)
    contact_name = contact_senders[0] if contact_senders else "Unknown"
    
    # Clean contact name (remove common suffixes/prefixes)
    contact_name = _clean_contact_name(contact_name)
    
    # Get messages from contact (for analysis)
    contact_messages = [msg for msg in messages if msg['sender'] != user_sender]
    
    # Detect languages
    languages = _detect_languages(contact_messages)
    
    # Detect dominant themes
    dominant_themes = _detect_themes(contact_messages)
    
    # Auto-detect context
    context = _detect_context(contact_messages, languages)
    
    return {
        'first_name': contact_name,
        'nickname': None,  # User will fill
        'relation_type_ids': None,  # User will fill (list of relation_type IDs)
        'context': context,
        'languages': languages,
        'location': None,  # User will fill
        'importance_rating': None,  # User will fill
        'dominant_themes': dominant_themes
    }


def _clean_contact_name(name: str) -> str:
    """Clean contact name from common WhatsApp patterns"""
    # Remove common suffixes
    suffixes = [' Bkt', ' Bkt:', ':', ' @', '@']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    
    # Remove phone number patterns
    import re
    name = re.sub(r'\+\d{1,3}\s?\d{1,14}', '', name).strip()
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name


def _detect_languages(messages: List[Dict], sample_size: int = 50) -> List[str]:
    """
    Detect languages from messages
    Returns list of language codes (e.g., ['fr', 'ar'])
    """
    if not messages:
        return []
    
    # Sample messages for language detection (to avoid processing all)
    sample = messages[:sample_size] if len(messages) > sample_size else messages
    
    languages = set()
    for msg in sample:
        content = msg.get('content', '')
        if content and len(content.strip()) > 10:  # Skip very short messages
            try:
                lang = detect_language(content)
                if lang:
                    languages.add(lang)
            except Exception:
                pass  # Skip if detection fails
    
    # Common language mappings
    lang_map = {
        'fr': 'français',
        'ar': 'darija',
        'en': 'anglais',
        'es': 'espagnol',
        'de': 'allemand',
        'it': 'italien',
        'pt': 'portugais'
    }
    
    # Convert to readable names
    detected = []
    for lang_code in sorted(languages):
        detected.append(lang_map.get(lang_code, lang_code))
    
    return detected if detected else ['français']  # Default to French


def _detect_themes(messages: List[Dict], sample_size: int = 100) -> List[str]:
    """
    Detect dominant themes from messages
    Returns list of theme keywords
    """
    if not messages:
        return []
    
    # Sample messages for theme detection
    sample = messages[:sample_size] if len(messages) > sample_size else messages
    
    # Combine all message content
    all_text = ' '.join([msg.get('content', '') for msg in sample]).lower()
    
    # Theme keywords (French and Arabic/Darija)
    theme_keywords = {
        'famille': ['famille', 'maman', 'papa', 'mère', 'père', 'enfant', 'fils', 'fille', 'frère', 'sœur', 'parent'],
        'couple': ['amour', 'mon cœur', 'chéri', 'chérie', 'bébé', 'couple', 'mariage', 'mari', 'femme', 'époux', 'épouse'],
        'travail': ['travail', 'bureau', 'réunion', 'projet', 'client', 'collègue', 'collègue', 'deadline', 'réunion'],
        'santé': ['santé', 'médecin', 'docteur', 'malade', 'fatigue', 'douleur', 'médicament', 'hôpital'],
        'quotidien': ['manger', 'repas', 'cuisine', 'courses', 'achat', 'magasin', 'super marché', 'supermarché'],
        'projet personnel': ['projet', 'idée', 'plan', 'objectif', 'but', 'rêve', 'ambition'],
        'affection': ['❤️', '💕', '😘', 'bisous', 'je t\'aime', 'i love you', 'amour']
    }
    
    theme_scores = {}
    for theme, keywords in theme_keywords.items():
        score = sum(1 for keyword in keywords if keyword in all_text)
        if score > 0:
            theme_scores[theme] = score
    
    # Return top 3 themes
    sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)
    return [theme for theme, _ in sorted_themes[:3]]


def _detect_context(messages: List[Dict], languages: List[str]) -> str:
    """
    Auto-detect context from messages and languages
    """
    if not messages:
        return "Conversation WhatsApp"
    
    # Check for personal indicators
    personal_keywords = ['famille', 'amour', 'mon cœur', 'chéri', 'bébé', 'maman', 'papa']
    all_text = ' '.join([msg.get('content', '').lower() for msg in messages[:50]])
    
    is_personal = any(keyword in all_text for keyword in personal_keywords)
    
    # Build context string
    context_parts = []
    
    if is_personal:
        context_parts.append("Conversations personnelles")
    
    if 'famille' in all_text or 'maman' in all_text or 'papa' in all_text:
        context_parts.append("et familiales")
    
    if languages:
        lang_str = " et ".join(languages)
        context_parts.append(f"({lang_str})")
    
    return " ".join(context_parts) if context_parts else "Conversation WhatsApp"

