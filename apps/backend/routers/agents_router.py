"""
Agent management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.database import get_db
from models import Agent
from schemas import AgentCreate, AgentUpdate, AgentResponse
from services.agent_manager import (
    get_agents, get_agent, create_agent, update_agent, delete_agent
)

router = APIRouter()


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents(
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all agents"""
    return get_agents(db, user_id=user_id, skip=skip, limit=limit)


@router.post("/agents", response_model=AgentResponse)
async def create_agent_endpoint(
    agent_data: AgentCreate,
    db: Session = Depends(get_db)
):
    """Create new agent"""
    return create_agent(db, agent_data)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent_endpoint(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get agent by ID"""
    agent = get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent_endpoint(
    agent_id: int,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db)
):
    """Update agent"""
    agent = update_agent(db, agent_id, agent_data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent_endpoint(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Delete agent"""
    success = delete_agent(db, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted"}

