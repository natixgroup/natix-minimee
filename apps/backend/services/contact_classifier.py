"""
Contact classification service
Automatically classifies contacts based on message content, tone, and patterns
"""
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models import Contact, ContactCategory, Message, RelationType
from services.llm_router import generate_llm_response
from services.logs_service import log_to_db
import json


def classify_contact_from_messages(
    db: Session,
    user_id: int,
    conversation_id: str,
    messages: Optional[List[Dict]] = None,
    confidence_threshold: float = 0.7
) -> Tuple[Optional[int], float, str]:
    """
    Classify a contact based on message content
    
    Args:
        db: Database session
        user_id: User ID
        conversation_id: Conversation ID
        messages: Optional list of message dicts. If None, fetches from DB
        confidence_threshold: Minimum confidence to auto-assign category
    
    Returns:
        Tuple of (category_id, confidence_score, reasoning)
    """
    try:
        # Get contact if exists
        contact = db.query(Contact).filter(
            Contact.user_id == user_id,
            Contact.conversation_id == conversation_id
        ).first()
        
        # If no messages provided, fetch from DB
        if messages is None:
            db_messages = db.query(Message).filter(
                Message.user_id == user_id,
                Message.conversation_id == conversation_id
            ).order_by(Message.timestamp.desc()).limit(50).all()
            
            messages = [
                {
                    'sender': msg.sender,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'source': msg.source
                }
                for msg in db_messages
            ]
        
        if not messages:
            return None, 0.0, "No messages found"
        
        # Analyze messages with LLM
        analysis_prompt = f"""Analyze the following conversation messages and classify the relationship type.

Messages:
{json.dumps(messages[:20], indent=2, default=str)}

Based on the content, tone, topics, and frequency of communication, classify this contact into one of these categories:
- famille (family)
- amis (friends)
- collegues (colleagues)
- clients (clients)
- fournisseurs (suppliers)
- contacts_pro (professional contacts)
- contacts_perso (personal contacts)
- autres (others)

Respond in JSON format:
{{
    "category_code": "category code",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""
        
        # Use LLM to classify
        llm_response = generate_llm_response(
            prompt=analysis_prompt,
            db=db,
            user_id=user_id
        )
        
        # Parse LLM response
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', llm_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # Fallback: try to parse entire response
                result = json.loads(llm_response)
            
            category_code = result.get('category_code', 'autres')
            confidence = float(result.get('confidence', 0.5))
            reasoning = result.get('reasoning', '')
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            log_to_db(
                db,
                "WARNING",
                f"Failed to parse LLM classification response: {str(e)}",
                service="contact_classifier",
                user_id=user_id
            )
            category_code = 'autres'
            confidence = 0.3
            reasoning = "Could not parse classification response"
        
        # Get category ID
        category = db.query(ContactCategory).filter(
            ContactCategory.code == category_code,
            ContactCategory.is_system == True
        ).first()
        
        if not category:
            # Fallback to 'autres'
            category = db.query(ContactCategory).filter(
                ContactCategory.code == 'autres',
                ContactCategory.is_system == True
            ).first()
        
        category_id = category.id if category else None
        
        log_to_db(
            db,
            "INFO",
            f"Classified contact {conversation_id} as {category_code} (confidence: {confidence:.2f})",
            service="contact_classifier",
            user_id=user_id,
            metadata={
                "conversation_id": conversation_id,
                "category_code": category_code,
                "confidence": confidence,
                "reasoning": reasoning
            }
        )
        
        return category_id, confidence, reasoning
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error classifying contact: {str(e)}",
            service="contact_classifier",
            user_id=user_id
        )
        return None, 0.0, f"Error: {str(e)}"


def classify_contact_from_gmail(
    db: Session,
    user_id: int,
    thread_id: str
) -> Tuple[Optional[int], float, str]:
    """
    Classify a contact from Gmail thread
    
    Args:
        db: Database session
        user_id: User ID
        thread_id: Gmail thread ID
    
    Returns:
        Tuple of (category_id, confidence_score, reasoning)
    """
    try:
        # Get messages from this thread
        messages = db.query(Message).filter(
            Message.user_id == user_id,
            Message.conversation_id == thread_id,
            Message.source == 'gmail'
        ).order_by(Message.timestamp.desc()).limit(50).all()
        
        if not messages:
            return None, 0.0, "No Gmail messages found"
        
        message_dicts = [
            {
                'sender': msg.sender,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'source': msg.source
            }
            for msg in messages
        ]
        
        return classify_contact_from_messages(
            db=db,
            user_id=user_id,
            conversation_id=thread_id,
            messages=message_dicts
        )
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error classifying Gmail contact: {str(e)}",
            service="contact_classifier",
            user_id=user_id
        )
        return None, 0.0, f"Error: {str(e)}"


def classify_contact_from_whatsapp(
    db: Session,
    user_id: int,
    conversation_id: str
) -> Tuple[Optional[int], float, str]:
    """
    Classify a contact from WhatsApp conversation
    
    Args:
        db: Database session
        user_id: User ID
        conversation_id: WhatsApp conversation ID
    
    Returns:
        Tuple of (category_id, confidence_score, reasoning)
    """
    try:
        # Get messages from this conversation
        messages = db.query(Message).filter(
            Message.user_id == user_id,
            Message.conversation_id == conversation_id,
            Message.source == 'whatsapp'
        ).order_by(Message.timestamp.desc()).limit(50).all()
        
        if not messages:
            return None, 0.0, "No WhatsApp messages found"
        
        message_dicts = [
            {
                'sender': msg.sender,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'source': msg.source,
                'recipient': msg.recipient,
                'recipients': msg.recipients
            }
            for msg in messages
        ]
        
        return classify_contact_from_messages(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            messages=message_dicts
        )
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error classifying WhatsApp contact: {str(e)}",
            service="contact_classifier",
            user_id=user_id
        )
        return None, 0.0, f"Error: {str(e)}"


def auto_classify_and_notify(
    db: Session,
    user_id: int,
    conversation_id: str,
    source: str,
    confidence_threshold: float = 0.7
) -> Optional[Dict]:
    """
    Automatically classify a contact and create notification if needed
    
    Args:
        db: Database session
        user_id: User ID
        conversation_id: Conversation ID
        source: 'gmail' or 'whatsapp'
        confidence_threshold: Minimum confidence to auto-assign
    
    Returns:
        Dict with classification result and notification info, or None if no classification
    """
    try:
        if source == 'gmail':
            category_id, confidence, reasoning = classify_contact_from_gmail(
                db, user_id, conversation_id
            )
        elif source == 'whatsapp':
            category_id, confidence, reasoning = classify_contact_from_whatsapp(
                db, user_id, conversation_id
            )
        else:
            return None
        
        if not category_id:
            return None
        
        # Get or create contact
        contact = db.query(Contact).filter(
            Contact.user_id == user_id,
            Contact.conversation_id == conversation_id
        ).first()
        
        if not contact:
            # Create contact if doesn't exist
            contact = Contact(
                user_id=user_id,
                conversation_id=conversation_id,
                contact_category_id=category_id if confidence >= confidence_threshold else None
            )
            db.add(contact)
            db.commit()
        else:
            # Update category if confidence is high enough
            if confidence >= confidence_threshold:
                contact.contact_category_id = category_id
                db.commit()
        
        # Return notification info if confidence is below threshold or contact was just created
        if confidence < confidence_threshold or (contact.contact_category_id is None and confidence >= 0.5):
            category = db.query(ContactCategory).filter(ContactCategory.id == category_id).first()
            return {
                'contact_id': contact.id,
                'conversation_id': conversation_id,
                'suggested_category_id': category_id,
                'suggested_category_code': category.code if category else None,
                'suggested_category_label': category.label if category else None,
                'confidence': confidence,
                'reasoning': reasoning,
                'needs_validation': True
            }
        
        return {
            'contact_id': contact.id,
            'conversation_id': conversation_id,
            'category_id': category_id,
            'confidence': confidence,
            'auto_assigned': True
        }
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error in auto_classify_and_notify: {str(e)}",
            service="contact_classifier",
            user_id=user_id
        )
        return None


