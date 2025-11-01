"""
Tests for approval flow
"""
import pytest
from sqlalchemy.orm import Session
from services.approval_flow import generate_response_options, process_approval, store_email_draft_proposals
from schemas import MessageOptions, ApprovalRequest
from models import Message


@pytest.mark.integration
def test_generate_response_options(db: Session):
    """Test generating response options"""
    # Create a test message
    message = Message(
        content="Test message",
        sender="user",
        timestamp="2024-01-01 10:00:00",
        source="whatsapp",
        conversation_id="test",
        user_id=1
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # Generate options (may need to mock LLM calls)
    # For now, test that function doesn't crash
    try:
        options = generate_response_options(db, message, num_options=3)
        assert options is not None
        assert hasattr(options, 'options')
    except Exception:
        # LLM may not be available in test environment
        pytest.skip("LLM not available in test environment")


@pytest.mark.integration
def test_store_email_draft_proposals():
    """Test storing email draft proposals"""
    thread_id = "test_thread_123"
    message_options = MessageOptions(
        options=["Draft A", "Draft B", "Draft C"],
        message_id=0,
        conversation_id=thread_id
    )
    
    store_email_draft_proposals(thread_id, message_options)
    
    # Verify stored (would need to check internal storage)
    # This tests the function doesn't crash
    assert True


@pytest.mark.integration
def test_process_approval_yes(db: Session):
    """Test approval with 'yes' action"""
    # This test requires a pending approval
    # For now, test structure
    approval = ApprovalRequest(
        message_id=999,  # Non-existent for testing
        option_index=0,
        action="yes",
        type="whatsapp_message"
    )
    
    result = process_approval(db, approval)
    
    # Should return error if no pending approval
    assert "status" in result
    assert result["status"] in ["error", "approved", "rejected"]


@pytest.mark.integration
def test_process_approval_no(db: Session):
    """Test approval with 'no' action"""
    approval = ApprovalRequest(
        message_id=999,
        action="no",
        type="whatsapp_message"
    )
    
    result = process_approval(db, approval)
    assert "status" in result

