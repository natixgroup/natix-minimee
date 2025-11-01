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

