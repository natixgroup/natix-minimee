"""
WhatsApp Integration Service
Handles business logic for WhatsApp integrations (user and minimee accounts)
"""
from sqlalchemy.orm import Session
from typing import Optional
from models import WhatsAppIntegration


def get_integration_by_type(
    db: Session,
    user_id: int,
    integration_type: str  # 'user' or 'minimee'
) -> Optional[WhatsAppIntegration]:
    """Get integration by type for a user"""
    return db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.user_id == user_id,
        WhatsAppIntegration.integration_type == integration_type
    ).first()


def get_user_integration(db: Session, user_id: int) -> Optional[WhatsAppIntegration]:
    """Get user WhatsApp integration"""
    return get_integration_by_type(db, user_id, 'user')


def get_minimee_integration(db: Session, user_id: int) -> Optional[WhatsAppIntegration]:
    """Get Minimee WhatsApp integration"""
    return get_integration_by_type(db, user_id, 'minimee')


def update_integration_status(
    db: Session,
    integration: WhatsAppIntegration,
    status: str,  # 'connected', 'disconnected', 'pending'
    phone_number: Optional[str] = None,
    display_name: Optional[str] = None
) -> WhatsAppIntegration:
    """Update integration status and metadata"""
    integration.status = status
    if phone_number is not None:
        integration.phone_number = phone_number
    if display_name is not None:
        integration.display_name = display_name
    db.commit()
    db.refresh(integration)
    return integration


def get_user_phone_number(db: Session, user_id: int) -> Optional[str]:
    """Get user's WhatsApp phone number"""
    integration = get_user_integration(db, user_id)
    return integration.phone_number if integration else None


def get_minimee_phone_number(db: Session, user_id: int) -> Optional[str]:
    """Get Minimee's WhatsApp phone number"""
    integration = get_minimee_integration(db, user_id)
    return integration.phone_number if integration else None


