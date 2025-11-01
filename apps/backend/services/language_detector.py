"""
Language detection service
"""
from langdetect import detect, LangDetectException
from typing import Optional


def detect_language(text: str) -> Optional[str]:
    """
    Detect language of text
    Returns ISO 639-1 language code (e.g., 'en', 'fr', 'es') or None
    """
    if not text or len(text.strip()) < 3:
        return None
    
    try:
        # Remove emojis for better detection (keep text only)
        # langdetect works better with longer text
        language = detect(text)
        return language
    except LangDetectException:
        return None
    except Exception:
        # Fallback to None if detection fails
        return None


def detect_language_safe(text: str, default: str = 'en') -> str:
    """
    Detect language with fallback to default
    """
    detected = detect_language(text)
    return detected if detected else default

