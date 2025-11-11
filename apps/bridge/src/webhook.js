/**
 * Backend webhook client
 * Handles communication with Minimee backend API
 */
import axios from 'axios';
import dotenv from 'dotenv';
import { logger, logWebhook } from './logger.js';

dotenv.config();

// Support both BACKEND_API_URL and BRIDGE_API_URL for backward compatibility
const BACKEND_API_URL = process.env.BACKEND_API_URL || process.env.BRIDGE_API_URL || 'http://localhost:8000';
const USER_ID = parseInt(process.env.USER_ID || '1', 10);

/**
 * Send message to backend /minimee/message endpoint
 */
export async function sendMessageToBackend(messageData) {
  const endpoint = `${BACKEND_API_URL}/minimee/message`;
  
  try {
    logWebhook('send', '/minimee/message', {
      sender: messageData.sender,
      conversationId: messageData.conversation_id,
    });

    const response = await axios.post(
      endpoint,
      {
        content: messageData.content,
        sender: messageData.sender,
        timestamp: messageData.timestamp,
        source: 'whatsapp',
        conversation_id: messageData.conversation_id,
        user_id: USER_ID,
      },
      {
        timeout: 30000, // 30 seconds
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    logWebhook('receive', '/minimee/message', {
      status: 'success',
      messageId: response.data.message_id,
      optionsCount: response.data.options?.length || 0,
    });

    return response.data;
  } catch (error) {
    logWebhook('send', '/minimee/message', {
      status: 'error',
      error: error.message,
    });

    if (error.response) {
      logger.error({
        status: error.response.status,
        data: error.response.data,
      }, 'Backend API error');
      throw new Error(`Backend API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
    } else if (error.request) {
      logger.error('No response from backend API');
      throw new Error('Backend API not reachable');
    } else {
      logger.error({ error: error.message }, 'Error sending to backend');
      throw error;
    }
  }
}

/**
 * Send approved message (when user approves a response)
 */
export async function sendApprovedMessage(messageId, optionIndex) {
  const endpoint = `${BACKEND_API_URL}/minimee/approve`;

  try {
    logWebhook('send', '/minimee/approve', { messageId, optionIndex });

    const response = await axios.post(
      endpoint,
      {
        message_id: messageId,
        option_index: optionIndex,
        action: 'yes',
      },
      {
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    logWebhook('receive', '/minimee/approve', {
      status: 'success',
      sent: response.data.sent,
    });

    return response.data;
  } catch (error) {
    logWebhook('send', '/minimee/approve', {
      status: 'error',
      error: error.message,
    });
    throw error;
  }
}

/**
 * Get pending approval by group_message_id
 * This queries the backend to find the pending_approval
 */
export async function getPendingApprovalByGroupMessageId(groupMessageId) {
  try {
    const endpoint = `${BACKEND_API_URL}/minimee/pending-approval/by-group-message-id/${groupMessageId}`;
    
    const response = await axios.get(endpoint, {
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 404) {
      // Not found - that's okay
      return null;
    }
    logger.error({ error: error.message, groupMessageId }, 'Error getting pending approval');
    return null;
  }
}

/**
 * Send approval response to backend
 * Supports both WhatsApp messages (with message_id) and email drafts (with email_thread_id)
 */
export async function sendApprovalResponse(messageId, optionIndex, action = 'yes', emailThreadId = null, approvalType = 'whatsapp_message') {
  const endpoint = `${BACKEND_API_URL}/minimee/approve`;

  try {
    const payload = {
      option_index: optionIndex,
      action: action,
      type: approvalType,
    };
    
    // For email drafts, use email_thread_id instead of message_id
    if (approvalType === 'email_draft' && emailThreadId) {
      payload.email_thread_id = emailThreadId;
      payload.message_id = 0; // Placeholder, will be ignored by backend
    } else {
      payload.message_id = messageId;
    }
    
    logWebhook('send', '/minimee/approve', { messageId, emailThreadId, optionIndex, action, type: approvalType });

    const response = await axios.post(
      endpoint,
      payload,
      {
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    logWebhook('receive', '/minimee/approve', {
      status: 'success',
      sent: response.data.sent,
    });

    return response.data;
  } catch (error) {
    logWebhook('send', '/minimee/approve', {
      status: 'error',
      error: error.message,
    });
    throw error;
  }
}

/**
 * Send message to backend for display only (no processing/response)
 * Used for user's own messages in Minimee TEAM group
 */
export async function sendMessageToBackendForDisplay(messageData) {
  const endpoint = `${BACKEND_API_URL}/minimee/message/display-only`;
  
  try {
    logWebhook('send', '/minimee/message/display-only', {
      sender: messageData.sender,
      conversationId: messageData.conversation_id,
      fromMe: messageData.fromMe,
    });

    const response = await axios.post(
      endpoint,
      {
        content: messageData.content,
        sender: messageData.sender,
        timestamp: messageData.timestamp,
        source: messageData.source || 'whatsapp',
        conversation_id: messageData.conversation_id,
        user_id: messageData.user_id,
        fromMe: messageData.fromMe,
      },
      {
        timeout: 10000, // 10 seconds (faster, just for display)
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    logWebhook('receive', '/minimee/message/display-only', {
      status: 'success',
    });

    return response.data;
  } catch (error) {
    // Don't throw error for display-only messages - just log
    logWebhook('send', '/minimee/message/display-only', {
      status: 'error',
      error: error.message,
    });
    // Return null instead of throwing to avoid breaking the flow
    return null;
  }
}

/**
 * Parse agent prefix from message (format: [Agent Name] message)
 * Returns { agentName: string | null, message: string }
 */
export function parseAgentPrefix(message) {
  const prefixMatch = message.match(/^\[([^\]]+)\]\s*(.*)$/);
  if (prefixMatch) {
    return {
      agentName: prefixMatch[1].trim(),
      message: prefixMatch[2].trim(),
    };
  }
  return {
    agentName: null,
    message: message,
  };
}

/**
 * Send direct chat message to backend (for Minimee TEAM group conversations)
 * This is a direct chat with Minimee, not a message that needs approval
 * Now supports agent routing via [Agent Name] prefix
 */
export async function sendDirectChatToBackend(chatData) {
  const endpoint = `${BACKEND_API_URL}/minimee/chat/direct`;
  
  try {
    // Parse agent prefix if present
    const { agentName, message } = parseAgentPrefix(chatData.content);
    
    logWebhook('send', '/minimee/chat/direct', {
      sender: chatData.sender,
      conversationId: chatData.conversation_id,
      agentName: agentName || 'leader',
    });

    const response = await axios.post(
      endpoint,
      {
        content: message || chatData.content, // Use parsed message (without prefix)
        sender: chatData.sender,
        timestamp: chatData.timestamp,
        source: chatData.source || 'whatsapp',
        conversation_id: chatData.conversation_id,
        user_id: chatData.user_id,
        agent_name: agentName, // Pass agent name for routing
      },
      {
        timeout: 30000, // 30 seconds
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    logWebhook('receive', '/minimee/chat/direct', {
      status: 'success',
      hasResponse: !!response.data.response,
      requiresApproval: response.data.requires_approval || false,
    });

    return response.data;
  } catch (error) {
    logWebhook('send', '/minimee/chat/direct', {
      status: 'error',
      error: error.message,
    });

    if (error.response) {
      logger.error({
        status: error.response.status,
        data: error.response.data,
      }, 'Backend chat API error');
      throw new Error(`Backend chat API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
    } else if (error.request) {
      logger.error('No response from backend chat API');
      throw new Error('Backend chat API not reachable');
    } else {
      logger.error({ error: error.message }, 'Error sending chat to backend');
      throw error;
    }
  }
}

/**
 * Health check backend
 */
export async function checkBackendHealth() {
  try {
    const response = await axios.get(`${BACKEND_API_URL}/health`, {
      timeout: 5000,
    });
    return response.data.status === 'ok';
  } catch (error) {
    logger.warn('Backend health check failed');
    return false;
  }
}

