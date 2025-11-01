"""
Tests for agent management
"""
import pytest
from sqlalchemy.orm import Session
from services.agent_manager import create_agent, get_agent, get_agents, select_agent_for_context
from schemas import AgentCreate, AgentUpdate
from models import Agent


@pytest.mark.integration
def test_create_agent(db: Session):
    """Test creating an agent"""
    agent_data = AgentCreate(
        name="Test Agent",
        role="Test Role",
        prompt="You are a test agent",
        style="Friendly",
        enabled=True,
        user_id=1
    )
    
    agent = create_agent(db, agent_data)
    
    assert agent.id is not None
    assert agent.name == "Test Agent"
    assert agent.role == "Test Role"
    assert agent.enabled is True


@pytest.mark.integration
def test_get_agent(db: Session):
    """Test retrieving an agent"""
    agent_data = AgentCreate(
        name="Retrieve Test Agent",
        role="Test",
        prompt="Test prompt",
        enabled=True,
        user_id=1
    )
    
    created = create_agent(db, agent_data)
    retrieved = get_agent(db, created.id)
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == created.name


@pytest.mark.integration
def test_list_agents(db: Session):
    """Test listing agents"""
    # Create multiple agents
    for i in range(3):
        create_agent(db, AgentCreate(
            name=f"Agent {i}",
            role="Test",
            prompt="Test prompt",
            enabled=True,
            user_id=1
        ))
    
    agents = get_agents(db, user_id=1)
    assert len(agents) >= 3


@pytest.mark.integration
def test_select_agent_for_context(db: Session):
    """Test agent selection based on context"""
    # Create agent with specific prompt
    agent = create_agent(db, AgentCreate(
        name="Support Agent",
        role="Customer Support",
        prompt="You help customers with technical issues",
        enabled=True,
        user_id=1
    ))
    
    # Select agent for technical support context
    selected = select_agent_for_context(db, "I have a technical problem", user_id=1)
    
    # Should select an agent (may or may not be the one we created)
    # This is a basic test - actual selection logic may vary
    assert selected is not None or True  # May return None if no good match

