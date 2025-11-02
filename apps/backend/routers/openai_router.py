"""
OpenAI API key management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from db.database import get_db
from models import Setting
from schemas import SettingCreate, SettingResponse
from pydantic import BaseModel
import httpx
from config import settings

router = APIRouter(prefix="/openai", tags=["openai"])


class OpenAIKeyRequest(BaseModel):
    api_key: str


class OpenAIKeyResponse(BaseModel):
    configured: bool
    valid: bool
    message: str
    masked_key: Optional[str] = None


@router.post("/validate", response_model=OpenAIKeyResponse)
async def validate_openai_key(
    request: OpenAIKeyRequest,
    db: Session = Depends(get_db)
):
    """
    Validate OpenAI API key by making a test request
    """
    try:
        # Test the API key with a simple request (GET /v1/models is the correct endpoint)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                }
            )
            
            if response.status_code == 200:
                # Key is valid - save it
                setting = Setting(
                    key="openai_api_key",
                    value={"api_key": request.api_key},
                    user_id=None  # Global setting
                )
                
                # Check if exists, update or create
                existing = db.query(Setting).filter(
                    Setting.key == "openai_api_key",
                    Setting.user_id == None
                ).first()
                
                if existing:
                    existing.value = {"api_key": request.api_key}
                else:
                    db.add(setting)
                
                db.commit()
                
                # Mask the key for response
                masked = request.api_key[:8] + "..." + request.api_key[-4:] if len(request.api_key) > 12 else "***"
                
                return OpenAIKeyResponse(
                    configured=True,
                    valid=True,
                    message="OpenAI API key validated and saved successfully",
                    masked_key=masked
                )
            elif response.status_code == 401:
                return OpenAIKeyResponse(
                    configured=False,
                    valid=False,
                    message="Invalid API key. Please check your key and try again."
                )
            else:
                return OpenAIKeyResponse(
                    configured=False,
                    valid=False,
                    message=f"API validation failed: {response.status_code}"
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OpenAI API timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating API key: {str(e)}")


@router.get("/status", response_model=OpenAIKeyResponse)
async def get_openai_status(
    db: Session = Depends(get_db)
):
    """
    Check if OpenAI API key is configured
    """
    # Check in database settings first
    setting = db.query(Setting).filter(
        Setting.key == "openai_api_key",
        Setting.user_id == None
    ).first()
    
    api_key = None
    if setting and isinstance(setting.value, dict):
        api_key = setting.value.get("api_key")
    
    # Fallback to environment variable
    if not api_key:
        api_key = settings.openai_api_key
    
    if not api_key:
        return OpenAIKeyResponse(
            configured=False,
            valid=False,
            message="OpenAI API key not configured"
        )
    
    # Mask the key
    masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    
    # Optionally validate the key
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                }
            )
            valid = response.status_code == 200
            message = "OpenAI API key is configured and valid" if valid else "OpenAI API key may be invalid"
            
            return OpenAIKeyResponse(
                configured=True,
                valid=valid,
                message=message,
                masked_key=masked
            )
    except:
        # If validation fails, assume configured but status unknown
        return OpenAIKeyResponse(
            configured=True,
            valid=False,
            message="OpenAI API key is configured but validation failed",
            masked_key=masked
        )


@router.delete("/key")
async def delete_openai_key(
    db: Session = Depends(get_db)
):
    """
    Remove OpenAI API key from settings
    """
    setting = db.query(Setting).filter(
        Setting.key == "openai_api_key",
        Setting.user_id == None
    ).first()
    
    if setting:
        db.delete(setting)
        db.commit()
    
    return {"message": "OpenAI API key removed"}

