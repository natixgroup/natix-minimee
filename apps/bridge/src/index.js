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
import { promises as fs } from 'fs';
import { join } from 'path';
import { logger, logMessage, logConnection } from './logger.js';
import { sendMessageToBackend, checkBackendHealth, getPendingApprovalByGroupMessageId, sendApprovalResponse, sendDirectChatToBackend, sendMessageToBackendForDisplay } from './webhook.js';
import { initializeMinimeeTeam, getPollMessageFromCache } from './groups.js';
import axios from 'axios';

dotenv.config();

// Support both BACKEND_API_URL and BRIDGE_API_URL for backward compatibility
const BACKEND_API_URL = process.env.BACKEND_API_URL || process.env.BRIDGE_API_URL || 'http://localhost:8000';
const USER_ID = parseInt(process.env.USER_ID || '1', 10);
const BRIDGE_PORT = parseInt(process.env.BRIDGE_PORT || '3003', 10);

// Dual session support: user and minimee
let sockUser = null;
let sockMinimee = null;
let reconnectAttemptsUser = 0;
let reconnectAttemptsMinimee = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// State for HTTP API - User session
let connectionStatusUser = 'disconnected';
let currentQRUser = null;
let qrImageDataUser = null;
let currentUserJid = null;

// State for HTTP API - Minimee session
let connectionStatusMinimee = 'disconnected';
let currentQRMinimee = null;
let qrImageDataMinimee = null;
let currentMinimeeJid = null;

// Legacy variables for backward compatibility (point to user session)
let sock = null; // Will point to sockUser
let connectionStatus = 'disconnected';
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
 * Send message via WhatsApp (legacy - uses user session)
 */
export async function sendWhatsAppMessage(to, text) {
  return sendWhatsAppMessageViaUser(to, text);
}

/**
 * Send message via User WhatsApp account
 */
export async function sendWhatsAppMessageViaUser(to, text) {
  if (!sockUser) {
    throw new Error('User WhatsApp not connected');
  }

  try {
    const jid = formatJID(to);
    await sockUser.sendMessage(jid, { text });
    
    logMessage('outgoing', text, {
      to: jid,
      integrationType: 'user',
    });
    
    logger.info(`User: Message sent to ${jid}`);
    return true;
  } catch (error) {
    logger.error({ error: error.message, to, integrationType: 'user' }, 'Error sending message');
    throw error;
  }
}

/**
 * Send message via Minimee WhatsApp account
 */
export async function sendWhatsAppMessageViaMinimee(to, text) {
  if (!sockMinimee) {
    throw new Error('Minimee WhatsApp not connected');
  }

  try {
    const jid = formatJID(to);
    await sockMinimee.sendMessage(jid, { text });
    
    logMessage('outgoing', text, {
      to: jid,
      integrationType: 'minimee',
    });
    
    logger.info(`Minimee: Message sent to ${jid}`);
    return true;
  } catch (error) {
    logger.error({ error: error.message, to, integrationType: 'minimee' }, 'Error sending message');
    throw error;
  }
}

/**
 * Start User WhatsApp Bridge
 */
