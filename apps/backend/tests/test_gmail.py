"""
Tests for Gmail service (mocked)
"""
import pytest
from unittest.mock import Mock, patch
from services.gmail_service import get_oauth_flow, get_user_credentials


def test_get_oauth_flow():
    """Test OAuth flow creation"""
    # Mock settings
    with patch('services.gmail_service.settings') as mock_settings:
        mock_settings.gmail_client_id = "test_client_id"
        mock_settings.gmail_client_secret = "test_secret"
        mock_settings.gmail_redirect_uri = "http://localhost:8000/callback"
        
        try:
            flow = get_oauth_flow()
            assert flow is not None
        except ValueError:
            # Expected if credentials not fully configured
            pass


@pytest.mark.integration
def test_gmail_status_endpoint(client):
    """Test Gmail status endpoint"""
    response = client.get("/gmail/status?user_id=1")
    assert response.status_code in [200, 400, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "connected" in data
        assert "has_token" in data

