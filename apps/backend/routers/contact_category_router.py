"""
Contact Category Router
Handles CRUD operations for contact categories and classification
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import get_db
from models import ContactCategory, Contact, User
from schemas import ContactCategoryCreate, ContactCategoryUpdate, ContactCategoryResponse
from services.contact_classifier import (
    classify_contact_from_messages,
    classify_contact_from_gmail,
    classify_contact_from_whatsapp,
    auto_classify_and_notify
)
from services.logs_service import log_to_db

router = APIRouter(prefix="/contact-categories", tags=["contact-categories"])


@router.get("", response_model=List[ContactCategoryResponse])
async def get_contact_categories(
    user_id: Optional[int] = Query(None),
    category_type: Optional[str] = Query(None),
    include_system: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Get all contact categories (system + user-created)
    """
    query = db.query(ContactCategory)
    
    if not include_system:
        query = query.filter(ContactCategory.is_system == False)
    
    if user_id is not None:
        # Get system categories + user's custom categories
        query = query.filter(
            (ContactCategory.is_system == True) | (ContactCategory.user_id == user_id)
        )
    else:
        # Get all system categories
        query = query.filter(ContactCategory.is_system == True)
    
    if category_type:
        query = query.filter(ContactCategory.category_type == category_type)
    
    categories = query.order_by(
        ContactCategory.is_system.desc(),
        ContactCategory.category_type,
        ContactCategory.display_order
    ).all()
    
    # Manually map meta_data to metadata for each category
    result = []
    for cat in categories:
        cat_dict = {
            "id": cat.id,
            "code": cat.code,
            "label": cat.label,
            "category_type": cat.category_type,
            "is_system": cat.is_system,
            "user_id": cat.user_id,
            "display_order": cat.display_order,
            "metadata": cat.meta_data,  # Map meta_data to metadata
            "created_at": cat.created_at,
            "updated_at": cat.updated_at,
        }
        result.append(ContactCategoryResponse(**cat_dict))
    
    return result


@router.get("/{category_id}", response_model=ContactCategoryResponse)
async def get_contact_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific contact category by ID
    """
    category = db.query(ContactCategory).filter(ContactCategory.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Contact category not found")
    
    return category


@router.post("", response_model=ContactCategoryResponse)
async def create_contact_category(
    category_data: ContactCategoryCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Create a custom contact category (system categories cannot be created via API)
    """
    # Check if code already exists for this user (or globally if system)
    existing = db.query(ContactCategory).filter(
        ContactCategory.code == category_data.code,
        (ContactCategory.is_system == True) | (ContactCategory.user_id == user_id)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Category with code '{category_data.code}' already exists"
        )
    
    category = ContactCategory(
        code=category_data.code,
        label=category_data.label,
        category_type=category_data.category_type,
        is_system=False,
        user_id=user_id,
        display_order=category_data.display_order or 0,
        meta_data=category_data.metadata
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    log_to_db(
        db,
        "INFO",
        f"Created contact category {category.id} for user {user_id}",
        service="contact_category_router",
        user_id=user_id,
        metadata={"category_id": category.id, "code": category_data.code}
    )
    
    return category


@router.put("/{category_id}", response_model=ContactCategoryResponse)
async def update_contact_category(
    category_id: int,
    category_data: ContactCategoryUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Update a contact category (only user-created categories can be updated)
    """
    category = db.query(ContactCategory).filter(
        ContactCategory.id == category_id,
        ContactCategory.user_id == user_id,
        ContactCategory.is_system == False
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=404,
            detail="Contact category not found or cannot be updated (system categories are read-only)"
        )
    
    if category_data.label is not None:
        category.label = category_data.label
    if category_data.category_type is not None:
        category.category_type = category_data.category_type
    if category_data.display_order is not None:
        category.display_order = category_data.display_order
    if category_data.metadata is not None:
        category.meta_data = category_data.metadata
    
    category.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(category)
    
    return category


@router.delete("/{category_id}")
async def delete_contact_category(
    category_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Delete a contact category (only user-created categories can be deleted)
    """
    category = db.query(ContactCategory).filter(
        ContactCategory.id == category_id,
        ContactCategory.user_id == user_id,
        ContactCategory.is_system == False
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=404,
            detail="Contact category not found or cannot be deleted (system categories cannot be deleted)"
        )
    
    # Set contacts using this category to None or 'autres'
    autres_category = db.query(ContactCategory).filter(
        ContactCategory.code == 'autres',
        ContactCategory.is_system == True
    ).first()
    
    if autres_category:
        db.query(Contact).filter(
            Contact.contact_category_id == category_id
        ).update({"contact_category_id": autres_category.id})
    
    db.delete(category)
    db.commit()
    
    return {"message": "Contact category deleted successfully"}


@router.post("/contacts/{contact_id}/classify")
async def classify_contact(
    contact_id: int,
    user_id: int = Query(...),
    source: Optional[str] = Query(None),  # 'gmail' or 'whatsapp'
    db: Session = Depends(get_db)
):
    """
    Manually trigger classification for a contact
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == user_id
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Determine source if not provided
    if not source:
        # Check messages to determine source
        from models import Message
        message = db.query(Message).filter(
            Message.conversation_id == contact.conversation_id,
            Message.user_id == user_id
        ).first()
        if message:
            source = message.source
        else:
            raise HTTPException(status_code=400, detail="Cannot determine source. Please specify source parameter.")
    
    # Classify based on source
    if source == 'gmail':
        category_id, confidence, reasoning = classify_contact_from_gmail(
            db, user_id, contact.conversation_id
        )
    elif source == 'whatsapp':
        category_id, confidence, reasoning = classify_contact_from_whatsapp(
            db, user_id, contact.conversation_id
        )
    else:
        raise HTTPException(status_code=400, detail="Source must be 'gmail' or 'whatsapp'")
    
    if category_id:
        contact.contact_category_id = category_id
        db.commit()
        db.refresh(contact)
    
    return {
        "contact_id": contact_id,
        "category_id": category_id,
        "confidence": confidence,
        "reasoning": reasoning,
        "auto_assigned": confidence >= 0.7
    }


@router.put("/contacts/{contact_id}/category")
async def update_contact_category_manual(
    contact_id: int,
    category_id: Optional[int] = Query(None),
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Manually set category for a contact
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == user_id
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    if category_id is not None:
        # Verify category exists
        category = db.query(ContactCategory).filter(ContactCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        contact.contact_category_id = category_id
    else:
        contact.contact_category_id = None
    
    db.commit()
    db.refresh(contact)
    
    return {
        "contact_id": contact_id,
        "category_id": contact.contact_category_id,
        "message": "Category updated successfully"
    }

