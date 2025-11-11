"""
Agent management service
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from models import Agent, Prompt
from schemas import AgentCreate, AgentUpdate


def get_agent(db: Session, agent_id: int) -> Optional[Agent]:
    """Get agent by ID"""
    return db.query(Agent).filter(Agent.id == agent_id).first()


def get_agents(db: Session, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[Agent]:
    """List agents, optionally filtered by user"""
    query = db.query(Agent)
    if user_id:
        query = query.filter(Agent.user_id == user_id)
    return query.offset(skip).limit(limit).all()


def create_agent(db: Session, agent_data: AgentCreate) -> Agent:
    """Create new agent"""
    agent = Agent(**agent_data.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent(db: Session, agent_id: int, agent_data: AgentUpdate) -> Optional[Agent]:
    """Update existing agent"""
    agent = get_agent(db, agent_id)
    if not agent:
        return None
    
    update_data = agent_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)
    
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: int) -> bool:
    """Delete agent"""
    agent = get_agent(db, agent_id)
    if not agent:
        return False
    
    db.delete(agent)
    db.commit()
    return True


def select_agent_for_context(db: Session, context: str, user_id: int) -> Optional[Agent]:
    """
    Select best agent for given context
    Simple implementation: returns first enabled agent
    Can be enhanced with ML-based selection
    """
    agent = db.query(Agent).filter(
        Agent.user_id == user_id,
        Agent.enabled == True
    ).first()
    return agent


def get_minimee_leader(db: Session, user_id: int) -> Optional[Agent]:
    """
    Get the Minimee leader agent for a user
    Only one agent can be leader per user
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Agent instance if leader exists, None otherwise
    """
    return db.query(Agent).filter(
        Agent.user_id == user_id,
        Agent.is_minimee_leader == True,
        Agent.enabled == True
    ).first()


def set_minimee_leader(db: Session, agent_id: int, user_id: int) -> Agent:
    """
    Set an agent as the Minimee leader
    Unsets any existing leader for the user first
    
    Args:
        db: Database session
        agent_id: Agent ID to set as leader
        user_id: User ID
    
    Returns:
        Updated Agent instance
    
    Raises:
        ValueError: If agent not found or doesn't belong to user
    """
    # Verify agent exists and belongs to user
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == user_id
    ).first()
    
    if not agent:
        raise ValueError(f"Agent {agent_id} not found for user {user_id}")
    
    # Unset any existing leader
    existing_leader = get_minimee_leader(db, user_id)
    if existing_leader and existing_leader.id != agent_id:
        existing_leader.is_minimee_leader = False
    
    # Set new leader
    agent.is_minimee_leader = True
    db.commit()
    db.refresh(agent)
    
    # Clear agent cache if using factory
    try:
        from services.minimee_agent.agent_factory import clear_agent_cache
        clear_agent_cache(agent_id)
    except ImportError:
        pass  # Factory not available
    
    return agent


def get_agent_by_whatsapp_name(db: Session, whatsapp_name: str, user_id: int) -> Optional[Agent]:
    """
    Get agent by WhatsApp display name (for routing)
    
    Args:
        db: Database session
        whatsapp_name: WhatsApp display name (from prefix [Name])
        user_id: User ID
    
    Returns:
        Agent instance if found, None otherwise
    """
    return db.query(Agent).filter(
        Agent.user_id == user_id,
        Agent.enabled == True
    ).filter(
        (Agent.whatsapp_display_name == whatsapp_name) |
        (Agent.name == whatsapp_name)
    ).first()

