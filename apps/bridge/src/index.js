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
import { logger, logMessage, logConnection } from './logger.js';
import { sendMessageToBackend, checkBackendHealth } from './webhook.js';
import { initializeMinimeeTeam } from './groups.js';

dotenv.config();

// Support both BACKEND_API_URL and BRIDGE_API_URL for backward compatibility
const BACKEND_API_URL = process.env.BACKEND_API_URL || process.env.BRIDGE_API_URL || 'http://localhost:8000';
const USER_ID = parseInt(process.env.USER_ID || '1', 10);

let sock = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

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
      printQRInTerminal: true,
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
        logger.info('QR Code generated - scan with WhatsApp');
        console.log('\n📱 Scan the QR code above with your WhatsApp\n');
      }

      if (connection === 'close') {
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
          // Skip status broadcasts and group messages for now (can be configured later)
          if (msg.key.remoteJid === 'status@broadcast') {
            continue;
          }

          // Skip if message is from a group (unless it mentions the bot)
          const isGroup = msg.key.remoteJid.includes('@g.us');
          if (isGroup) {
            // For now, skip group messages (can be enhanced later)
            continue;
          }

          // Skip own messages
          const messageText = extractMessageText(msg.message || {});
          if (!messageText) {
            continue;
          }

          const sender = msg.key.remoteJid;
          const messageId = msg.key.id;
          const timestamp = msg.messageTimestamp 
            ? new Date(msg.messageTimestamp * 1000) 
            : new Date();

          logMessage('incoming', messageText, {
            from: sender,
            messageId,
            timestamp: timestamp.toISOString(),
          });

          // Forward to backend
          try {
            const conversationId = sender.split('@')[0];
            
            const response = await sendMessageToBackend({
              content: messageText,
              sender: sender,
              timestamp: timestamp.toISOString(),
              conversation_id: conversationId,
            });

            logger.info({
              messageId: response.message_id,
              optionsCount: response.options?.length || 0,
            }, 'Message processed by backend');

            // TODO: In future, handle response options and approval flow
            // For now, just log the options
            
          } catch (error) {
            logger.error({ 
              error: error.message,
              from: sender,
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

// Start the bridge
startBridge();
