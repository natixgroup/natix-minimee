"""
Script to create a default user with password for testing
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from db.database import SessionLocal
from models import User
from passlib.context import CryptContext
from datetime import datetime
import bcrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_default_user():
    """Create default user with password"""
    db = SessionLocal()
    try:
        # Check if user exists by email
        user = db.query(User).filter(User.email == "admin@minimee.ai").first()
        
        # Hash password using bcrypt directly
        password = "admin123"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        if user:
            # Update password if user exists
            user.password_hash = password_hash
            user.name = "Admin User"
            user.updated_at = datetime.utcnow()
            print(f"✓ Updated default user password: admin@minimee.ai / admin123")
        else:
            # Check if user with ID 1 exists (from seed script)
            existing_user_id_1 = db.query(User).filter(User.id == 1).first()
            if existing_user_id_1:
                # Update existing user ID 1
                existing_user_id_1.email = "admin@minimee.ai"
                existing_user_id_1.name = "Admin User"
                existing_user_id_1.password_hash = password_hash
                existing_user_id_1.updated_at = datetime.utcnow()
                print(f"✓ Updated existing user (ID 1) with password: admin@minimee.ai / admin123")
            else:
                # Create new user
                user = User(
                    email="admin@minimee.ai",
                    name="Admin User",
                    password_hash=password_hash,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(user)
                print(f"✓ Created default user: admin@minimee.ai / admin123")
        
        db.commit()
        print("\n✅ Default user credentials:")
        print("   Email: admin@minimee.ai")
        print("   Password: admin123")
        print("\n⚠️  WARNING: Change this password in production!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Failed to create default user: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_default_user()

