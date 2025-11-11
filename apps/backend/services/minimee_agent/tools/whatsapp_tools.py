"""
LangChain tools for WhatsApp operations
"""
from typing import Optional
from langchain.tools import tool
from sqlalchemy.orm import Session
from services.bridge_client import send_message_via_bridge
from services.whatsapp_integration_service import get_minimee_integration
from services.logs_service import log_to_db
from models import Agent


@tool
def send_whatsapp_message(recipient: str, message: str, agent_name: str) -> str:
    """
    Send a WhatsApp message via the bridge with agent name prefix.
    Format: [Agent Name] message
    
    Args:
        recipient: Recipient JID or phone number
        message: Message content (will be prefixed with [Agent Name])
        agent_name: Name of the agent sending the message (for prefix)
    
    Returns:
        Status message indicating success or failure
    """
    return f"Sending WhatsApp message to {recipient} as {agent_name}"


def create_send_whatsapp_message_tool(db: Session, agent: Agent):
    """
    Create send_whatsapp_message tool with database and agent context
    
    Args:
        db: Database session
        agent: Agent model with whatsapp_display_name
    
    Returns:
        Tool instance
    """
    import asyncio
    
    def send_whatsapp_sync(recipient: str, message: str) -> str:
        """
        Send a WhatsApp message via the bridge with agent name prefix.
        Format: [Agent Name] message
        
        Args:
            recipient: Recipient JID or phone number
            message: Message content (will be prefixed with [Agent Name])
        
        Returns:
            Status message indicating success or failure
        """
        try:
            # Get agent display name for prefix
            display_name = agent.whatsapp_display_name or agent.name
            
            # Format message with prefix: [Agent Name] message
            formatted_message = f"[{display_name}] {message}"
            
            # Send via bridge (sync wrapper for async function)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we need to use a different approach
                    # For now, create a new event loop in a thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            send_message_via_bridge(
                                recipient=recipient,
                                message_text=formatted_message,
                                source="whatsapp",
                                db=db,
                                integration_type='user'
                            )
                        )
                        result = future.result()
                else:
                    result = loop.run_until_complete(
                        send_message_via_bridge(
                            recipient=recipient,
                            message_text=formatted_message,
                            source="whatsapp",
                            db=db,
                            integration_type='user'
                        )
                    )
            except RuntimeError:
                # No event loop, create one
                result = asyncio.run(
                    send_message_via_bridge(
                        recipient=recipient,
                        message_text=formatted_message,
                        source="whatsapp",
                        db=db,
                        integration_type='user'
                    )
                )
            
            if result.get("sent"):
                return f"Message sent successfully to {recipient}"
            else:
                return f"Failed to send message: {result.get('message', 'Unknown error')}"
        except Exception as e:
            log_to_db(db, "ERROR", f"Send WhatsApp message failed: {str(e)}", service="minimee_agent")
            return f"Error sending message: {str(e)}"
    
    # Create tool - need to handle both dict and JSON string inputs
    # LangChain ReAct agent may send JSON string or dict
    def send_whatsapp_wrapper(input_data) -> str:
        """Wrapper that handles both dict and JSON string inputs"""
        import json
        
        # If input is a string, try to parse as JSON
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except json.JSONDecodeError:
                # If not JSON, treat as message and use default recipient
                return send_whatsapp_sync(recipient="unknown", message=input_data)
        
        # Extract recipient and message from dict
        recipient = input_data.get("recipient", "unknown")
        message = input_data.get("message", "")
        
        if not message:
            return "Error: 'message' field is required"
        
        return send_whatsapp_sync(recipient=recipient, message=message)
    
    # Use StructuredTool with proper schema
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    class SendWhatsAppInput(BaseModel):
        recipient: str = Field(description="Recipient JID or phone number")
        message: str = Field(description="Message content to send")
    
    # But we need to handle the fact that LangChain may pass a dict directly
    # So we create a tool that accepts the dict and extracts fields
    send_whatsapp_message_tool = StructuredTool.from_function(
        func=send_whatsapp_sync,
        name="send_whatsapp_message",
        description=(
            f"Send a WhatsApp message via the bridge with agent name prefix [{agent.whatsapp_display_name or agent.name}]. "
            "Format: [Agent Name] message. "
            "Use this when you need to send a message to a WhatsApp contact."
        ),
        args_schema=SendWhatsAppInput
    )
    
    return send_whatsapp_message_tool


@tool
def route_whatsapp_message(message: str, sender: str) -> str:
    """
    Route an incoming WhatsApp message to the appropriate agent based on prefix.
    Parses [Agent Name] prefix to determine which agent should handle the message.
    
    Args:
        message: Incoming message text (may contain [Agent Name] prefix)
        sender: Sender JID or phone number
    
    Returns:
        Agent name that should handle this message, or 'leader' if no prefix
    """
    # Parse prefix [Agent Name]
    if message.startswith("[") and "]" in message:
        prefix_end = message.find("]")
        if prefix_end > 0:
            agent_name = message[1:prefix_end].strip()
            return agent_name
    
    return "leader"  # Default to leader agent


def create_route_whatsapp_message_tool():
    """
    Create route_whatsapp_message tool
    
    Returns:
        Tool instance
    """
    route_tool = tool(route_whatsapp_message)
    route_tool.name = "route_whatsapp_message"
    route_tool.description = (
        "Route an incoming WhatsApp message to the appropriate agent based on prefix. "
        "Parses [Agent Name] prefix to determine which agent should handle the message. "
        "Returns agent name or 'leader' if no prefix."
    )
    return route_tool


@tool
def get_whatsapp_status() -> str:
    """
    Get the status of WhatsApp Business connection.
    Returns connection status (connected/disconnected/pending).
    
    Returns:
        Status string with connection information
    """
    return "Checking WhatsApp status..."


def create_get_whatsapp_status_tool(db: Session, user_id: int):
    """
    Create get_whatsapp_status tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def get_whatsapp_status_tool() -> str:
        """Get WhatsApp connection status"""
        try:
            # Check minimee integration status
            integration = get_minimee_integration(db, user_id)
            
            if not integration:
                return "WhatsApp Business not configured"
            
            status = integration.status
            phone_number = integration.phone_number or "Not set"
            display_name = integration.display_name or "Minimee"
            
            return f"WhatsApp Business Status: {status}, Phone: {phone_number}, Display Name: {display_name}"
        except Exception as e:
            log_to_db(db, "ERROR", f"Get WhatsApp status failed: {str(e)}", service="minimee_agent")
            return f"Error checking status: {str(e)}"
    
    get_whatsapp_status_tool.name = "get_whatsapp_status"
    get_whatsapp_status_tool.description = (
        "Get the status of WhatsApp Business connection. "
        "Returns connection status (connected/disconnected/pending)."
    )
    
    return get_whatsapp_status_tool

