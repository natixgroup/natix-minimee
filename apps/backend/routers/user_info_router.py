"""
User Info Router
Handles CRUD operations for user information and visibility management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import get_db
from models import UserInfo, UserInfoVisibility, User, RelationType, Contact
from schemas import (
    UserInfoCreate, UserInfoUpdate, UserInfoResponse,
    UserInfoVisibilityCreate, UserInfoVisibilityUpdate, UserInfoVisibilityResponse
)
from services.user_identity_extractor import get_user_context_for_agent
from services.logs_service import log_to_db

router = APIRouter(prefix="/user-info", tags=["user-info"])


@router.get("", response_model=List[UserInfoResponse])
async def get_user_infos(
    user_id: int = Query(...),
    info_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get all user information for a user, optionally filtered by type
    """
    query = db.query(UserInfo).filter(UserInfo.user_id == user_id)
    
    if info_type:
        query = query.filter(UserInfo.info_type == info_type)
    
    user_infos = query.order_by(UserInfo.info_type).all()
    return user_infos


@router.get("/{user_info_id}", response_model=UserInfoResponse)
async def get_user_info(
    user_info_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get a specific user info by ID
    """
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    return user_info


@router.post("", response_model=UserInfoResponse)
async def create_user_info(
    user_info_data: UserInfoCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Create a new user info entry
    """
    # Check if info_type already exists for this user
    existing = db.query(UserInfo).filter(
        UserInfo.user_id == user_id,
        UserInfo.info_type == user_info_data.info_type
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User info of type '{user_info_data.info_type}' already exists. Use PUT to update."
        )
    
    user_info = UserInfo(
        user_id=user_id,
        info_type=user_info_data.info_type,
        info_value=user_info_data.info_value,
        info_value_json=user_info_data.info_value_json
    )
    
    db.add(user_info)
    db.commit()
    db.refresh(user_info)
    
    log_to_db(
        db,
        "INFO",
        f"Created user_info {user_info.id} for user {user_id}",
        service="user_info_router",
        user_id=user_id,
        metadata={"user_info_id": user_info.id, "info_type": user_info_data.info_type}
    )
    
    return user_info


@router.put("/{user_info_id}", response_model=UserInfoResponse)
async def update_user_info(
    user_info_id: int,
    user_info_data: UserInfoUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Update an existing user info entry
    """
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    if user_info_data.info_value is not None:
        user_info.info_value = user_info_data.info_value
    if user_info_data.info_value_json is not None:
        user_info.info_value_json = user_info_data.info_value_json
    
    user_info.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user_info)
    
    log_to_db(
        db,
        "INFO",
        f"Updated user_info {user_info.id} for user {user_id}",
        service="user_info_router",
        user_id=user_id,
        metadata={"user_info_id": user_info.id}
    )
    
    return user_info


@router.delete("/{user_info_id}")
async def delete_user_info(
    user_info_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Delete a user info entry (also deletes all visibilities)
    """
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    db.delete(user_info)
    db.commit()
    
    log_to_db(
        db,
        "INFO",
        f"Deleted user_info {user_info_id} for user {user_id}",
        service="user_info_router",
        user_id=user_id,
        metadata={"user_info_id": user_info_id}
    )
    
    return {"message": "User info deleted successfully"}


@router.get("/{user_info_id}/visibility", response_model=List[UserInfoVisibilityResponse])
async def get_user_info_visibilities(
    user_info_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get all visibility rules for a user info
    """
    # Verify user_info belongs to user
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    visibilities = db.query(UserInfoVisibility).filter(
        UserInfoVisibility.user_info_id == user_info_id
    ).all()
    
    return visibilities


@router.post("/{user_info_id}/visibility", response_model=UserInfoVisibilityResponse)
async def create_user_info_visibility(
    user_info_id: int,
    visibility_data: UserInfoVisibilityCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Create a visibility rule for a user info
    """
    # Verify user_info belongs to user
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    # Verify relation_type if provided
    if visibility_data.relation_type_id:
        relation_type = db.query(RelationType).filter(
            RelationType.id == visibility_data.relation_type_id
        ).first()
        if not relation_type:
            raise HTTPException(status_code=404, detail="Relation type not found")
    
    # Verify contact if provided
    if visibility_data.contact_id:
        contact = db.query(Contact).filter(
            Contact.id == visibility_data.contact_id,
            Contact.user_id == user_id
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
    
    # Check if visibility already exists
    existing = db.query(UserInfoVisibility).filter(
        UserInfoVisibility.user_info_id == user_info_id,
        UserInfoVisibility.relation_type_id == visibility_data.relation_type_id,
        UserInfoVisibility.contact_id == visibility_data.contact_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Visibility rule already exists for this combination"
        )
    
    visibility = UserInfoVisibility(
        user_info_id=user_info_id,
        relation_type_id=visibility_data.relation_type_id,
        contact_id=visibility_data.contact_id,
        can_use_for_response=visibility_data.can_use_for_response,
        can_say_explicitly=visibility_data.can_say_explicitly,
        forbidden_for_response=visibility_data.forbidden_for_response,
        forbidden_to_say=visibility_data.forbidden_to_say
    )
    
    db.add(visibility)
    db.commit()
    db.refresh(visibility)
    
    return visibility


@router.put("/{user_info_id}/visibility/{visibility_id}", response_model=UserInfoVisibilityResponse)
async def update_user_info_visibility(
    user_info_id: int,
    visibility_id: int,
    visibility_data: UserInfoVisibilityUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Update a visibility rule
    """
    # Verify user_info belongs to user
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    visibility = db.query(UserInfoVisibility).filter(
        UserInfoVisibility.id == visibility_id,
        UserInfoVisibility.user_info_id == user_info_id
    ).first()
    
    if not visibility:
        raise HTTPException(status_code=404, detail="Visibility rule not found")
    
    if visibility_data.can_use_for_response is not None:
        visibility.can_use_for_response = visibility_data.can_use_for_response
    if visibility_data.can_say_explicitly is not None:
        visibility.can_say_explicitly = visibility_data.can_say_explicitly
    if visibility_data.forbidden_for_response is not None:
        visibility.forbidden_for_response = visibility_data.forbidden_for_response
    if visibility_data.forbidden_to_say is not None:
        visibility.forbidden_to_say = visibility_data.forbidden_to_say
    
    visibility.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(visibility)
    
    return visibility


@router.delete("/{user_info_id}/visibility/{visibility_id}")
async def delete_user_info_visibility(
    user_info_id: int,
    visibility_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Delete a visibility rule
    """
    # Verify user_info belongs to user
    user_info = db.query(UserInfo).filter(
        UserInfo.id == user_info_id,
        UserInfo.user_id == user_id
    ).first()
    
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")
    
    visibility = db.query(UserInfoVisibility).filter(
        UserInfoVisibility.id == visibility_id,
        UserInfoVisibility.user_info_id == user_info_id
    ).first()
    
    if not visibility:
        raise HTTPException(status_code=404, detail="Visibility rule not found")
    
    db.delete(visibility)
    db.commit()
    
    return {"message": "Visibility rule deleted successfully"}


@router.get("/context/for-agent")
async def get_user_context_for_agent_endpoint(
    user_id: int = Query(...),
    relation_type_id: Optional[int] = Query(None),
    contact_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get formatted user context for agent prompt, filtered by visibility rules
    """
    context = get_user_context_for_agent(
        db=db,
        user_id=user_id,
        relation_type_id=relation_type_id,
        contact_id=contact_id
    )
    
    return {"context": context}


