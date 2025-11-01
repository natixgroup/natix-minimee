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

