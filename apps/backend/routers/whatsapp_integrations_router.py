"""
WhatsApp Integrations Router
Handles CRUD operations for WhatsApp integrations (user and minimee accounts)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.database import get_db
from models import WhatsAppIntegration
from schemas import (
    WhatsAppIntegrationCreate,
    WhatsAppIntegrationUpdate,
    WhatsAppIntegrationResponse
)

router = APIRouter(prefix="/whatsapp-integrations", tags=["whatsapp-integrations"])


@router.get("/", response_model=List[WhatsAppIntegrationResponse])
async def get_integrations(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """Get all WhatsApp integrations for a user"""
    integrations = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.user_id == user_id
    ).all()
    return integrations


@router.get("/{integration_type}", response_model=WhatsAppIntegrationResponse)
async def get_integration(
    integration_type: str,  # 'user' or 'minimee'
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """Get a specific integration by type"""
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.user_id == user_id,
        WhatsAppIntegration.integration_type == integration_type
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_type}' not found for user {user_id}")
    
    return integration


@router.post("/", response_model=WhatsAppIntegrationResponse)
async def create_integration(
    integration: WhatsAppIntegrationCreate,
    db: Session = Depends(get_db)
):
    """Create a new WhatsApp integration"""
    # Check if integration already exists
    existing = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.user_id == integration.user_id,
        WhatsAppIntegration.integration_type == integration.integration_type
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Integration '{integration.integration_type}' already exists for user {integration.user_id}"
        )
    
    db_integration = WhatsAppIntegration(**integration.dict())
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    return db_integration


@router.put("/{integration_type}", response_model=WhatsAppIntegrationResponse)
async def update_integration(
    integration_type: str,
    integration_update: WhatsAppIntegrationUpdate,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """Update an existing integration"""
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.user_id == user_id,
        WhatsAppIntegration.integration_type == integration_type
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_type}' not found for user {user_id}")
    
    # Update only provided fields
    update_data = integration_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(integration, field, value)
    
    db.commit()
    db.refresh(integration)
    return integration


@router.delete("/{integration_type}")
async def delete_integration(
    integration_type: str,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """Delete an integration"""
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.user_id == user_id,
        WhatsAppIntegration.integration_type == integration_type
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_type}' not found for user {user_id}")
    
    db.delete(integration)
    db.commit()
    return {"message": f"Integration '{integration_type}' deleted successfully"}


