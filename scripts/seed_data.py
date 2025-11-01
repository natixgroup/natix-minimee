"""
Seed script to populate database with default Minimee agent and prompts
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))

from sqlalchemy.orm import Session
from db.database import SessionLocal, engine
from models import User, Agent, Prompt, Policy, Setting
from datetime import datetime


def seed_default_user(db: Session) -> User:
    """Create default user if not exists"""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(
            id=1,
            email="user@minimee.ai",
            name="Minimee User",
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✓ Created default user: {user.email}")
    else:
        print(f"✓ Default user exists: {user.email}")
    return user


def seed_minimee_agent(db: Session, user_id: int) -> Agent:
    """Create default Minimee agent"""
    agent = db.query(Agent).filter(Agent.name == "Minimee", Agent.user_id == user_id).first()
    if not agent:
        agent = Agent(
            name="Minimee",
            role="Personal Assistant",
            prompt="""You are Minimee, a personal AI assistant. Your role is to:
- Help users manage their communications (WhatsApp, Gmail)
- Respond to messages in a style that matches the user's communication patterns
- Learn from past conversations to provide contextually relevant responses
- Always be helpful, professional, and empathetic
- Ask for clarification when needed
- Respect user privacy and data""",
            style="Professional, friendly, and context-aware",
            enabled=True,
            user_id=user_id
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        print(f"✓ Created default agent: {agent.name}")
    else:
        print(f"✓ Default agent exists: {agent.name}")
    return agent


def seed_default_prompts(db: Session, agent_id: int):
    """Create default prompts for Minimee agent"""
    default_prompts = [
        {
            "name": "Greeting Response",
            "content": "Generate a friendly greeting response that matches the sender's tone.",
        },
        {
            "name": "Information Request",
            "content": "Provide helpful information while being concise and accurate.",
        },
        {
            "name": "Meeting Coordination",
            "content": "Help coordinate meetings and schedules. Be clear about dates and times.",
        },
    ]
    
    created_count = 0
    for prompt_data in default_prompts:
        existing = db.query(Prompt).filter(
            Prompt.name == prompt_data["name"],
            Prompt.agent_id == agent_id
        ).first()
        
        if not existing:
            prompt = Prompt(
                name=prompt_data["name"],
                content=prompt_data["content"],
                agent_id=agent_id
            )
            db.add(prompt)
            created_count += 1
    
    db.commit()
    print(f"✓ Created {created_count} default prompts")


def seed_default_policy(db: Session, user_id: int):
    """Create default policy"""
    policy = db.query(Policy).filter(Policy.name == "Default Policy", Policy.user_id == user_id).first()
    if not policy:
        policy = Policy(
            name="Default Policy",
            rules={
                "auto_respond": False,
                "require_approval": True,
                "max_response_length": 500,
                "language": "en",
                "topics_to_avoid": ["sensitive", "confidential"],
                "response_time_limit": 300,  # seconds
            },
            user_id=user_id
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        print(f"✓ Created default policy: {policy.name}")
    else:
        print(f"✓ Default policy exists: {policy.name}")


def seed_default_settings(db: Session, user_id: int):
    """Create default settings"""
    default_settings = [
        {
            "key": "llm_provider",
            "value": {"provider": "ollama"}
        },
        {
            "key": "embedding_model",
            "value": {"model": "sentence-transformers/all-MiniLM-L6-v2"}
        },
        {
            "key": "auto_indexing",
            "value": {"enabled": True}
        },
    ]
    
    created_count = 0
    for setting_data in default_settings:
        existing = db.query(Setting).filter(
            Setting.key == setting_data["key"],
            Setting.user_id == user_id
        ).first()
        
        if not existing:
            setting = Setting(
                key=setting_data["key"],
                value=setting_data["value"],
                user_id=user_id
            )
            db.add(setting)
            created_count += 1
    
    db.commit()
    print(f"✓ Created {created_count} default settings")


def main():
    """Run seed script"""
    print("🌱 Seeding Minimee database with default data...\n")
    
    db = SessionLocal()
    try:
        # Seed in order
        user = seed_default_user(db)
        agent = seed_minimee_agent(db, user.id)
        seed_default_prompts(db, agent.id)
        seed_default_policy(db, user.id)
        seed_default_settings(db, user.id)
        
        print("\n✅ Seed completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

