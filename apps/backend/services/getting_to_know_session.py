"""
Getting to know session service
Manages interactive "getting to know" sessions with adaptive questions
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from models import ConversationSession, UserInfo, Message
from services.logs_service import log_to_db
from services.llm_router import generate_llm_response
import json
import uuid


# Question structure: organized by category with dependencies
QUESTION_CATEGORIES = {
    'identity': {
        'questions': [
            {'type': 'first_name', 'question': "Quel est ton prénom ?", 'required': True},
            {'type': 'last_name', 'question': "Quel est ton nom de famille ?", 'required': True},
        ],
        'next_category': 'location'
    },
    'location': {
        'questions': [
            {'type': 'birth_place', 'question': "Où es-tu né(e) ?", 'required': False},
            {'type': 'current_city', 'question': "Dans quelle ville vis-tu actuellement ?", 'required': False},
            {'type': 'current_country', 'question': "Dans quel pays vis-tu ?", 'required': False},
        ],
        'next_category': 'personal'
    },
    'personal': {
        'questions': [
            {'type': 'birth_date', 'question': "Quelle est ta date de naissance ? (format: JJ/MM/AAAA)", 'required': False},
            {'type': 'marital_status', 'question': "Es-tu marié(e), en couple, célibataire ?", 'required': False},
            {'type': 'spouse_name', 'question': "Quel est le nom de ton/ta conjoint(e) ?", 'required': False, 'depends_on': 'marital_status'},
            {'type': 'children', 'question': "As-tu des enfants ? Si oui, combien et quels sont leurs prénoms ?", 'required': False},
        ],
        'next_category': 'profession'
    },
    'profession': {
        'questions': [
            {'type': 'profession', 'question': "Quelle est ta profession ?", 'required': False},
            {'type': 'company', 'question': "Pour quelle entreprise travailles-tu ?", 'required': False},
            {'type': 'education', 'question': "Quelle est ta formation/éducation ?", 'required': False},
        ],
        'next_category': 'interests'
    },
    'interests': {
        'questions': [
            {'type': 'interests', 'question': "Quels sont tes centres d'intérêt ?", 'required': False},
            {'type': 'hobbies', 'question': "Quels sont tes hobbies/passions ?", 'required': False},
            {'type': 'languages', 'question': "Quelles langues parles-tu ?", 'required': False},
        ],
        'next_category': 'preferences'
    },
    'preferences': {
        'questions': [
            {'type': 'humor_style', 'question': "Quel est ton style d'humour ? (décontracté, formel, drôle, etc.)", 'required': False},
            {'type': 'preferred_emojis', 'question': "Quels emojis utilises-tu le plus souvent ?", 'required': False},
        ],
        'next_category': None  # End of questions
    }
}


def create_getting_to_know_session(
    db: Session,
    user_id: int
) -> ConversationSession:
    """
    Create a new "getting to know" session
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        ConversationSession object
    """
    try:
        # Generate unique conversation_id
        conversation_id = f"getting-to-know-{user_id}-{uuid.uuid4().hex[:8]}"
        
        session = ConversationSession(
            user_id=user_id,
            session_type='getting_to_know',
            title="Session 'Se connaître'",
            conversation_id=conversation_id
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        log_to_db(
            db,
            "INFO",
            f"Created getting-to-know session {session.id} for user {user_id}",
            service="getting_to_know_session",
            user_id=user_id,
            metadata={"session_id": session.id, "conversation_id": conversation_id}
        )
        
        return session
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error creating getting-to-know session: {str(e)}",
            service="getting_to_know_session",
            user_id=user_id
        )
        raise


def get_next_question(
    db: Session,
    session_id: int,
    last_answer: Optional[str] = None,
    last_question_type: Optional[str] = None
) -> Dict[str, any]:
    """
    Get the next question in the getting-to-know session
    
    Args:
        db: Database session
        session_id: Session ID
        last_answer: Answer to the previous question (if any)
        last_question_type: Type of the previous question (if any)
    
    Returns:
        Dict with question info or completion message
    """
    try:
        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if not session:
            return {'error': 'Session not found'}
        
        # Save last answer if provided
        if last_answer and last_question_type:
            save_answer_to_user_info(db, session_id, last_question_type, last_answer)
        
        # Get all answered questions for this session
        answered_questions = db.query(UserInfo).filter(
            UserInfo.user_id == session.user_id,
            UserInfo.info_type.in_([q['type'] for category in QUESTION_CATEGORIES.values() for q in category['questions']])
        ).all()
        
        answered_types = {info.info_type for info in answered_questions}
        
        # Find next unanswered question
        current_category = 'identity'  # Start with identity
        
        # Determine current category based on what's been answered
        if 'first_name' in answered_types or 'last_name' in answered_types:
            current_category = 'location'
        if any(t in answered_types for t in ['birth_place', 'current_city', 'current_country']):
            current_category = 'personal'
        if any(t in answered_types for t in ['birth_date', 'marital_status', 'children']):
            current_category = 'profession'
        if any(t in answered_types for t in ['profession', 'company', 'education']):
            current_category = 'interests'
        if any(t in answered_types for t in ['interests', 'hobbies', 'languages']):
            current_category = 'preferences'
        
        # Get questions for current category
        category_data = QUESTION_CATEGORIES.get(current_category)
        if not category_data:
            # All questions answered
            return {
                'completed': True,
                'message': "Merci ! J'ai maintenant une bonne compréhension de qui tu es. Je vais utiliser ces informations pour mieux t'aider à l'avenir."
            }
        
        # Find first unanswered question in category
        for question_data in category_data['questions']:
            question_type = question_data['type']
            
            # Check dependencies
            if 'depends_on' in question_data:
                depends_on = question_data['depends_on']
                if depends_on not in answered_types:
                    continue  # Skip if dependency not met
            
            # Check if already answered
            if question_type in answered_types:
                continue
            
            # Return this question
            return {
                'question': question_data['question'],
                'question_type': question_type,
                'required': question_data.get('required', False),
                'category': current_category,
                'progress': {
                    'answered': len(answered_types),
                    'total': sum(len(cat['questions']) for cat in QUESTION_CATEGORIES.values())
                }
            }
        
        # All questions in current category answered, move to next
        next_category = category_data.get('next_category')
        if next_category:
            next_category_data = QUESTION_CATEGORIES.get(next_category)
            if next_category_data:
                for question_data in next_category_data['questions']:
                    question_type = question_data['type']
                    if question_type not in answered_types:
                        if 'depends_on' not in question_data or question_data['depends_on'] in answered_types:
                            return {
                                'question': question_data['question'],
                                'question_type': question_type,
                                'required': question_data.get('required', False),
                                'category': next_category,
                                'progress': {
                                    'answered': len(answered_types),
                                    'total': sum(len(cat['questions']) for cat in QUESTION_CATEGORIES.values())
                                }
                            }
        
        # All questions answered
        return {
            'completed': True,
            'message': "Merci ! J'ai maintenant une bonne compréhension de qui tu es. Je vais utiliser ces informations pour mieux t'aider à l'avenir."
        }
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error getting next question: {str(e)}",
            service="getting_to_know_session",
            user_id=session.user_id if 'session' in locals() else None
        )
        return {'error': str(e)}


def save_answer_to_user_info(
    db: Session,
    session_id: int,
    question_type: str,
    answer: str
) -> UserInfo:
    """
    Save answer to user_info table
    
    Args:
        db: Database session
        session_id: Session ID
        question_type: Type of question (maps to info_type)
        answer: User's answer
    
    Returns:
        UserInfo object
    """
    try:
        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if not session:
            raise ValueError("Session not found")
        
        # Handle special cases for complex data types
        info_value = answer
        info_value_json = None
        
        if question_type == 'children':
            # Parse children answer (could be "oui, 2 enfants: Alice et Bob" or "non")
            if answer.lower().startswith(('non', 'aucun', 'pas')):
                info_value = "Aucun enfant"
            else:
                # Try to extract children names
                info_value = answer
                # Could use LLM to extract structured data here
        elif question_type in ['interests', 'hobbies', 'languages', 'preferred_emojis']:
            # Store as JSON array if it's a list
            if ',' in answer or 'et' in answer.lower():
                items = [item.strip() for item in answer.replace('et', ',').split(',')]
                info_value_json = items
                info_value = ', '.join(items)
            else:
                info_value = answer
        
        # Get or create user_info
        user_info = db.query(UserInfo).filter(
            UserInfo.user_id == session.user_id,
            UserInfo.info_type == question_type
        ).first()
        
        if user_info:
            user_info.info_value = info_value
            user_info.info_value_json = info_value_json
            user_info.updated_at = datetime.utcnow()
        else:
            user_info = UserInfo(
                user_id=session.user_id,
                info_type=question_type,
                info_value=info_value,
                info_value_json=info_value_json
            )
            db.add(user_info)
        
        db.commit()
        db.refresh(user_info)
        
        log_to_db(
            db,
            "INFO",
            f"Saved answer for {question_type} in session {session_id}",
            service="getting_to_know_session",
            user_id=session.user_id,
            metadata={"session_id": session_id, "question_type": question_type}
        )
        
        return user_info
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error saving answer: {str(e)}",
            service="getting_to_know_session",
            user_id=session.user_id if 'session' in locals() else None
        )
        raise