async function startUserBridge() {
  try {
    logger.info('Starting User WhatsApp Bridge...');
    logger.info(`Backend API: ${BACKEND_API_URL}`);
    
    // Reset reconnect counter if we're starting fresh (manual restart)
    // This allows manual restart even after max attempts
    if (reconnectAttemptsUser >= MAX_RECONNECT_ATTEMPTS) {
      logger.info('User: Resetting reconnect counter for fresh start');
      reconnectAttemptsUser = 0;
    }
    
    // Check backend health
    const backendHealthy = await checkBackendHealth();
    if (!backendHealthy) {
      logger.warn('Backend API not reachable, continuing anyway...');
    } else {
      logger.info('Backend API is healthy');
    }

    const { state, saveCreds } = await useMultiFileAuthState('auth_info_user');
    
    const { version } = await fetchLatestBaileysVersion();
    
    sockUser = makeWASocket({
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      logger,
      version,
      browser: ['Minimee User', 'Chrome', '1.0.0'],
      getMessage: async (key) => {
        // Try to get message from cache or return placeholder
        // This is needed for decrypting poll votes
        if (sockUser && sockUser.store) {
          try {
            const msg = await sockUser.loadMessage(key.remoteJid, key.id);
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

    // Legacy compatibility - point sock to sockUser
    sock = sockUser;

    sockUser.ev.on('creds.update', saveCreds);

    sockUser.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;
      
      if (qr) {
        connectionStatusUser = 'connecting';
        connectionStatus = 'connecting'; // Legacy
        currentQRUser = qr;
        currentQR = qr; // Legacy
        // Generate QR code as data URL for frontend
        try {
          qrImageDataUser = await QRCode.toDataURL(qr);
          qrImageData = qrImageDataUser; // Legacy
        } catch (error) {
          logger.error({ error: error.message }, 'Failed to generate QR image');
        }
        
        logger.info('QR Code generated for USER - scan with WhatsApp');
        console.log('\n📱 USER WhatsApp Connection - Scan this QR code with your phone:\n');
        qrcode.generate(qr, { small: true });
        console.log('\n📱 Instructions:');
        console.log('   1. Open WhatsApp on your phone');
        console.log('   2. Go to Settings > Linked Devices');
        console.log('   3. Tap "Link a Device"');
        console.log('   4. Point your camera at the QR code above\n');
      }

      if (connection === 'close') {
        connectionStatusUser = 'disconnected';
        connectionStatus = 'disconnected'; // Legacy
        currentQRUser = null;
        currentQR = null; // Legacy
        qrImageDataUser = null;
        qrImageData = null; // Legacy
        
        const error = lastDisconnect?.error;
        const statusCode = error?.output?.statusCode;
        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        
        logConnection('closed', {
          integrationType: 'user',
          shouldReconnect,
          statusCode: statusCode,
        });

        if (shouldReconnect && reconnectAttemptsUser < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsUser++;
          logger.info(`User: Reconnecting... (attempt ${reconnectAttemptsUser}/${MAX_RECONNECT_ATTEMPTS})`);
          setTimeout(() => startUserBridge(), 3000);
        } else {
          logger.error('User: Max reconnect attempts reached or logged out');
        }
      } else if (connection === 'open') {
        connectionStatusUser = 'connected';
        connectionStatus = 'connected'; // Legacy
        currentQRUser = null;
        currentQR = null; // Legacy
        qrImageDataUser = null;
        qrImageData = null; // Legacy
        
        // Store user JID when connected
        if (sockUser.user?.id) {
          currentUserJid = sockUser.user.id;
        } else {
          try {
            const { state: authState } = await useMultiFileAuthState('auth_info_user');
            if (authState.creds?.me?.id) {
              currentUserJid = authState.creds.me.id;
            }
          } catch (error) {
            logger.warn({ error: error.message }, 'Could not load user JID from auth state');
          }
        }
        
        reconnectAttemptsUser = 0;
        logConnection('open', { integrationType: 'user' });
        logger.info('✓ User WhatsApp connected successfully');
        
        // Initialize Minimee TEAM group
        try {
          await initializeMinimeeTeam(sockUser);
        } catch (error) {
          logger.error({ error: error.message }, 'Failed to initialize Minimee TEAM group');
        }
      } else if (connection === 'connecting') {
        connectionStatusUser = 'connecting';
        connectionStatus = 'connecting'; // Legacy
        logConnection('connecting', { integrationType: 'user' });
        logger.info('User: Connecting to WhatsApp...');
      }
    });

    // Listen for all events to catch poll votes
    sockUser.ev.on('messages.upsert', async (m) => {
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
          // Log every message received for debugging
          const msgText = extractMessageText(msg.message || {});
          logger.info({
            messageText: msgText.substring(0, 50),
            remoteJid: msg.key.remoteJid,
            fromMe: msg.key.fromMe,
            messageId: msg.key.id,
            hasText: !!msgText,
            isGroup: msg.key.remoteJid?.includes('@g.us'),
            hasPollUpdate: !!msg.message?.pollUpdateMessage,
          }, '=== Message received in upsert ===');
          
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
                  const groupMetadata = await sockUser.groupMetadata(pollMessageKey.remoteJid);
                  if (groupMetadata.subject === 'Minimee TEAM') {
                    // The vote is encrypted, we need to decrypt it using getAggregateVotesInPollMessage
                    // We need the original poll message. Try multiple methods to get it
                    let pollMessageData = null;
                    
                    try {
                      // Method 1: Try to get from our cache first (most reliable)
                      pollMessageData = getPollMessageFromCache(pollMessageKey.id);
                      if (pollMessageData) {
                        logger.info({
                          pollMessageId: pollMessageKey.id,
                        }, 'Loaded poll message from cache');
                      }
                      
                      // Method 2: Try using Baileys message store if available
                      if (!pollMessageData && sockUser.store && typeof sockUser.store.loadMessage === 'function') {
                        try {
                          pollMessageData = await sockUser.store.loadMessage(pollMessageKey.remoteJid, pollMessageKey.id);
                          logger.info({
                            pollMessageId: pollMessageKey.id,
                            hasMessage: !!pollMessageData,
                          }, 'Loaded poll message from store');
                        } catch (storeError) {
                          logger.debug({ error: storeError.message }, 'Message not in store');
                        }
                      }
                      
                      // Method 3: Try using getMessage callback
                      if (!pollMessageData && sockUser.getMessage) {
                        const messageKey = {
                          remoteJid: pollMessageKey.remoteJid,
                          id: pollMessageKey.id,
                          fromMe: pollMessageKey.fromMe || false,
                          participant: pollMessageKey.participant,
                        };
                        pollMessageData = await sockUser.getMessage(messageKey);
                        logger.info({
                          pollMessageId: pollMessageKey.id,
                          hasMessage: !!pollMessageData,
                        }, 'Loaded poll message via getMessage callback');
                      }
                      
                      // Method 3: If we still don't have the message, try to construct it from cache
                      // Check if we have the structure but need to fix it
                      if (!pollMessageData || !pollMessageData.message || !pollMessageData.message.pollCreationMessage) {
                        // Try to get from cache again (it might have been updated by the setTimeout)
                        const cached = getPollMessageFromCache(pollMessageKey.id);
                        if (cached && cached.message && cached.message.pollCreationMessage) {
                          pollMessageData = cached;
                          logger.info({
                            pollMessageId: pollMessageKey.id,
                          }, 'Retrieved poll message from cache (retry)');
                        } else {
                          logger.warn({
                            pollMessageId: pollMessageKey.id,
                            hasMessage: !!pollMessageData,
                            hasPollCreation: pollMessageData?.message?.pollCreationMessage ? true : false,
                            cacheHasMessage: cached?.message?.pollCreationMessage ? true : false,
                          }, 'Poll message not available - cannot decrypt votes automatically');
                        }
                      }
                    } catch (error) {
                      logger.warn({ 
                        error: error.message,
                        pollMessageId: pollMessageKey.id,
                      }, 'Error loading poll message');
                    }
                    
                    // Use Baileys helper to decrypt and aggregate votes
                    try {
                      // Try with the message if we have it, otherwise try with minimal structure
                      const votes = await getAggregateVotesInPollMessage({
                        message: pollMessageData?.message || { pollCreationMessage: {} },
                        pollUpdates: [pollUpdate],
                      });
                      
                      logger.info({
                        votes: JSON.stringify(votes),
                        pollMessageId: pollMessageKey.id,
                        votesStructure: typeof votes,
                        isArray: Array.isArray(votes),
                        votesLength: Array.isArray(votes) ? votes.length : (votes?.votes?.length || 0),
                        hasMessage: !!pollMessageData?.message?.pollCreationMessage,
                      }, 'Poll votes decrypted via getAggregateVotesInPollMessage');
                      
                      // getAggregateVotesInPollMessage returns different structures:
                      // - Sometimes { votes: [...] } with votes containing { selectedOptionIds, senderJid }
                      // - Sometimes [{ name, voters: [...] }] directly (array of options with voters)
                      
                      let selectedOptions = [];
                      let senderJid = msg.key.fromMe ? currentUserJid : (msg.key.participant || msg.key.remoteJid);
                      
                      // Handle different return structures
                      if (Array.isArray(votes)) {
                        // Structure: [{ name: "A) ...", voters: [...] }, ...]
                        // Find the option with voters
                        for (const option of votes) {
                          if (option.voters && option.voters.length > 0) {
                            // Get option index from name (A) = 0, B) = 1, C) = 2, No) = 3)
                            const optionIndex = option.name.startsWith('A)') ? 0 :
                                              option.name.startsWith('B)') ? 1 :
                                              option.name.startsWith('C)') ? 2 :
                                              option.name.startsWith('No)') ? 3 : -1;
                            if (optionIndex >= 0) {
                              selectedOptions = [optionIndex];
                              // Check if current user voted (if fromMe, or if participant matches)
                              const userVoted = option.voters.some(voter => {
                                const voterJid = typeof voter === 'string' ? voter : voter.jid || voter.id;
                                return voterJid === currentUserJid || voterJid === senderJid;
                              });
                              if (userVoted) {
                                logger.info({
                                  selectedOptions,
                                  optionIndex,
                                  optionName: option.name.substring(0, 50),
                                  pollMessageId: pollMessageKey.id,
                                }, 'Found vote in aggregated votes array (array format)');
                                break;
                              }
                            }
                          }
                        }
                      } else if (votes && votes.votes && Array.isArray(votes.votes)) {
                        // Structure: { votes: [{ selectedOptionIds: [0], senderJid: "..." }, ...] }
                        // Get the latest vote (most recent)
                        const latestVote = votes.votes[votes.votes.length - 1];
                        selectedOptions = latestVote.selectedOptionIds || [];
                        senderJid = latestVote.senderJid || senderJid;
                      }
                      
                      if (selectedOptions.length > 0) {
                        logger.info({
                          selectedOptions,
                          pollMessageId: pollMessageKey.id,
                          senderJid,
                        }, 'Processing decrypted poll vote from messages.upsert');
                        await processPollVote(sockUser, pollMessageKey, selectedOptions, msg.key, 'user');
                        continue; // Don't process as regular message
                      } else {
                        // Last resort for LID groups: Since getAggregateVotesInPollMessage doesn't work,
                        // we can't decrypt the vote. The only workaround is to:
                        // 1. Ask user to use buttons instead of polls for LID groups
                        // 2. Or monitor the poll message and detect when a vote is added
                        // For now, log that this is a known limitation
                        logger.warn({
                          pollMessageId: pollMessageKey.id,
                          votesStructure: typeof votes,
                          isArray: Array.isArray(votes),
                          votesSample: JSON.stringify(Array.isArray(votes) ? votes[0] : votes),
                          pollUpdateStructure: Object.keys(pollUpdate || {}),
                          hasVote: !!pollUpdate?.vote,
                          issue: 'LID group - votes cannot be decrypted by Baileys',
                        }, 'Vote detected but cannot decrypt (LID group limitation) - will try messages.update');
                        
                        // Note: For LID groups, getAggregateVotesInPollMessage doesn't work
                        // We'll rely on messages.update which might have aggregated vote counts
                        // But even that might not work. The best solution is to use buttons instead of polls
                        
                        // Don't continue - let messages.update handle it (though it will likely fail too)
                      }
                    } catch (decryptError) {
                      logger.error({ 
                        error: decryptError.message,
                        stack: decryptError.stack,
                        pollMessageId: pollMessageKey.id,
                      }, 'Error decrypting poll votes');
                    }
                  }
                } catch (error) {
                  logger.error({ 
                    error: error.message,
                    stack: error.stack,
                  }, 'Error processing poll vote from messages.upsert');
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
                  const groupMetadata = await sockUser.groupMetadata(pollMessageKey.remoteJid);
                  if (groupMetadata.subject === 'Minimee TEAM') {
                    // Get selected options
                    const selectedOptions = pollUpdate.vote?.selectedOptionIds || pollUpdate.vote?.selectedOptions || pollUpdate.pollUpdates?.[0]?.vote?.selectedOptionIds || [];
                    if (selectedOptions.length > 0) {
                      logger.info({
                        selectedOptions,
                        pollMessageId: pollMessageKey.id,
                      }, 'Processing poll vote from messages.upsert');
                      await processPollVote(sockUser, pollMessageKey, selectedOptions, msg.key, 'user');
                      continue; // Don't process as regular message
                    }
                  }
                } catch (error) {
                  logger.warn({ error: error.message }, 'Error processing poll vote from messages.upsert');
                }
              }
            }
          }
          
          // Handle group messages (Minimee TEAM) - only for user session
          if (isGroup) {
            // Get group name
            try {
              const groupMetadata = await sockUser.groupMetadata(msg.key.remoteJid);
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
                      await sockUser.sendMessage(groupJid, { 
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

          logger.info({
            messageText: messageText.substring(0, 50),
            senderJid,
            senderName,
            fromMe: msg.key.fromMe,
            isGroup,
            messageId,
          }, 'Processing individual message (before forwarding to backend)');

          logMessage('incoming', messageText, {
            from: senderJid,
            senderName,
            messageId,
            timestamp: timestamp.toISOString(),
          });

          // Forward to backend
          // Note: We process ALL messages (including fromMe) to create embeddings
          // The backend will decide what to do with them
          try {
            const conversationId = senderJid.split('@')[0];
            
            logger.info({
              content: messageText.substring(0, 50),
              sender: senderName,
              conversationId,
              fromMe: msg.key.fromMe,
            }, 'Sending individual message to backend for processing');
            
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
    sockUser.ev.on('messages.update', async (updates) => {
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
            const groupMetadata = await sockUser.groupMetadata(update.key.remoteJid);
            if (groupMetadata.subject === 'Minimee TEAM') {
              // Check if this is a poll update
              if (update.update?.pollUpdateMessage) {
                const pollUpdate = update.update.pollUpdateMessage;
                const pollMessageKey = pollUpdate.pollCreationMessageKey;
                
                if (pollMessageKey?.id === update.key.id) {
                  // Try to get poll message from cache or store
                  let pollMessageData = getPollMessageFromCache(update.key.id);
                  
                  if (!pollMessageData) {
                    // Try from store
                    if (sock.store && typeof sock.store.loadMessage === 'function') {
                      try {
                        pollMessageData = await sock.store.loadMessage(update.key.remoteJid, update.key.id);
                      } catch (e) {
                        logger.debug({ error: e.message }, 'Poll message not in store');
                      }
                    }
                  }
                  
                  // Use cache or construct minimal structure
                  if (!pollMessageData || !pollMessageData.message) {
                    pollMessageData = getPollMessageFromCache(update.key.id) || {
                      message: { pollCreationMessage: {} },
                      key: update.key,
                    };
                  }
                  
                  // For LID groups, getAggregateVotesInPollMessage often fails
                  // Instead, try to get vote counts directly from the poll message
                  let selectedOptions = [];
                  
                  if (pollUpdate) {
                    // Try decrypting first
                    try {
                      const votes = await getAggregateVotesInPollMessage({
                        message: pollMessageData.message,
                        pollUpdates: [pollUpdate],
                      });
                      
                      logger.info({
                        pollMessageId: update.key.id,
                        votes: JSON.stringify(votes),
                        votesStructure: typeof votes,
                        isArray: Array.isArray(votes),
                        hasMessage: !!pollMessageData?.message?.pollCreationMessage,
                      }, 'Poll votes retrieved via getAggregateVotesInPollMessage in messages.update');
                      
                      // Process votes
                      if (Array.isArray(votes)) {
                        for (const option of votes) {
                          if (option.voters && option.voters.length > 0) {
                            const optionIndex = option.name.startsWith('A)') ? 0 :
                                              option.name.startsWith('B)') ? 1 :
                                              option.name.startsWith('C)') ? 2 :
                                              option.name.startsWith('No)') ? 3 : -1;
                            if (optionIndex >= 0) {
                              selectedOptions = [optionIndex];
                              break;
                            }
                          }
                        }
                      } else if (votes && votes.votes && Array.isArray(votes.votes)) {
                        const latestVote = votes.votes[votes.votes.length - 1];
                        selectedOptions = latestVote.selectedOptionIds || [];
                      }
                    } catch (decryptError) {
                      logger.debug({ error: decryptError.message }, 'Decryption failed (expected for LID groups)');
                    }
                  }
                  
                  // Fallback: Try to get vote counts from message directly (if available)
                  // This works by checking which option has increased vote count
                  if (selectedOptions.length === 0 && pollMessageData && pollMessageData.message && pollMessageData.message.pollCreationMessage) {
                    // Check if we have a stored previous state to compare
                    // For now, we'll try a different approach: get the latest poll message state
                    try {
                      const currentMessage = await (async () => {
                        if (sock.store && typeof sock.store.loadMessage === 'function') {
                          return await sock.store.loadMessage(update.key.remoteJid, update.key.id);
                        }
                        return null;
                      })();
                      
                      if (currentMessage?.message?.pollCreationMessage) {
                        // Poll message exists, but vote info might not be in this structure
                        // We need to check vote counts if available
                        logger.info({
                          pollMessageId: update.key.id,
                        }, 'Poll message available but vote counts not accessible in LID groups');
                      }
                    } catch (e) {
                      // Ignore
                    }
                  }
                  
                  if (selectedOptions.length > 0) {
                    await processPollVote(sock, pollMessageKey, selectedOptions, update.key);
                    continue;
                  }
                }
              }
              
              // Also check if message is a poll by loading it
              let msg = null;
              if (sock.store && typeof sock.store.loadMessage === 'function') {
                try {
                  msg = await sock.store.loadMessage(update.key.remoteJid, update.key.id);
                } catch (e) {
                  // Not in store, that's ok
                }
              }
              
              if (msg?.message?.pollCreationMessage && !update.update?.pollUpdateMessage) {
                // Poll message but no update - might be initial creation, skip
                continue;
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
    async function processPollVote(sock, pollMessageKey, selectedOptions, updateKey, integrationType = 'user') {
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

    return sockUser;
  } catch (error) {
    logger.error({ 
      error: error.message,
      stack: error.stack,
      integrationType: 'user' 
    }, 'User bridge startup error');
    // Don't throw - let it retry later
    connectionStatusUser = 'disconnected';
    setTimeout(() => {
      logger.info('Retrying User bridge startup...');
      startUserBridge().catch(err => {
        logger.error({ error: err.message }, 'Failed to retry User bridge');
      });
    }, 5000);
    return null;
  }
}

/**
 * Start Minimee WhatsApp Bridge
 */
async function startMinimeeBridge() {
  try {
    logger.info('Starting Minimee WhatsApp Bridge...');
    
    // Reset reconnect counter if we're starting fresh (manual restart)
    // This allows manual restart even after max attempts
    if (reconnectAttemptsMinimee >= MAX_RECONNECT_ATTEMPTS) {
      logger.info('Minimee: Resetting reconnect counter for fresh start');
      reconnectAttemptsMinimee = 0;
    }
    
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_minimee');
    const { version } = await fetchLatestBaileysVersion();
    
    const sock = makeWASocket({
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      logger,
      version,
      browser: ['Minimee', 'Chrome', '1.0.0'],
      getMessage: async (key) => {
        if (sockMinimee && sockMinimee.store) {
          try {
            const msg = await sockMinimee.loadMessage(key.remoteJid, key.id);
            if (msg) return msg;
          } catch (error) {
            // Message not in cache
          }
        }
        return {
          conversation: 'Message not available',
        };
      },
    });

    sockMinimee = sock;

    sockMinimee.ev.on('creds.update', saveCreds);

    sockMinimee.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;
      
      if (qr) {
        connectionStatusMinimee = 'connecting';
        currentQRMinimee = qr;
        try {
          qrImageDataMinimee = await QRCode.toDataURL(qr);
        } catch (error) {
          logger.error({ error: error.message }, 'Failed to generate QR image');
        }
        
        logger.info('QR Code generated for MINIMEE - scan with WhatsApp');
        console.log('\n🤖 MINIMEE WhatsApp Connection - Scan this QR code:\n');
        qrcode.generate(qr, { small: true });
      }

      if (connection === 'close') {
        connectionStatusMinimee = 'disconnected';
        currentQRMinimee = null;
        qrImageDataMinimee = null;
        
        const error = lastDisconnect?.error;
        const statusCode = error?.output?.statusCode;
        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        
        logConnection('closed', {
          integrationType: 'minimee',
          shouldReconnect,
          statusCode: statusCode,
        });

        if (shouldReconnect && reconnectAttemptsMinimee < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsMinimee++;
          logger.info(`Minimee: Reconnecting... (attempt ${reconnectAttemptsMinimee}/${MAX_RECONNECT_ATTEMPTS})`);
          setTimeout(() => startMinimeeBridge(), 3000);
        } else {
          logger.error('Minimee: Max reconnect attempts reached or logged out');
        }
      } else if (connection === 'open') {
        connectionStatusMinimee = 'connected';
        currentQRMinimee = null;
        qrImageDataMinimee = null;
        
        if (sockMinimee.user?.id) {
          currentMinimeeJid = sockMinimee.user.id;
        }
        
        reconnectAttemptsMinimee = 0;
        logConnection('open', { integrationType: 'minimee' });
        logger.info('✓ Minimee WhatsApp connected successfully');
        
        // Initialize Minimee TEAM group on Minimee account (with User + Minimee)
        try {
          const { initializeMinimeeTeam } = await import('./groups.js');
          // Get User phone number from User account to add to Minimee TEAM group
          let userPhoneJid = null;
          if (sockUser && connectionStatusUser === 'connected' && currentUserJid) {
            userPhoneJid = currentUserJid;
          } else if (sockUser && connectionStatusUser === 'connected' && sockUser.user?.id) {
            userPhoneJid = sockUser.user.id;
          }
          await initializeMinimeeTeam(sockMinimee, userPhoneJid);
        } catch (error) {
          logger.error({ error: error.message }, 'Failed to initialize Minimee TEAM group on Minimee account');
        }
      } else if (connection === 'connecting') {
        connectionStatusMinimee = 'connecting';
        logConnection('connecting', { integrationType: 'minimee' });
        logger.info('Minimee: Connecting to WhatsApp...');
      }
    });

    // Handle messages for Minimee session
    sockMinimee.ev.on('messages.upsert', async (m) => {
      try {
        const { messages, type } = m;
        
        if (type !== 'notify') {
          return;
        }

        for (const msg of messages) {
          const messageText = extractMessageText(msg.message || {});
          
          if (!messageText) {
            continue;
          }

          // Skip status broadcasts
          if (msg.key.remoteJid === 'status@broadcast') {
            continue;
          }

          const isGroup = msg.key.remoteJid?.includes('@g.us');
          
          // Skip groups for Minimee session (only handle direct messages)
          if (isGroup) {
            continue;
          }

          // Handle direct messages to Minimee
          // Check if sender is user account (for dashboard sync)
          const senderJid = msg.key.remoteJid;
          const senderName = msg.pushName || senderJid.split('@')[0];
          const timestamp = msg.messageTimestamp 
            ? new Date(msg.messageTimestamp * 1000) 
            : new Date();

          // Get user phone number from bridge to check if sender is user
          let isUserMessage = false;
          try {
            const bridgeUrl = process.env.BRIDGE_API_URL || 'http://localhost:3003';
            const userInfoResponse = await axios.get(`${bridgeUrl}/user-info`);
            if (userInfoResponse.data && userInfoResponse.data.phone) {
              const userPhone = userInfoResponse.data.phone.replace(/[^0-9]/g, '');
              const userPhoneJid = `${userPhone}@s.whatsapp.net`;
              const senderPhone = senderJid.split('@')[0].replace(/[^0-9]/g, '');
              isUserMessage = senderJid === userPhoneJid || senderPhone === userPhone;
            }
          } catch (error) {
            logger.warn({ error: error.message }, 'Could not check if sender is user, treating as user message');
            // Fallback: treat as user message if we can't check
            isUserMessage = true;
          }

          // Only process messages from user account (for dashboard sync)
          // Other messages would be external contacts talking to Minimee
          if (isUserMessage) {
            // Use dashboard-minimee conversation_id for sync
            const conversationId = `dashboard-minimee-${USER_ID}`;
            
            try {
              const chatResponse = await sendDirectChatToBackend({
                content: messageText,
                sender: senderName,
                timestamp: timestamp.toISOString(),
                source: 'whatsapp',
                conversation_id: conversationId,
                user_id: USER_ID,
              });
              
              // Response will be sent back via Minimee account in chat_direct endpoint
            } catch (error) {
              logger.error({ 
                error: error.message,
                integrationType: 'minimee',
              }, 'Error processing direct message to Minimee');
            }
          } else {
            // External contact messaging Minimee - generate proposals and send via USER account
            // This is similar to how user session handles messages
            const conversationId = senderJid.split('@')[0];
            
            try {
              await sendMessageToBackend({
                content: messageText,
                sender: senderName,
                timestamp: timestamp.toISOString(),
                source: 'whatsapp',
                conversation_id: conversationId,
                user_id: USER_ID,
              });
            } catch (error) {
              logger.error({ 
                error: error.message,
                integrationType: 'minimee',
              }, 'Error processing external message to Minimee');
            }
          }
        }
      } catch (error) {
        logger.error({ error: error.message, integrationType: 'minimee' }, 'Error in messages.upsert for Minimee');
      }
    });

    return sockMinimee;
  } catch (error) {
    logger.error({ 
      error: error.message,
      stack: error.stack,
      integrationType: 'minimee' 
    }, 'Minimee bridge startup error');
    // Don't throw - let it retry later
    connectionStatusMinimee = 'disconnected';
    setTimeout(() => {
      logger.info('Retrying Minimee bridge startup...');
      startMinimeeBridge().catch(err => {
        logger.error({ error: err.message }, 'Failed to retry Minimee bridge');
      });
    }, 5000);
    return null;
  }
}

// Legacy function for backward compatibility
async function startBridge() {
  return startUserBridge();
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  logger.info('Shutting down WhatsApp Bridge...');
  if (sockUser) {
    sockUser.end(undefined);
  }
  if (sockMinimee) {
    sockMinimee.end(undefined);
  }
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down WhatsApp Bridge...');
  if (sockUser) {
    sockUser.end(undefined);
  }
  if (sockMinimee) {
    sockMinimee.end(undefined);
  }
  process.exit(0);
});

// HTTP API Server
const app = express();
app.use(cors());
app.use(express.json());

// ==================== USER ENDPOINTS ====================

// GET /user/status
app.get('/user/status', (req, res) => {
  try {
    res.json({
      status: connectionStatusUser === 'connected' ? 'connected' : (connectionStatusUser === 'connecting' ? 'pending' : 'disconnected'),
      running: true,
      connected: connectionStatusUser === 'connected',
      has_qr: !!currentQRUser,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting user status');
    res.status(500).json({
      status: 'error',
      running: false,
      connected: false,
      has_qr: false,
      error: error.message,
    });
  }
});

// GET /user/qr
app.get('/user/qr', async (req, res) => {
  try {
    if (currentQRUser && qrImageDataUser) {
      res.json({
        qr_available: true,
        qr_data: qrImageDataUser,
        qr_text: currentQRUser,
      });
    } else {
      res.json({
        qr_available: false,
        qr_data: null,
        qr_text: null,
      });
    }
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting user QR code');
    res.status(500).json({
      qr_available: false,
      qr_data: null,
      qr_text: null,
      error: error.message,
    });
  }
});

// POST /user/restart
app.post('/user/restart', async (req, res) => {
  // Always return success immediately - the restart is initiated
  res.json({
    status: 'restarting',
    message: 'User bridge restarting, new QR code will be available shortly',
  });
  
  // Silently clean up socket - ignore all errors
  // Use setImmediate to ensure response is sent before cleanup
  setImmediate(async () => {
    if (sockUser) {
      try {
        if (connectionStatusUser === 'connected' && typeof sockUser.logout === 'function') {
          sockUser.logout().catch(() => {
            // Ignore all logout errors
          });
        }
      } catch (e) {
        // Ignore all errors
      }
      
      try {
        if (typeof sockUser.end === 'function') {
          sockUser.end(undefined);
        }
      } catch (e) {
        // Ignore all errors
      }
      
      sockUser = null;
      sock = null; // Legacy compatibility
    }
    
    // Delete auth files to force fresh QR code generation
    try {
      const authDir = 'auth_info_user';
      const files = await fs.readdir(authDir);
      for (const file of files) {
        await fs.unlink(join(authDir, file)).catch(() => {
          // Ignore errors
        });
      }
      logger.info('User: Cleared auth files for fresh connection');
    } catch (e) {
      // Auth dir might not exist or be empty, that's ok
      logger.info('User: No auth files to clear (fresh start)');
    }
    
    // Reset all state including reconnect counter
    connectionStatusUser = 'disconnected';
    connectionStatus = 'disconnected'; // Legacy compatibility
    reconnectAttemptsUser = 0; // Reset reconnect counter for manual restart
    currentQRUser = null;
    currentQR = null; // Legacy compatibility
    qrImageDataUser = null;
    qrImageData = null; // Legacy compatibility
    
    // Start bridge after a short delay
    setTimeout(() => {
      startUserBridge().catch(err => {
        logger.error({ error: err.message }, 'Failed to restart user bridge');
      });
    }, 1000);
  });
});

// POST /user/send
app.post('/user/send', async (req, res) => {
  try {
    const { recipient, message, source } = req.body;
    
    if (!recipient || !message) {
      return res.status(400).json({
        status: 'error',
        message: 'recipient and message are required',
      });
    }
    
    if (!sockUser || connectionStatusUser !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'User WhatsApp not connected',
      });
    }
    
    if (source !== 'whatsapp') {
      return res.status(400).json({
        status: 'error',
        message: 'Only WhatsApp source is supported',
      });
    }
    
    const jid = formatJID(recipient);
    await sockUser.sendMessage(jid, { text: message });
    
    logMessage('outgoing', message, {
      to: jid,
      source,
      integrationType: 'user',
    });
    
    logger.info(`User: Message sent to ${jid}`);
    
    res.json({
      status: 'success',
      sent: true,
      recipient: jid,
    });
  } catch (error) {
    logger.error({ error: error.message, recipient: req.body.recipient }, 'Error sending message via user');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// ==================== MINIMEE ENDPOINTS ====================

// GET /minimee/status
app.get('/minimee/status', (req, res) => {
  try {
    res.json({
      status: connectionStatusMinimee === 'connected' ? 'connected' : (connectionStatusMinimee === 'connecting' ? 'pending' : 'disconnected'),
      running: true,
      connected: connectionStatusMinimee === 'connected',
      has_qr: !!currentQRMinimee,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting minimee status');
    res.status(500).json({
      status: 'error',
      running: false,
      connected: false,
      has_qr: false,
      error: error.message,
    });
  }
});

// GET /minimee/qr
app.get('/minimee/qr', async (req, res) => {
  try {
    if (currentQRMinimee && qrImageDataMinimee) {
      res.json({
        qr_available: true,
        qr_data: qrImageDataMinimee,
        qr_text: currentQRMinimee,
      });
    } else {
      res.json({
        qr_available: false,
        qr_data: null,
        qr_text: null,
      });
    }
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting minimee QR code');
    res.status(500).json({
      qr_available: false,
      qr_data: null,
      qr_text: null,
      error: error.message,
    });
  }
});

// POST /minimee/restart
app.post('/minimee/restart', async (req, res) => {
  // Always return success immediately - the restart is initiated
  res.json({
    status: 'restarting',
    message: 'Minimee bridge restarting, new QR code will be available shortly',
  });
  
  // Silently clean up socket - ignore all errors
  // Use setImmediate to ensure response is sent before cleanup
  setImmediate(async () => {
    if (sockMinimee) {
      try {
        if (connectionStatusMinimee === 'connected' && typeof sockMinimee.logout === 'function') {
          sockMinimee.logout().catch(() => {
            // Ignore all logout errors
          });
        }
      } catch (e) {
        // Ignore all errors
      }
      
      try {
        if (typeof sockMinimee.end === 'function') {
          sockMinimee.end(undefined);
        }
      } catch (e) {
        // Ignore all errors
      }
      
      sockMinimee = null;
    }
    
    // Delete auth files to force fresh QR code generation
    try {
      const authDir = 'auth_info_minimee';
      const files = await fs.readdir(authDir);
      for (const file of files) {
        await fs.unlink(join(authDir, file)).catch(() => {
          // Ignore errors
        });
      }
      logger.info('Minimee: Cleared auth files for fresh connection');
    } catch (e) {
      // Auth dir might not exist or be empty, that's ok
      logger.info('Minimee: No auth files to clear (fresh start)');
    }
    
    // Reset all state including reconnect counter
    connectionStatusMinimee = 'disconnected';
    reconnectAttemptsMinimee = 0; // Reset reconnect counter for manual restart
    currentQRMinimee = null;
    qrImageDataMinimee = null;
    
    // Start bridge after a short delay
    setTimeout(() => {
      startMinimeeBridge().catch(err => {
        logger.error({ error: err.message }, 'Failed to restart minimee bridge');
      });
    }, 1000);
  });
});

// POST /minimee/send
app.post('/minimee/send', async (req, res) => {
  try {
    const { recipient, message, source } = req.body;
    
    if (!recipient || !message) {
      return res.status(400).json({
        status: 'error',
        message: 'recipient and message are required',
      });
    }
    
    if (!sockMinimee || connectionStatusMinimee !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'Minimee WhatsApp not connected',
      });
    }
    
    if (source !== 'whatsapp') {
      return res.status(400).json({
        status: 'error',
        message: 'Only WhatsApp source is supported',
      });
    }
    
    const jid = formatJID(recipient);
    await sockMinimee.sendMessage(jid, { text: message });
    
    logMessage('outgoing', message, {
      to: jid,
      source,
      integrationType: 'minimee',
    });
    
    logger.info(`Minimee: Message sent to ${jid}`);
    
    res.json({
      status: 'success',
      sent: true,
      recipient: jid,
    });
  } catch (error) {
    logger.error({ error: error.message, recipient: req.body.recipient }, 'Error sending message via minimee');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// ==================== LEGACY ENDPOINTS (backward compatibility) ====================

// GET /status - Get connection status (legacy - returns user status)
app.get('/status', (req, res) => {
  try {
    res.json({
      status: connectionStatusUser === 'connected' ? 'connected' : (connectionStatusUser === 'connecting' ? 'pending' : 'disconnected'),
      running: true,
      connected: connectionStatusUser === 'connected',
      has_qr: !!currentQRUser,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting legacy status');
    res.status(500).json({
      status: 'error',
      running: false,
      connected: false,
      has_qr: false,
      error: error.message,
    });
  }
});

// GET /qr - Get QR code (legacy - returns user QR)
app.get('/qr', async (req, res) => {
  try {
    if (currentQRUser && qrImageDataUser) {
      res.json({
        qr_available: true,
        qr_data: qrImageDataUser,
        qr_text: currentQRUser,
      });
    } else {
      res.json({
        qr_available: false,
        qr_data: null,
        qr_text: null,
      });
    }
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting legacy QR code');
    res.status(500).json({
      qr_available: false,
      qr_data: null,
      qr_text: null,
      error: error.message,
    });
  }
});

// POST /restart - Restart connection (legacy - restarts user session)
app.post('/restart', (req, res) => {
  // Silently clean up socket - ignore all errors
  // Use setImmediate to ensure response is sent before cleanup
  setImmediate(() => {
    if (sockUser) {
      try {
        if (connectionStatusUser === 'connected' && typeof sockUser.logout === 'function') {
          sockUser.logout().catch(() => {
            // Ignore all logout errors
          });
        }
      } catch (e) {
        // Ignore all errors
      }
      
      try {
        if (typeof sockUser.end === 'function') {
          sockUser.end(undefined);
        }
      } catch (e) {
        // Ignore all errors
      }
      
      sockUser = null;
      sock = null; // Legacy compatibility
    }
    
    // Reset all state
    connectionStatusUser = 'disconnected';
    connectionStatus = 'disconnected'; // Legacy compatibility
    currentQRUser = null;
    currentQR = null; // Legacy compatibility
    qrImageDataUser = null;
    qrImageData = null; // Legacy compatibility
    
    // Start bridge after a short delay
    setTimeout(() => {
      startUserBridge().catch(err => {
        logger.error({ error: err.message }, 'Failed to restart user bridge');
      });
    }, 1000);
  });
  
  // Always return success immediately - the restart is initiated
  res.json({
    status: 'restarting',
    message: 'Bridge restarting, new QR code will be available shortly',
  });
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
    
    const userStatus = connectionStatusUser === 'connected';
    if (!sockUser || !userStatus) {
      return res.status(503).json({
        status: 'error',
        message: 'User WhatsApp not connected',
      });
    }
    
    // Import group function
    const { sendApprovalMessageToGroup } = await import('./groups.js');
    
    // Send to group with timeout protection
    // Use Promise.race to ensure we don't wait forever
    const sendPromise = sendApprovalMessageToGroup(sockUser, {
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
    
    // Legacy endpoint - uses user session
    if (!sockUser || connectionStatusUser !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'User WhatsApp not connected',
      });
    }
    
    if (source !== 'whatsapp') {
      return res.status(400).json({
        status: 'error',
        message: 'Only WhatsApp source is supported',
      });
    }
    
    const jid = formatJID(recipient);
    await sockUser.sendMessage(jid, { text: message });
    
    logMessage('outgoing', message, {
      to: jid,
      source,
      integrationType: 'user',
    });
    
    logger.info(`User: Message sent to ${jid}`);
    
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

// GET /user-info - Get connected WhatsApp user info (legacy - returns user session info)
app.get('/user-info', (req, res) => {
  try {
    if (!sockUser || connectionStatusUser !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'User WhatsApp not connected',
      });
    }

    // Get user phone number from stored JID or current socket
    let userJid = currentUserJid;
    
    // Fallback: try to get from socket if not stored
    if (!userJid && sockUser) {
      if (sockUser.user?.id) {
        userJid = sockUser.user.id;
      } else if (sockUser.user?.jid) {
        userJid = sockUser.user.jid;
      }
    }
    
    if (!userJid) {
      return res.status(404).json({
        status: 'error',
        message: 'User info not available - user not connected or credentials not loaded',
      });
    }

    // Extract phone number from JID (format: 33612345678@s.whatsapp.net or 33612345678:47@s.whatsapp.net)
    // Remove device/session ID after colon if present
    let phone = typeof userJid === 'string' && userJid.includes('@') 
      ? userJid.split('@')[0] 
      : String(userJid).replace(/@.*$/, '');
    // Remove device/session ID (everything after colon)
    phone = phone.split(':')[0];

    // Detect if it's WhatsApp Business (JID contains @c.us instead of @s.whatsapp.net)
    const isBusiness = typeof userJid === 'string' && userJid.includes('@c.us');
    const accountType = isBusiness ? 'business' : 'standard';

    res.json({
      status: 'success',
      phone: phone,
      user_id: userJid,
      account_type: accountType,
      is_business: isBusiness,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting user info');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// GET /minimee/user-info - Get connected Minimee WhatsApp info
app.get('/minimee/user-info', (req, res) => {
  try {
    if (!sockMinimee || connectionStatusMinimee !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: 'Minimee WhatsApp not connected',
      });
    }

    // Get Minimee phone number from stored JID or current socket
    let minimeeJid = currentMinimeeJid;
    
    // Fallback: try to get from socket if not stored
    if (!minimeeJid && sockMinimee) {
      if (sockMinimee.user?.id) {
        minimeeJid = sockMinimee.user.id;
      } else if (sockMinimee.user?.jid) {
        minimeeJid = sockMinimee.user.jid;
      }
    }
    
    if (!minimeeJid) {
      return res.status(404).json({
        status: 'error',
        message: 'Minimee info not available - not connected or credentials not loaded',
      });
    }

    // Extract phone number from JID (format: 33612345678@s.whatsapp.net or 33612345678:47@s.whatsapp.net)
    // Remove device/session ID after colon if present
    let phone = typeof minimeeJid === 'string' && minimeeJid.includes('@') 
      ? minimeeJid.split('@')[0] 
      : String(minimeeJid).replace(/@.*$/, '');
    // Remove device/session ID (everything after colon)
    phone = phone.split(':')[0];

    // Detect if it's WhatsApp Business (JID contains @c.us instead of @s.whatsapp.net)
    const isBusiness = typeof minimeeJid === 'string' && minimeeJid.includes('@c.us');
    const accountType = isBusiness ? 'business' : 'standard';

    res.json({
      status: 'success',
      phone: phone,
      user_id: minimeeJid,
      account_type: accountType,
      is_business: isBusiness,
    });
  } catch (error) {
    logger.error({ error: error.message }, 'Error getting Minimee info');
    res.status(500).json({
      status: 'error',
      message: error.message,
    });
  }
});

// POST /bridge/test-message - Send test message with different formats
// Messages can be sent from User or Minimee account to either User WhatsApp or Minimee TEAM group
app.post('/bridge/test-message', async (req, res) => {
  try {
    const { method, sender, destination, userPhone } = req.body;

    if (!method) {
      return res.status(400).json({
        status: 'error',
        message: 'method is required (buttons, interactive, template, poll)',
      });
    }

    if (!sender || !['user', 'minimee'].includes(sender)) {
      return res.status(400).json({
        status: 'error',
        message: 'sender is required and must be "user" or "minimee"',
      });
    }

    if (!destination || !['user', 'group'].includes(destination)) {
      return res.status(400).json({
        status: 'error',
        message: 'destination is required and must be "user" or "group"',
      });
    }

    // Check sender account connection
    const sock = sender === 'user' ? sockUser : sockMinimee;
    const connectionStatus = sender === 'user' ? connectionStatusUser : connectionStatusMinimee;
    const accountName = sender === 'user' ? 'User' : 'Minimee';

    if (!sock || connectionStatus !== 'connected') {
      return res.status(503).json({
        status: 'error',
        message: `${accountName} WhatsApp not connected`,
      });
    }

    // Import test message functions and group utilities
    const { sendTestMessage } = await import('./test-messages.js');
    const { findGroupByName } = await import('./groups.js');

    let recipientJid;
    
    if (destination === 'user') {
      // Send to User WhatsApp
      if (!userPhone) {
        return res.status(400).json({
          status: 'error',
          message: 'userPhone is required when destination is "user"',
        });
      }
      recipientJid = userPhone.includes('@') ? userPhone : `${userPhone.replace(/[^0-9]/g, '')}@s.whatsapp.net`;
    } else {
      // Send to Minimee TEAM group
      // For group, we need to use the account that has the group
      // If sender is user, use user account's group; if sender is minimee, use minimee account's group
      const groupSock = sender === 'user' ? sockUser : sockMinimee;
      const group = await findGroupByName(groupSock, 'Minimee TEAM');
      if (!group) {
        return res.status(404).json({
          status: 'error',
          message: 'Minimee TEAM group not found. Please ensure it is initialized.',
        });
      }
      recipientJid = group.id;
    }

    // Send test message with timeout (10 seconds)
    const sendPromise = sendTestMessage(sock, method, recipientJid);
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Test message timeout after 10s')), 10000)
    );

    const result = await Promise.race([sendPromise, timeoutPromise]);

    logger.info({
      method,
      sender,
      destination,
      recipient: recipientJid,
      messageId: result.group_message_id,
      format: result.format,
    }, `Test message sent successfully from ${accountName} account`);

    res.json({
      status: 'success',
      message: `Test message sent from ${accountName} to ${destination === 'user' ? 'User WhatsApp' : 'Minimee TEAM group'}`,
      formatUsed: result.format,
      method: result.method,
      messageId: result.group_message_id,
      sender,
      destination,
    });
  } catch (error) {
    logger.error({ 
      error: error.message, 
      method: req.body.method, 
      sender: req.body.sender,
      destination: req.body.destination 
    }, 'Error sending test message');
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

// Start both bridges with error handling
// Start user bridge first, then minimee after a short delay to avoid conflicts
startUserBridge().catch(err => {
  logger.error({ 
    error: err.message,
    stack: err.stack 
  }, 'Failed to start user bridge');
  connectionStatusUser = 'disconnected';
});

// Start Minimee bridge after a short delay to avoid potential conflicts
setTimeout(() => {
  startMinimeeBridge().catch(err => {
    logger.error({ 
      error: err.message,
      stack: err.stack 
    }, 'Failed to start minimee bridge');
    connectionStatusMinimee = 'disconnected';
  });
}, 2000); // 2 second delay
