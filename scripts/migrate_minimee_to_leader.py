"""
Migration script to mark existing Minimee agent as leader
This script is optional as the Alembic migration 006 already handles this,
but can be run manually if needed.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))

from sqlalchemy.orm import Session
from db.database import SessionLocal
from models import Agent, WhatsAppIntegration


def migrate_minimee_to_leader(db: Session, user_id: int = 1) -> bool:
    """
    Mark existing Minimee agent as leader and link to WhatsApp integration
    
    Args:
        db: Database session
        user_id: User ID to migrate (default: 1)
    
    Returns:
        True if migration successful, False otherwise
    """
    try:
        # Check if there's already a leader
        existing_leader = db.query(Agent).filter(
            Agent.user_id == user_id,
            Agent.is_minimee_leader == True
        ).first()
        
        if existing_leader:
            print(f"✓ Agent '{existing_leader.name}' is already the leader for user {user_id}")
            return True
        
        # Find Minimee agent
        minimee_agent = db.query(Agent).filter(
            Agent.name == "Minimee",
            Agent.user_id == user_id
        ).first()
        
        if not minimee_agent:
            print(f"⚠ No 'Minimee' agent found for user {user_id}")
            return False
        
        # Find minimee WhatsApp integration
        minimee_integration = db.query(WhatsAppIntegration).filter(
            WhatsAppIntegration.user_id == user_id,
            WhatsAppIntegration.integration_type == 'minimee'
        ).first()
        
        # Update agent
        minimee_agent.is_minimee_leader = True
        minimee_agent.whatsapp_display_name = 'Minimee'
        
        if minimee_integration:
            minimee_agent.whatsapp_integration_id = minimee_integration.id
            print(f"✓ Linked Minimee agent to WhatsApp integration")
        
        # Set default approval rules if not set
        if not minimee_agent.approval_rules:
            minimee_agent.approval_rules = {
                "auto_approve_confidence_threshold": 0.7,
                "auto_approve_simple_messages": True,
                "require_approval_keywords": ["urgent", "important", "confidential"],
                "max_auto_approve_length": 200
            }
            print(f"✓ Set default approval rules")
        
        db.commit()
        print(f"✓ Successfully marked '{minimee_agent.name}' as leader for user {user_id}")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {str(e)}")
        return False


def main():
    """Run migration for all users"""
    print("🔄 Migrating Minimee agents to leaders...\n")
    
    db = SessionLocal()
    try:
        # Get all users with Minimee agents
        users_with_minimee = db.query(Agent.user_id).filter(
            Agent.name == "Minimee"
        ).distinct().all()
        
        if not users_with_minimee:
            print("⚠ No Minimee agents found")
            return
        
        success_count = 0
        for (user_id,) in users_with_minimee:
            print(f"\n📋 Processing user {user_id}...")
            if migrate_minimee_to_leader(db, user_id):
                success_count += 1
        
        print(f"\n✅ Migration completed: {success_count}/{len(users_with_minimee)} users migrated")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()



