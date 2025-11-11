"""
Factory for creating and caching MinimeeAgent instances
Singleton pattern with cache per agent_id
"""
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from langchain_core.language_models import BaseLanguageModel
from models import Agent
from .agent import MinimeeAgent
from .llm_wrapper import create_minimee_llm
from services.logs_service import log_to_db


# Global cache for agent instances
_agent_cache: Dict[int, MinimeeAgent] = {}


def get_or_create_agent(
    agent_id: int,
    db: Session,
    user_id: int,
    llm: Optional[BaseLanguageModel] = None,
    conversation_id: Optional[str] = None,
    force_recreate: bool = False,
    included_sources: Optional[List[str]] = None
) -> MinimeeAgent:
    """
    Get or create MinimeeAgent instance (cached singleton per agent_id)
    
    Args:
        agent_id: Agent ID
        db: Database session
        user_id: User ID
        llm: Optional LangChain LLM (will create if not provided)
        conversation_id: Optional conversation ID
        force_recreate: Force recreation even if cached
        included_sources: List of sources to include in RAG context (whatsapp, gmail). If None or empty, all sources included.
    
    Returns:
        MinimeeAgent instance
    """
    # Check cache
    if not force_recreate and agent_id in _agent_cache:
        cached_agent = _agent_cache[agent_id]
        # Update conversation_id if provided
        if conversation_id and cached_agent.conversation_id != conversation_id:
            cached_agent.conversation_id = conversation_id
        return cached_agent
    
    # Get agent from database
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == user_id
    ).first()
    
    if not agent:
        raise ValueError(f"Agent {agent_id} not found for user {user_id}")
    
    # Expunge agent from session to avoid detached instance errors
    # We'll pass the agent object but access its attributes immediately
    db.expunge(agent)
    
    # Create LLM if not provided
    if llm is None:
        llm = create_minimee_llm(db=db, user_id=user_id)
    
    # Create agent instance (agent is now detached, but we access its attributes in __init__)
    minimee_agent = MinimeeAgent(
        agent=agent,
        db=db,
        user_id=user_id,
        llm=llm,
        conversation_id=conversation_id,
        included_sources=included_sources
    )
    
    # Cache it
    _agent_cache[agent_id] = minimee_agent
    
    return minimee_agent


def get_minimee_leader_agent(
    user_id: int,
    db: Session,
    llm: Optional[BaseLanguageModel] = None,
    conversation_id: Optional[str] = None,
    force_recreate: bool = False,
    included_sources: Optional[List[str]] = None
) -> Optional[MinimeeAgent]:
    """
    Get the Minimee leader agent for a user
    
    Args:
        user_id: User ID
        db: Database session
        llm: Optional LangChain LLM
        conversation_id: Optional conversation ID
        force_recreate: Force recreation even if cached
        included_sources: List of sources to include in RAG context (whatsapp, gmail). If None or empty, all sources included.
    
    Returns:
        MinimeeAgent instance or None if no leader found
    """
    from services.agent_manager import get_minimee_leader
    
    leader = get_minimee_leader(db, user_id)
    if not leader:
        return None
    
    return get_or_create_agent(
        agent_id=leader.id,
        db=db,
        user_id=user_id,
        llm=llm,
        conversation_id=conversation_id,
        force_recreate=force_recreate,
        included_sources=included_sources
    )


def get_agent_by_whatsapp_name(
    whatsapp_name: str,
    user_id: int,
    db: Session,
    llm: Optional[BaseLanguageModel] = None,
    conversation_id: Optional[str] = None,
    included_sources: Optional[List[str]] = None
) -> Optional[MinimeeAgent]:
    """
    Get agent by WhatsApp display name (for routing)
    
    Args:
        whatsapp_name: WhatsApp display name (from prefix [Name])
        user_id: User ID
        db: Database session
        llm: Optional LangChain LLM
        conversation_id: Optional conversation ID
        included_sources: List of sources to include in RAG context (whatsapp, gmail). If None or empty, all sources included.
    
    Returns:
        MinimeeAgent instance or None if not found
    """
    # Search for agent by whatsapp_display_name or name
    agent = db.query(Agent).filter(
        Agent.user_id == user_id,
        Agent.enabled == True
    ).filter(
        (Agent.whatsapp_display_name == whatsapp_name) |
        (Agent.name == whatsapp_name)
    ).first()
    
    if not agent:
        # Fallback to leader if name not found
        return get_minimee_leader_agent(user_id, db, llm, conversation_id, included_sources=included_sources)
    
    return get_or_create_agent(
        agent_id=agent.id,
        db=db,
        user_id=user_id,
        llm=llm,
        conversation_id=conversation_id,
        included_sources=included_sources
    )


def clear_agent_cache(agent_id: Optional[int] = None) -> None:
    """
    Clear agent cache
    
    Args:
        agent_id: Specific agent ID to clear, or None to clear all
    """
    global _agent_cache
    
    if agent_id is None:
        _agent_cache.clear()
    elif agent_id in _agent_cache:
        del _agent_cache[agent_id]


