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


def mask_sensitive_settings(setting: Setting) -> Setting:
    """
    Mask sensitive information in settings before returning to client
    """
    # Clone the setting to avoid modifying the original
    if setting.key in ["openai_api_key", "gmail_client_secret", "gmail_client_id"]:
        if isinstance(setting.value, dict):
            masked_value = setting.value.copy()
            # Mask API keys
            if "api_key" in masked_value:
                api_key = masked_value["api_key"]
                if api_key and len(api_key) > 12:
                    masked_value["api_key"] = api_key[:8] + "..." + api_key[-4:]
                else:
                    masked_value["api_key"] = "***"
            # Mask client secrets
            if "client_secret" in masked_value:
                secret = masked_value["client_secret"]
                if secret and len(secret) > 12:
                    masked_value["client_secret"] = secret[:8] + "..." + secret[-4:]
                else:
                    masked_value["client_secret"] = "***"
            if "client_id" in masked_value:
                client_id = masked_value["client_id"]
                if client_id and len(client_id) > 12:
                    masked_value["client_id"] = client_id[:8] + "..." + client_id[-4:]
                else:
                    masked_value["client_id"] = "***"
            # Create a new Setting object with masked value
            from models import Setting as SettingModel
            from datetime import datetime
            masked_setting = SettingModel(
                id=setting.id,
                key=setting.key,
                value=masked_value,
                user_id=setting.user_id,
                created_at=setting.created_at,
                updated_at=setting.updated_at
            )
            return masked_setting
    return setting


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
    settings_list = query.all()
    # Mask sensitive settings before returning
    return [mask_sensitive_settings(s) for s in settings_list]


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
    # Mask sensitive settings before returning
    return mask_sensitive_settings(setting)


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

