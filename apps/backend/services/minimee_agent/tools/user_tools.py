"""
LangChain tools for user preferences and settings
"""
from typing import Optional, Dict, Any
from langchain.tools import tool
from sqlalchemy.orm import Session
from models import Setting, User
from services.logs_service import log_to_db


@tool
def get_user_preferences(user_id: int) -> str:
    """
    Get user preferences and communication style.
    Returns user settings and preferences that can inform agent behavior.
    
    Args:
        user_id: User ID
    
    Returns:
        Formatted string with user preferences
    """
    return f"Getting preferences for user {user_id}"


def create_get_user_preferences_tool(db: Session, user_id: int):
    """
    Create get_user_preferences tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def get_user_preferences_tool() -> str:
        """Get user preferences"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return f"User {user_id} not found"
            
            # Get user settings
            settings = db.query(Setting).filter(
                Setting.user_id == user_id
            ).all()
            
            results = [f"User: {user.name or user.email}"]
            
            for setting in settings:
                results.append(f"{setting.key}: {setting.value}")
            
            if len(results) == 1:
                return "No preferences configured"
            
            return "\n".join(results)
        except Exception as e:
            log_to_db(db, "ERROR", f"Get user preferences failed: {str(e)}", service="minimee_agent")
            return f"Error retrieving preferences: {str(e)}"
    
    get_user_preferences_tool.name = "get_user_preferences"
    get_user_preferences_tool.description = (
        "Get user preferences and communication style. "
        "Returns user settings and preferences that can inform agent behavior."
    )
    
    return get_user_preferences_tool


@tool
def get_user_settings(user_id: int) -> str:
    """
    Get user system settings (LLM provider, embedding model, etc.).
    Returns technical configuration settings.
    
    Args:
        user_id: User ID
    
    Returns:
        Formatted string with user settings
    """
    return f"Getting settings for user {user_id}"


def create_get_user_settings_tool(db: Session, user_id: int):
    """
    Create get_user_settings tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def get_user_settings_tool() -> str:
        """Get user system settings"""
        try:
            from services.llm_router import get_llm_provider_from_db
            provider, model = get_llm_provider_from_db(db)
            
            results = [
                f"LLM Provider: {provider}",
                f"LLM Model: {model or 'default'}"
            ]
            
            return "\n".join(results)
        except Exception as e:
            log_to_db(db, "ERROR", f"Get user settings failed: {str(e)}", service="minimee_agent")
            return f"Error retrieving settings: {str(e)}"
    
    get_user_settings_tool.name = "get_user_settings"
    get_user_settings_tool.description = (
        "Get user system settings (LLM provider, embedding model, etc.). "
        "Returns technical configuration settings."
    )
    
    return get_user_settings_tool


@tool
def update_user_preference(key: str, value: Any, user_id: int) -> str:
    """
    Update a user preference setting.
    Note: This is a read-only operation in most cases. Actual updates require proper permissions.
    
    Args:
        key: Setting key
        value: Setting value
        user_id: User ID
    
    Returns:
        Status message
    """
    return f"Updating preference {key} for user {user_id}"


def create_update_user_preference_tool(db: Session, user_id: int):
    """
    Create update_user_preference tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def update_user_preference_tool(key: str, value: str) -> str:
        """Update user preference (read-only for now)"""
        # For now, this is read-only - agents shouldn't modify user settings
        # Return informative message
        return f"Preference updates are not available through the agent. Please use the dashboard to update {key}."
    
    update_user_preference_tool.name = "update_user_preference"
    update_user_preference_tool.description = (
        "Update a user preference setting. "
        "Note: This is a read-only operation. Actual updates require dashboard access."
    )
    
    return update_user_preference_tool



