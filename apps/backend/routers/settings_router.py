"""
Settings management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.database import get_db
from models import Setting
from schemas import SettingCreate, SettingResponse

router = APIRouter()


@router.get("/settings", response_model=List[SettingResponse])
async def list_settings(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List all settings, optionally filtered by user"""
    query = db.query(Setting)
    if user_id:
        query = query.filter(Setting.user_id == user_id)
    else:
        query = query.filter(Setting.user_id == None)  # Global settings
    return query.all()


@router.get("/settings/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get specific setting by key"""
    query = db.query(Setting).filter(Setting.key == key)
    if user_id:
        query = query.filter(Setting.user_id == user_id)
    else:
        query = query.filter(Setting.user_id == None)
    
    setting = query.first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.post("/settings", response_model=SettingResponse)
async def create_setting(
    setting_data: SettingCreate,
    db: Session = Depends(get_db)
):
    """Create or update setting"""
    # Check if exists
    query = db.query(Setting).filter(Setting.key == setting_data.key)
    if setting_data.user_id:
        query = query.filter(Setting.user_id == setting_data.user_id)
    else:
        query = query.filter(Setting.user_id == None)
    
    existing = query.first()
    
    if existing:
        # Update
        existing.value = setting_data.value
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create
        setting = Setting(**setting_data.model_dump())
        db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

