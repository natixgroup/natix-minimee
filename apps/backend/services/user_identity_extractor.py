"""
User identity extraction service
Extracts user information from RAG embeddings and syncs with user_info table
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from models import User, UserInfo
from services.embeddings import generate_embedding
from services.rag_llamaindex import find_similar_messages_enhanced
from services.logs_service import log_to_db
import json


def extract_user_identity_from_rag(
    db: Session,
    user_id: int,
    limit: int = 20,
    threshold: float = 0.15
) -> Dict[str, Any]:
    """
    Extract user identity information from RAG embeddings
    
    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of results to retrieve
        threshold: Similarity threshold
    
    Returns:
        Dictionary with extracted information organized by type
    """
    try:
        # Get user email
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}
        
        user_email = user.email
        
        # Define queries to extract different types of information
        queries = {
            'name': [
                f"nom de {user_email}",
                f"prénom de {user_email}",
                f"qui est {user_email}",
                f"identité de {user_email}",
                f"nom complet de {user_email}"
            ],
            'location': [
                f"adresse de {user_email}",
                f"ville de {user_email}",
                f"pays de {user_email}",
                f"où habite {user_email}",
                f"localisation de {user_email}"
            ],
            'profession': [
                f"profession de {user_email}",
                f"travail de {user_email}",
                f"emploi de {user_email}",
                f"entreprise de {user_email}",
                f"métier de {user_email}"
            ],
            'personal': [
                f"date de naissance de {user_email}",
                f"âge de {user_email}",
                f"marié {user_email}",
                f"enfants de {user_email}",
                f"famille de {user_email}"
            ],
            'preferences': [
                f"préférences de {user_email}",
                f"centres d'intérêt de {user_email}",
                f"hobbies de {user_email}",
                f"humour de {user_email}",
                f"emojis préférés de {user_email}"
            ]
        }
        
        extracted_info = {}
        
        # Search for each type of information
        for info_type, query_list in queries.items():
            all_results = []
            
            for query in query_list:
                results = find_similar_messages_enhanced(
                    db=db,
                    query_text=query,
                    limit=limit,
                    threshold=threshold,
                    user_id=user_id,
                    use_chunks=True
                )
                
                # Filter results from Gmail source (most reliable for user info)
                # Results format: dict with 'message' (Message object), 'similarity', etc.
                gmail_results = []
                for r in results:
                    msg = r.get('message')
                    if msg and hasattr(msg, 'source') and msg.source == 'gmail':
                        gmail_results.append(r)
                all_results.extend(gmail_results)
            
            # Deduplicate by message content
            seen_contents = set()
            unique_results = []
            for result in all_results:
                msg = result.get('message')
                if msg and hasattr(msg, 'content'):
                    content = msg.content
                    if content and content not in seen_contents:
                        seen_contents.add(content)
                        unique_results.append(result)
            
            # Sort by similarity and take top results
            unique_results.sort(key=lambda x: x.get('similarity', 0) or 0, reverse=True)
            extracted_info[info_type] = unique_results[:10]  # Top 10 per type
        
        log_to_db(
            db,
            "INFO",
            f"Extracted user identity information for user {user_id}: {len(extracted_info)} types found",
            service="user_identity_extractor",
            user_id=user_id,
            metadata={"types_found": list(extracted_info.keys())}
        )
        
        return extracted_info
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error extracting user identity: {str(e)}",
            service="user_identity_extractor",
            user_id=user_id
        )
        return {}


def sync_user_info_from_rag(
    db: Session,
    user_id: int,
    force_update: bool = False
) -> Dict[str, int]:
    """
    Sync user_info table with extracted information from RAG
    
    Args:
        db: Database session
        user_id: User ID
        force_update: If True, update existing user_info even if it exists
    
    Returns:
        Dictionary with counts: created, updated, skipped
    """
    try:
        extracted = extract_user_identity_from_rag(db, user_id)
        
        stats = {'created': 0, 'updated': 0, 'skipped': 0}
        
        # Map info types to user_info types
        info_type_mapping = {
            'name': ['first_name', 'last_name'],
            'location': ['address', 'city', 'country'],
            'profession': ['profession', 'company'],
            'personal': ['birth_date', 'marital_status', 'spouse_name', 'children'],
            'preferences': ['interests', 'hobbies', 'humor_style', 'preferred_emojis']
        }
        
        # Process extracted information
        for category, results in extracted.items():
            if not results:
                continue
            
            # Extract text from results (format: dict with 'message' object)
            text_parts = []
            for r in results[:5]:
                msg = r.get('message')
                if msg and hasattr(msg, 'content'):
                    text_parts.append(msg.content)
            combined_text = " ".join(text_parts)
            
            # For now, we'll create a general info entry
            # In a more sophisticated version, we could use LLM to extract structured data
            if category in info_type_mapping:
                for info_type in info_type_mapping[category]:
                    # Check if user_info already exists
                    existing = db.query(UserInfo).filter(
                        UserInfo.user_id == user_id,
                        UserInfo.info_type == info_type
                    ).first()
                    
                    if existing:
                        if force_update:
                            existing.info_value = combined_text[:500]  # Limit length
                            existing.updated_at = datetime.utcnow()
                            db.commit()
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        new_info = UserInfo(
                            user_id=user_id,
                            info_type=info_type,
                            info_value=combined_text[:500]
                        )
                        db.add(new_info)
                        db.commit()
                        stats['created'] += 1
        
        log_to_db(
            db,
            "INFO",
            f"Synced user_info for user {user_id}: {stats}",
            service="user_identity_extractor",
            user_id=user_id,
            metadata=stats
        )
        
        return stats
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error syncing user_info: {str(e)}",
            service="user_identity_extractor",
            user_id=user_id
        )
        return {'created': 0, 'updated': 0, 'skipped': 0, 'error': str(e)}


def get_user_context_for_agent(
    db: Session,
    user_id: int,
    relation_type_id: Optional[int] = None,
    contact_id: Optional[int] = None
) -> str:
    """
    Get formatted user context for agent prompt, filtered by visibility rules
    
    Args:
        db: Database session
        user_id: User ID
        relation_type_id: Optional relation type ID to filter visibilities
        contact_id: Optional contact ID to filter visibilities
    
    Returns:
        Formatted string with user information
    """
    try:
        from models import UserInfoVisibility
        
        # Get all user_info for this user
        user_infos = db.query(UserInfo).filter(UserInfo.user_id == user_id).all()
        
        if not user_infos:
            return ""
        
        context_parts = []
        
        for user_info in user_infos:
            # Check visibility rules
            visibilities = db.query(UserInfoVisibility).filter(
                UserInfoVisibility.user_info_id == user_info.id
            ).all()
            
            # Determine if this info can be used
            can_use = False
            can_say = False
            
            # Check global rules (relation_type_id and contact_id both NULL)
            global_visibility = next(
                (v for v in visibilities if v.relation_type_id is None and v.contact_id is None),
                None
            )
            
            # Check specific rules
            specific_visibility = None
            if relation_type_id:
                specific_visibility = next(
                    (v for v in visibilities if v.relation_type_id == relation_type_id and v.contact_id is None),
                    None
                )
            elif contact_id:
                specific_visibility = next(
                    (v for v in visibilities if v.contact_id == contact_id),
                    None
                )
            
            # Use specific rule if available, otherwise global
            visibility = specific_visibility or global_visibility
            
            if visibility:
                # Check if forbidden
                if visibility.forbidden_for_response and visibility.forbidden_to_say:
                    continue  # Skip this info completely
                
                can_use = visibility.can_use_for_response and not visibility.forbidden_for_response
                can_say = visibility.can_say_explicitly and not visibility.forbidden_to_say
            else:
                # Default: can use but not say explicitly if no rule exists
                can_use = True
                can_say = False
            
            if can_use:
                info_label = user_info.info_type.replace('_', ' ').title()
                info_value = user_info.info_value or (json.dumps(user_info.info_value_json) if user_info.info_value_json else '')
                
                if can_say:
                    context_parts.append(f"{info_label}: {info_value}")
                else:
                    # Can use but not say explicitly - add as context only
                    context_parts.append(f"[Context only - do not mention] {info_label}: {info_value}")
        
        if context_parts:
            return "\n".join(context_parts)
        
        return ""
        
    except Exception as e:
        log_to_db(
            db,
            "ERROR",
            f"Error getting user context: {str(e)}",
            service="user_identity_extractor",
            user_id=user_id
        )
        return ""

