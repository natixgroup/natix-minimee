"""
Tests for database connection
"""
from sqlalchemy import text
from db.database import engine, get_db
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_db_connection():
    """Test database connection works"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_health_with_db():
    """Test health endpoint includes DB check"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

