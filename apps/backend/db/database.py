"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://minimee:minimee@localhost:5432/minimee"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
    pool_timeout=30,  # Timeout for getting connection from pool
    connect_args={
        "connect_timeout": 10,  # PostgreSQL connection timeout
        "options": "-c statement_timeout=30000"  # 30s statement timeout
    },
    echo=False  # Set to True for SQL logging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

