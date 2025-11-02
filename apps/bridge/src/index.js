/**
 * Minimee WhatsApp Bridge
 * Real-time interface using Baileys
 * Handles QR login, persistent sessions, message forwarding, and group management
 */

import makeWASocket, { 
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import dotenv from 'dotenv';
import qrcode from 'qrcode-terminal';
import QRCode from 'qrcode';
import express from 'express';
import cors from 'cors';
import { logger, logMessage, logConnection } from './logger.js';
import { sendMessageToBackend, checkBackendHealth, getPendingApprovalByGroupMessageId, sendApprovalResponse, sendDirectChatToBackend, sendMessageToBackendForDisplay } from './webhook.js';
import { initializeMinimeeTeam } from './groups.js';

dotenv.config();

// Support both BACKEND_API_URL and BRIDGE_API_URL for backward compatibility
const BACKEND_API_URL = process.env.BACKEND_API_URL || process.env.BRIDGE_API_URL || 'http://localhost:8000';
const USER_ID = parseInt(process.env.USER_ID || '1', 10);
const BRIDGE_PORT = parseInt(process.env.BRIDGE_PORT || '3003', 10);

let sock = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// State for HTTP API
let connectionStatus = 'disconnected'; // 'disconnected', 'connecting', 'connected'
let currentQR = null;
let qrImageData = null;

/**
 * Extract text from Baileys message
 */
function extractMessageText(message) {
  if (message.conversation) {
    return message.conversation;
  }
  if (message.extendedTextMessage) {
    return message.extendedTextMessage.text || '';
  }
  if (message.imageMessage) {
    return message.imageMessage.caption || '';
  }
  if (message.videoMessage) {
    return message.videoMessage.caption || '';
  }
  return '';
}

/**
 * Format phone number to WhatsApp JID format
 */
function formatJID(jid) {
  if (jid.includes('@')) {
    return jid;
  }
  return `${jid.replace(/[^0-9]/g, '')}@s.whatsapp.net`;
}

/**
 * Send message via WhatsApp
 */
export async function sendWhatsAppMessage(to, text) {
  if (!sock) {
    throw new Error('WhatsApp not connected');
  }

  try {
    const jid = formatJID(to);
    await sock.sendMessage(jid, { text });
    
    logMessage('outgoing', text, {
      to: jid,
    });
    
    logger.info(`Message sent to ${jid}`);
    return true;
  } catch (error) {
    logger.error({ error: error.message, to }, 'Error sending message');
    throw error;
  }
}

/**
 * Start WhatsApp Bridge
 */
async function startBridge() {
  try {
    logger.info('Starting Minimee WhatsApp Bridge...');
    logger.info(`Backend API: ${BACKEND_API_URL}`);
    
    // Check backend health
    const backendHealthy = await checkBackendHealth();
    if (!backendHealthy) {
      logger.warn('Backend API not reachable, continuing anyway...');
    } else {
      logger.info('Backend API is healthy');
    }

    const { state, saveCreds } = await useMultiFileAuthState('auth_info');
    
    const { version } = await fetchLatestBaileysVersion();
    
    sock = makeWASocket({
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      logger,
      version,
      browser: ['Minimee', 'Chrome', '1.0.0'],
      getMessage: async (key) => {
        return {
          conversation: 'Message not available',
        };
      },
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;
      
      if (qr) {
        connectionStatus = 'connecting';
        currentQR = qr;
        // Generate QR code as data URL for frontend
        try {
          qrImageData = await QRCode.toDataURL(qr);
        } catch (error) {
          logger.error({ error: error.message }, 'Failed to generate QR image');
        }
        
        logger.info('QR Code generated - scan with WhatsApp');
        console.log('\n📱 WhatsApp Connection - Scan this QR code with your phone:\n');
        qrcode.generate(qr, { small: true });
        console.log('\n📱 Instructions:');
        console.log('   1. Open WhatsApp on your phone');
        console.log('   2. Go to Settings > Linked Devices');
        console.log('   3. Tap "Link a Device"');
        console.log('   4. Point your camera at the QR code above\n');
      }

      if (connection === 'close') {
        connectionStatus = 'disconnected';
        currentQR = null;
        qrImageData = null;
        
        const error = lastDisconnect?.error;
        const statusCode = error?.output?.statusCode;
        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        
        logConnection('closed', {
          shouldReconnect,
          statusCode: statusCode,
        });

        if (shouldReconnect && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts++;
          logger.info(`Reconnecting... (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
          setTimeout(() => startBridge(), 3000);
        } else {
          logger.error('Max reconnect attempts reached or logged out');
          process.exit(1);
        }
      } else if (connection === 'open') {
        connectionStatus = 'connected';
        currentQR = null;
        qrImageData = null;
        
        reconnectAttempts = 0;
        logConnection('open', {});
        logger.info('✓ WhatsApp connected successfully');
        
        // Initialize Minimee TEAM group
        try {
          await initializeMinimeeTeam(sock);
        } catch (error) {
          logger.error({ error: error.message }, 'Failed to initialize Minimee TEAM group');
        }
      } else if (connection === 'connecting') {
        connectionStatus = 'connecting';
        logConnection('connecting', {});
        logger.info('Connecting to WhatsApp...');
      }
    });

    sock.ev.on('messages.upsert', async (m) => {
      try {
        const { messages, type } = m;
        
        if (type !== 'notify') {
          return;
        }

        for (const msg of messages) {
          // Skip status broadcasts
          if (msg.key.remoteJid === 'status@broadcast') {
            continue;
          }

          const isGroup = msg.key.remoteJid.includes('@g.us');
          const messageText = extractMessageText(msg.message || {});
          
          // Skip if no message text
          if (!messageText) {
            continue;
          }
          
          // Skip messages with [🤖 Minimee] prefix to avoid loops
          if (messageText.startsWith('[🤖 Minimee]')) {
            continue;
          }
          
          // Handle group messages (Minimee TEAM)
          if (isGroup) {
            // Get group name
            try {
              const groupMetadata = await sock.groupMetadata(msg.key.remoteJid);
              const groupName = groupMetadata.subject;
              
              // Only process messages from Minimee TEAM group
              if (groupName === 'Minimee TEAM') {
                // Check if this is a button response
                let approvalChoice = null;
                let messageId = null;
                
                // Try to extract from button response
                if (msg.message?.buttonsResponseMessage) {
                  const buttonId = msg.message.buttonsResponseMessage.selectedButtonId;
                  // Format: approve_{approval_id}_{choice}
                  const match = buttonId.match(/approve_(\d+)_([ABC]|NO)/);
                  if (match) {
                    const approvalId = match[1];
                    const choice = match[2];
                    
                    // Map choice to option_index
                    const choiceMap = { 'A': 0, 'B': 1, 'C': 2, 'NO': 'no' };
                    approvalChoice = choiceMap[choice];
                    
                    // We need to get message_id from approval_id, but for now we'll parse from text
                    // This is a limitation - we'll improve by storing approval_id in group_message metadata
                    logger.info({
                      approvalId,
                      choice,
                      buttonId,
                    }, 'Button response received in group');
                  }
                }
                
                // If not a button response, try parsing text
                if (!approvalChoice && messageText) {
                  const textUpper = messageText.trim().toUpperCase();
                  // Look for simple responses: "A", "B", "C", "No", "NO"
                  if (textUpper === 'A' || textUpper.startsWith('A)') || textUpper === '/A') {
                    approvalChoice = 0;
                  } else if (textUpper === 'B' || textUpper.startsWith('B)') || textUpper === '/B') {
                    approvalChoice = 1;
                  } else if (textUpper === 'C' || textUpper.startsWith('C)') || textUpper === '/C') {
                    approvalChoice = 2;
                  } else if (textUpper === 'NO' || textUpper === 'N' || textUpper.startsWith('NO)')) {
                    approvalChoice = 'no';
                  }
                }
                
                // If we found a valid choice, forward to backend for approval processing
                if (approvalChoice !== null) {
                  try {
                    const groupMessageId = msg.key.id;
                    
                    // Try to get approval_id from button response first
                    let approvalId = null;
                    if (msg.message?.buttonsResponseMessage) {
                      const buttonId = msg.message.buttonsResponseMessage.selectedButtonId;
                      const match = buttonId.match(/approve_(\d+)_([ABC]|NO)/);
                      if (match) {
                        approvalId = parseInt(match[1]);
                      }
                    }
                    
                    // Get pending approval info from backend
                    const pendingApproval = await getPendingApprovalByGroupMessageId(groupMessageId);
                    
                    if (!pendingApproval && !approvalId) {
                      logger.warn({
                        choice: approvalChoice,
                        groupMessageId,
                      }, 'Approval response detected but pending approval not found');
                      continue;
                    }
                    
                    const messageId = pendingApproval?.message_id || null;
                    const conversationId = pendingApproval?.conversation_id || null;
                    // Determine if this is an email draft (message_id is null but conversation_id exists)
                    const approvalType = (conversationId && messageId === null) ? 'email_draft' : 'whatsapp_message';
                    const emailThreadId = approvalType === 'email_draft' ? conversationId : null;
                    
                    // For email drafts, we need conversation_id (thread_id), not message_id
                    // For WhatsApp, we need message_id
                    if (approvalType === 'whatsapp_message' && !messageId) {
                      logger.warn({
                        choice: approvalChoice,
                        groupMessageId,
                        approvalType,
                      }, 'Cannot find message_id for WhatsApp approval response');
                      continue;
                    }
                    
                    if (approvalType === 'email_draft' && !emailThreadId) {
                      logger.warn({
                        choice: approvalChoice,
                        groupMessageId,
                        approvalType,
                      }, 'Cannot find email_thread_id for email draft approval response');
                      continue;
                    }
                    
                    logger.info({
                      messageId,
                      emailThreadId,
                      conversationId,
                      choice: approvalChoice,
                      sender: msg.key.participant || msg.key.remoteJid,
                      groupMessageId,
                      approvalType,
                    }, 'Processing approval response');
                    
                    // Determine action and option_index
                    let action = 'yes';
                    let optionIndex = null;
                    
                    if (approvalChoice === 'no') {
                      action = 'no';
                    } else if (typeof approvalChoice === 'number') {
                      optionIndex = approvalChoice;
                    }
                    
                    // Call backend to process approval
                    const result = await sendApprovalResponse(messageId, optionIndex, action, emailThreadId, approvalType);
                    
                    logger.info({
                      messageId,
                      emailThreadId,
                      choice: approvalChoice,
                      result: result.status,
                      approvalType,
                    }, 'Approval response sent to backend');
                    
                    continue; // Approval processed, don't treat as regular message
                  } catch (error) {
                    logger.error({ 
                      error: error.message,
                      choice: approvalChoice,
                      stack: error.stack,
                    }, 'Error processing approval response from group');
                  }
                }
                
                // For other messages in Minimee TEAM group (including user's own messages)
                // Send to backend for display in dashboard and as direct chat with Minimee
                logger.info({
                  messageText: messageText.substring(0, 50),
                  groupName,
                  fromMe: msg.key.fromMe,
                }, 'Message from Minimee TEAM group (direct chat, not approval response)');
                
                // Use same conversation_id as dashboard to display messages together
                // Dashboard uses "dashboard-user-{userId}", so use that instead of "minimee-team-{userId}"
                const conversationId = `dashboard-user-${USER_ID}`;
                // For user's own messages (fromMe), always use "User" as sender to match dashboard expectations
                // For messages from others, use their name
                const senderName = msg.key.fromMe 
                  ? 'User' 
                  : (msg.pushName || msg.key.participant?.split('@')[0] || 'User');
                const messageTimestamp = new Date(msg.messageTimestamp ? msg.messageTimestamp * 1000 : Date.now()).toISOString();
                
                // Only process as direct chat if NOT from the user themselves (fromMe)
                // This avoids Minimee responding to its own messages
                if (!msg.key.fromMe) {
                  try {
                    // Send to backend chat endpoint (not message endpoint to avoid generating approval options)
                    // This will create the message in DB, generate embedding, and broadcast via WebSocket
                    const chatResponse = await sendDirectChatToBackend({
                      content: messageText,
                      sender: senderName,
                      timestamp: messageTimestamp,
                      source: 'whatsapp',
                      conversation_id: conversationId,
                      user_id: USER_ID,
                    });
                    
                    // If backend returned a response, send it back to the group
                    if (chatResponse && chatResponse.response) {
                      const groupJid = msg.key.remoteJid;
                      // Add prefix to identify Minimee messages and avoid loops
                      const responseWithPrefix = `[🤖 Minimee] ${chatResponse.response}`;
                      await sock.sendMessage(groupJid, { 
                        text: responseWithPrefix,
                      });
                      
                      logger.info({
                        responseLength: chatResponse.response.length,
                        conversationId,
                      }, 'Direct chat response sent to Minimee TEAM group');
                    }
                  } catch (error) {
                    logger.error({ 
                      error: error.message,
                      stack: error.stack,
                    }, 'Error processing direct chat message from Minimee TEAM group');
                  }
                } else {
                  // For user's own messages (fromMe), just store for display without generating response
                  // Use display-only endpoint to avoid duplicate embeddings (chat/direct already creates one)
                  try {
                    await sendMessageToBackendForDisplay({
                      content: messageText,
                      sender: senderName,
                      timestamp: messageTimestamp,
                      source: 'whatsapp',
                      conversation_id: conversationId,
                      user_id: USER_ID,
                      fromMe: msg.key.fromMe,
                    });
                  } catch (error) {
                    logger.warn({ 
                      error: error.message,
                    }, 'Error broadcasting user message to dashboard');
                  }
                }
                
                continue; // Don't process as regular incoming message
              }
              
              // Skip other groups
              continue;
            } catch (error) {
              // If we can't get group metadata, skip
              logger.warn({ error: error.message }, 'Error getting group metadata');
              continue;
            }
          }

          const senderJid = msg.key.remoteJid;
          const senderName = msg.pushName || msg.key.participant?.split('@')[0] || senderJid.split('@')[0];
          const messageId = msg.key.id;
          const timestamp = msg.messageTimestamp 
            ? new Date(msg.messageTimestamp * 1000) 
            : new Date();

          logMessage('incoming', messageText, {
            from: senderJid,
            senderName,
            messageId,
            timestamp: timestamp.toISOString(),
          });

          // Forward to backend
          try {
            const conversationId = senderJid.split('@')[0];
            
            const response = await sendMessageToBackend({
              content: messageText,
              sender: senderName, // Use readable name instead of full JID
              timestamp: timestamp.toISOString(),
              conversation_id: conversationId,
            });

            logger.info({
              messageId: response.message_id,
              optionsCount: response.options?.length || 0,
              conversationId,
              sender: senderName,
            }, 'Message processed by backend - approval options should be sent to group');
            
            // Note: The backend will automatically send approval request to Minimee TEAM group
            // via the bridge_client service after generating options
            
          } catch (error) {
            logger.error({ 
              error: error.message,
              errorStack: error.stack,
              from: senderJid,
              senderName,
              conversationId,
            }, 'Error forwarding message to backend');
          }
        }
      } catch (error) {
        logger.error({ error: error.message }, 'Error processing messages');
      }
    });

    // Handle message sending errors
    sock.ev.on('messages.update', async (updates) => {
      for (const update of updates) {
        if (update.update?.status === 'ERROR') {
          logger.error({
            messageId: update.key.id,
            status: update.update.status,
          }, 'Message sending failed');
        }
      }
    });

    return sock;
  } catch (error) {
    logger.error({ error: error.message }, 'Bridge startup error');
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  logger.info('Shutting down WhatsApp Bridge...');
  if (sock) {
    sock.end(undefined);
  }
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down WhatsApp Bridge...');
  if (sock) {
    sock.end(undefined);
  }
  process.exit(0);
});

// HTTP API Server
const app = express();
app.use(cors());
app.use(express.json());

// GET /status - Get connection status
app.get('/status', (req, res) => {
  res.json({
    status: connectionStatus,
    connected: connectionStatus === 'connected',
    has_qr: !!currentQR,
  });
});

// GET /qr - Get QR code
app.get('/qr', async (req, res) => {
  if (currentQR && qrImageData) {
    res.json({
      qr_available: true,
      qr_data: qrImageData,
      qr_text: currentQR,
    });
  } else {
    res.json({
      qr_available: false,
      qr_data: null,
      qr_text: null,
    });
  }
});

// POST /restart - Restart connection (generate new QR)
app.post('/restart', async (req, res) => {
  try {
    if (sock) {
      await sock.logout();
    }
    connectionStatus = 'disconnected';
    currentQR = null;
    qrImageData = null;
    
    setTimeout(() => {
      startBridge();
    }, 1000);
    
    res.json({
      status: 'restarting',
      message: 'Bridge restarting, new QR code will be available shortly',
    });
  } catch (error) {
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// POST /bridge/send-approval-request - Send approval request to Minimee TEAM group
app.post('/bridge/send-approval-request', async (req, res) => {
  try {
    const { message_id, approval_id, message_text, options, sender, source } = req.body;
    
    if (!message_text || !options) {
      return res.status(400).json({
        status: 'error',
        message: 'message_text and options are required',
      });
    }
    
    if (!sock || connectionStatus !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'WhatsApp not connected',
      });
    }
    
    // Import group function
    const { sendApprovalMessageToGroup } = await import('./groups.js');
    
    // Send to group with timeout protection
    // Use Promise.race to ensure we don't wait forever
    const sendPromise = sendApprovalMessageToGroup(sock, {
      message_text,
      options,
      message_id,
      approval_id,
      sender,
      source,
    });
    
    // Add a 45s timeout wrapper (backend timeout is 60s, so we have margin)
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('Sending message to WhatsApp group timed out after 45s')), 45000);
    });
    
    const result = await Promise.race([sendPromise, timeoutPromise]);
    
    logger.info({
      message_id,
      approval_id,
      group_message_id: result.group_message_id,
    }, 'Approval request sent to group');
    
    res.json({
      status: 'success',
      group_message_id: result.group_message_id,
      sent: true,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error sending approval request to group');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// POST /bridge/send-message - Send message to recipient
app.post('/bridge/send-message', async (req, res) => {
  try {
    const { recipient, message, source } = req.body;
    
    if (!recipient || !message) {
      return res.status(400).json({
        status: 'error',
        message: 'recipient and message are required',
      });
    }
    
    if (!sock || connectionStatus !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'WhatsApp not connected',
      });
    }
    
    // For now, only support WhatsApp (Gmail will be handled separately)
    if (source !== 'whatsapp') {
      return res.status(400).json({
        status: 'error',
        message: 'Only WhatsApp source is supported for now',
      });
    }
    
    const jid = formatJID(recipient);
    await sock.sendMessage(jid, { text: message });
    
    logMessage('outgoing', message, {
      to: jid,
      source,
    });
    
    logger.info(`Message sent to ${jid}`);
    
    res.json({
      status: 'success',
      sent: true,
      recipient: jid,
    });
  } catch (error) {
    logger.error({ error: error.message, recipient: req.body.recipient }, 'Error sending message');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// Start HTTP server
app.listen(BRIDGE_PORT, '0.0.0.0', () => {
  logger.info(`WhatsApp Bridge HTTP API listening on port ${BRIDGE_PORT}`);
});

// Start the bridge
startBridge();
