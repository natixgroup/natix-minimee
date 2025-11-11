"""
Pytest configuration and fixtures
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base, get_db
from main import app


# Test database URL (use PostgreSQL for compatibility with JSONB and pgvector)
# Use the same database as development, but with a test schema or separate test DB
import os
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://minimee:minimee@postgres:5432/minimee_test")


@pytest.fixture(scope="function")
def db():
    """Create a test database session"""
    from models import User
    
    # Create test engine (PostgreSQL)
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    # Create a test user if it doesn't exist
    test_user = session.query(User).filter(User.id == 1).first()
    if not test_user:
        test_user = User(
            id=1,
            email="test@example.com",
            name="Test User"
        )
        session.add(test_user)
        session.commit()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        # Clean up: drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    test_client = TestClient(app)
    
    yield test_client
    
    app.dependency_overrides.clear()

