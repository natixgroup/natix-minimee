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
  getAggregateVotesInPollMessage,
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
let currentUserJid = null; // Store connected user's JID

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
        // Try to get message from cache or return placeholder
        // This is needed for decrypting poll votes
        if (sock && sock.store) {
          try {
            const msg = await sock.loadMessage(key.remoteJid, key.id);
            if (msg) return msg;
          } catch (error) {
            // Message not in cache, that's ok
          }
        }
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
        
        // Store user JID when connected
        // Try to get from socket first, then from saved credentials
        if (sock.user?.id) {
          currentUserJid = sock.user.id;
        } else {
          // Try to get from saved auth state
          try {
            const { state: authState } = await useMultiFileAuthState('auth_info');
            if (authState.creds?.me?.id) {
              currentUserJid = authState.creds.me.id;
            }
          } catch (error) {
            logger.warn({ error: error.message }, 'Could not load user JID from auth state');
          }
        }
        
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

    // Listen for all events to catch poll votes
    sock.ev.on('messages.upsert', async (m) => {
      try {
        const { messages, type } = m;
        
        // Log all upsert events for debugging
        logger.info({
          type,
          messagesCount: messages.length,
          firstMessage: messages[0] ? {
            hasPollUpdate: !!messages[0].message?.pollUpdateMessage,
            hasPollCreation: !!messages[0].message?.pollCreationMessage,
            remoteJid: messages[0].key?.remoteJid,
          } : null,
        }, '=== messages.upsert event received ===');
        
        if (type !== 'notify') {
          return;
        }

        for (const msg of messages) {
          // Check for poll vote updates in upsert
          if (msg.message?.pollUpdateMessage) {
            logger.info({
              pollUpdate: JSON.stringify(msg.message.pollUpdateMessage),
              key: JSON.stringify(msg.key),
            }, 'Poll vote detected in messages.upsert!');
            
            const pollUpdate = msg.message.pollUpdateMessage;
            const pollMessageKey = pollUpdate.pollCreationMessageKey;
            
            if (pollMessageKey?.id) {
              const isGroup = pollMessageKey.remoteJid?.includes('@g.us');
              if (isGroup) {
                try {
                  const groupMetadata = await sock.groupMetadata(pollMessageKey.remoteJid);
                  if (groupMetadata.subject === 'Minimee TEAM') {
                    // Get selected options
                    const selectedOptions = pollUpdate.vote?.selectedOptionIds || pollUpdate.vote?.selectedOptions || pollUpdate.pollUpdates?.[0]?.vote?.selectedOptionIds || [];
                    if (selectedOptions.length > 0) {
                      logger.info({
                        selectedOptions,
                        pollMessageId: pollMessageKey.id,
                      }, 'Processing poll vote from messages.upsert');
                      await processPollVote(sock, pollMessageKey, selectedOptions, msg.key);
                      continue; // Don't process as regular message
                    }
                  }
                } catch (error) {
                  logger.warn({ error: error.message }, 'Error processing poll vote from messages.upsert');
                }
              }
            }
          }
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
          
          // Check for poll vote messages (they arrive in upsert too)
          if (msg.message?.pollUpdateMessage) {
            logger.info({
              pollUpdate: JSON.stringify(msg.message.pollUpdateMessage),
              key: JSON.stringify(msg.key),
            }, 'Poll vote received via messages.upsert - debugging structure');
            
            const pollUpdate = msg.message.pollUpdateMessage;
            const pollMessageKey = pollUpdate.pollCreationMessageKey;
            
            if (pollMessageKey?.id) {
              const isGroup = pollMessageKey.remoteJid?.includes('@g.us');
              if (isGroup) {
                try {
                  const groupMetadata = await sock.groupMetadata(pollMessageKey.remoteJid);
                  if (groupMetadata.subject === 'Minimee TEAM') {
                    // Get selected options
                    const selectedOptions = pollUpdate.vote?.selectedOptionIds || pollUpdate.vote?.selectedOptions || pollUpdate.pollUpdates?.[0]?.vote?.selectedOptionIds || [];
                    if (selectedOptions.length > 0) {
                      logger.info({
                        selectedOptions,
                        pollMessageId: pollMessageKey.id,
                      }, 'Processing poll vote from messages.upsert');
                      await processPollVote(sock, pollMessageKey, selectedOptions, msg.key);
                      continue; // Don't process as regular message
                    }
                  }
                } catch (error) {
                  logger.warn({ error: error.message }, 'Error processing poll vote from messages.upsert');
                }
              }
            }
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

    // Handle message sending errors and poll updates
    sock.ev.on('messages.update', async (updates) => {
      logger.info({
        updatesCount: updates.length,
      }, '=== messages.update event triggered ===');
      
      for (const update of updates) {
        // Handle message sending errors
        if (update.update?.status === 'ERROR') {
          logger.error({
            messageId: update.key.id,
            status: update.update.status,
          }, 'Message sending failed');
          continue;
        }
        
        // Log ALL update types for debugging (temporarily)
        // This is critical to see what events actually arrive
        logger.info({
          hasUpdate: !!update.update,
          updateKeys: update.update ? Object.keys(update.update) : [],
          updateType: update.update ? Object.keys(update.update)[0] : 'none',
          update: JSON.stringify(update.update).substring(0, 2000),
          key: JSON.stringify(update.key),
          remoteJid: update.key?.remoteJid,
          messageId: update.key?.id,
        }, '=== Messages.update event received (DEBUG) ===');
        
        // Try to get poll votes using Baileys helper function
        // Poll updates might come as regular message updates
        try {
          if (update.key?.remoteJid?.includes('@g.us') && update.key?.id) {
            const groupMetadata = await sock.groupMetadata(update.key.remoteJid);
            if (groupMetadata.subject === 'Minimee TEAM') {
              // Try to load the message and check if it's a poll
              const msg = await sock.loadMessage(update.key.remoteJid, update.key.id);
              if (msg?.message?.pollCreationMessage) {
                // This is a poll message, get aggregate votes
                const pollUpdate = update.update?.pollUpdateMessage ? update.update.pollUpdateMessage : null;
                const votes = await getAggregateVotesInPollMessage({
                  message: msg.message,
                  pollUpdates: pollUpdate ? [pollUpdate] : [],
                });
                
                logger.info({
                  pollMessageId: update.key.id,
                  votes: JSON.stringify(votes),
                  update: JSON.stringify(update.update).substring(0, 500),
                }, 'Poll votes retrieved via getAggregateVotesInPollMessage');
                
                // Process the latest vote
                if (votes && votes.votes && votes.votes.length > 0) {
                  // Get the most recent vote (last in array)
                  const latestVote = votes.votes[votes.votes.length - 1];
                  const selectedOptions = latestVote.selectedOptionIds || [];
                  
                  if (selectedOptions.length > 0) {
                    const pollMessageKey = { id: update.key.id, remoteJid: update.key.remoteJid };
                    await processPollVote(sock, pollMessageKey, selectedOptions, update.key);
                    continue;
                  }
                }
              }
            }
          }
        } catch (error) {
          // Not a poll or error loading - continue to check other update types
          logger.debug({ error: error.message }, 'Error checking poll votes');
        }
        
        // Handle poll vote updates (alternative method)
        if (update.update?.pollUpdateMessage) {
          const pollUpdate = update.update.pollUpdateMessage;
          
          // Log the full structure for debugging
          logger.info({
            pollUpdate: JSON.stringify(pollUpdate),
            updateKey: JSON.stringify(update.key),
          }, 'Poll update message received - debugging structure');
          
          // In Baileys, poll updates come with pollUpdates array
          // Each pollUpdate contains votes with selectedOptionIds
          const pollUpdates = pollUpdate.pollUpdates || [];
          
          if (pollUpdates.length === 0) {
            // Try alternative structure: direct vote on pollCreationMessageKey
            const pollMessageKey = pollUpdate.pollCreationMessageKey;
            
            if (!pollMessageKey || !pollMessageKey.id) {
              logger.warn('Poll update has no pollUpdates array and no pollCreationMessageKey');
              continue;
            }
            
            // Process single poll update
            const selectedOptions = pollUpdate.vote?.selectedOptionIds || pollUpdate.vote?.selectedOptions || [];
            await processPollVote(sock, pollMessageKey, selectedOptions, update.key);
            continue;
          }
          
          // Process multiple poll updates (each vote is separate)
          for (const pollVoteUpdate of pollUpdates) {
            const pollMessageKey = pollVoteUpdate.pollCreationMessageKey || pollUpdate.pollCreationMessageKey;
            if (!pollMessageKey || !pollMessageKey.id) {
              continue;
            }
            
            const selectedOptions = pollVoteUpdate.vote?.selectedOptionIds || pollVoteUpdate.vote?.selectedOptions || [];
            await processPollVote(sock, pollMessageKey, selectedOptions, update.key);
          }
        }
      }
    });

    // Helper function to process a poll vote
    async function processPollVote(sock, pollMessageKey, selectedOptions, updateKey) {
      try {
        // Check if this poll is from Minimee TEAM group
        const isGroup = pollMessageKey.remoteJid?.includes('@g.us');
        if (!isGroup) {
          return;
        }
        
        // Get group metadata to verify it's Minimee TEAM
        try {
          const groupMetadata = await sock.groupMetadata(pollMessageKey.remoteJid);
          if (groupMetadata.subject !== 'Minimee TEAM') {
            return;
          }
        } catch (error) {
          logger.warn({ error: error.message }, 'Could not get group metadata for poll update');
          return;
        }
        
        if (selectedOptions.length === 0) {
          logger.warn({
            pollMessageKey: pollMessageKey.id,
          }, 'Poll vote update has no selected options');
          return;
        }
            
        // Map poll option index (0, 1, 2, 3) to approval choice (A, B, C, NO)
        // Poll values are: ["A) Option A", "B) Option B", "C) Option C", "No) Ne pas répondre"]
        // Index 0 = A (option_index 0)
        // Index 1 = B (option_index 1)
        // Index 2 = C (option_index 2)
        // Index 3 = NO (action 'no')
        const selectedIndex = selectedOptions[0]; // Single choice poll, take first vote
        
        let approvalChoice = null;
        if (selectedIndex === 0) {
          approvalChoice = 0; // A
        } else if (selectedIndex === 1) {
          approvalChoice = 1; // B
        } else if (selectedIndex === 2) {
          approvalChoice = 2; // C
        } else if (selectedIndex === 3) {
          approvalChoice = 'no'; // NO
        } else {
          logger.warn({ selectedIndex }, 'Invalid poll vote index');
          return;
        }
        
        logger.info({
          selectedIndex,
          approvalChoice,
          pollMessageId: pollMessageKey.id,
          sender: updateKey.participant || updateKey.remoteJid,
        }, 'Poll vote received in Minimee TEAM group');
        
        // Get pending approval info from backend using the poll message ID as group_message_id
        const pendingApproval = await getPendingApprovalByGroupMessageId(pollMessageKey.id);
        
        if (!pendingApproval) {
          logger.warn({
            choice: approvalChoice,
            pollMessageId: pollMessageKey.id,
          }, 'Poll vote detected but pending approval not found');
          return;
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
            pollMessageId: pollMessageKey.id,
            approvalType,
          }, 'Cannot find message_id for WhatsApp approval response');
          return;
        }
        
        if (approvalType === 'email_draft' && !emailThreadId) {
          logger.warn({
            choice: approvalChoice,
            pollMessageId: pollMessageKey.id,
            approvalType,
          }, 'Cannot find email_thread_id for email draft approval response');
          return;
        }
        
        logger.info({
          messageId,
          emailThreadId,
          conversationId,
          choice: approvalChoice,
          selectedIndex,
          pollMessageId: pollMessageKey.id,
          approvalType,
        }, 'Processing poll vote approval response');
        
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
        }, 'Poll vote approval response sent to backend');
        
      } catch (error) {
        logger.error({
          error: error.message,
          stack: error.stack,
        }, 'Error processing poll vote update');
      }
    }

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

// GET /user-info - Get connected WhatsApp user info
app.get('/user-info', (req, res) => {
  try {
    if (!sock || connectionStatus !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'WhatsApp not connected',
      });
    }

    // Get user phone number from stored JID or current socket
    let userJid = currentUserJid;
    
    // Fallback: try to get from socket if not stored
    if (!userJid && sock) {
      if (sock.user?.id) {
        userJid = sock.user.id;
      } else if (sock.user?.jid) {
        userJid = sock.user.jid;
      }
    }
    
    if (!userJid) {
      return res.status(404).json({
        status: 'error',
        message: 'User info not available - user not connected or credentials not loaded',
      });
    }

    // Extract phone number from JID (format: 33612345678@s.whatsapp.net or just the number)
    const phone = typeof userJid === 'string' && userJid.includes('@') 
      ? userJid.split('@')[0] 
      : String(userJid).replace(/@.*$/, '');

    res.json({
      status: 'success',
      phone: phone,
      user_id: userJid,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting user info');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// POST /bridge/test-message - Send test message with different formats
app.post('/bridge/test-message', async (req, res) => {
  try {
    const { method, recipient } = req.body;

    if (!method) {
      return res.status(400).json({
        status: 'error',
        message: 'method is required (buttons, interactive, template, poll)',
      });
    }

    if (!recipient) {
      return res.status(400).json({
        status: 'error',
        message: 'recipient phone number is required',
      });
    }

    if (!sock || connectionStatus !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'WhatsApp not connected',
      });
    }

    // Import test message functions
    const { sendTestMessage } = await import('./test-messages.js');

    // Send test message with timeout (10 seconds)
    const sendPromise = sendTestMessage(sock, method, recipient);
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Test message timeout after 10s')), 10000)
    );

    const result = await Promise.race([sendPromise, timeoutPromise]);

    logger.info({
      method,
      recipient,
      messageId: result.group_message_id,
      format: result.format,
    }, 'Test message sent successfully');

    res.json({
      status: 'success',
      message: 'Test message sent',
      formatUsed: result.format,
      method: result.method,
      messageId: result.group_message_id,
    });
  } catch (error) {
    logger.error({ error: error.message, method: req.body.method }, 'Error sending test message');
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
