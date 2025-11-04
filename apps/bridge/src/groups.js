/**
 * Group management for WhatsApp
 * Auto-creates "Minimee TEAM" group and manages agents
 */
import { logger, logGroupOperation } from './logger.js';
import dotenv from 'dotenv';

dotenv.config();

const GROUP_NAME = 'Minimee TEAM';
const AGENT_PHONES = process.env.AGENT_PHONES 
  ? process.env.AGENT_PHONES.split(',').map(p => p.trim()).filter(Boolean)
  : [];

// Cache for poll messages: pollMessageId -> pollMessage
// This allows us to decrypt votes even if message is not in Baileys cache
const pollMessageCache = new Map();

/**
 * Check if group exists
 */
export async function findGroupByName(sock, groupName) {
  try {
    const groups = await sock.groupFetchAllParticipating();
    
    for (const groupId in groups) {
      const group = groups[groupId];
      if (group.subject === groupName) {
        return { id: groupId, ...group };
      }
    }
    
    return null;
  } catch (error) {
    logger.error({ error: error.message }, 'Error fetching groups');
    return null;
  }
}

/**
 * Create "Minimee TEAM" group
 */
export async function createMinimeeTeamGroup(sock) {
  try {
    // Check if group already exists
    const existingGroup = await findGroupByName(sock, GROUP_NAME);
    
    if (existingGroup) {
      logGroupOperation('exists', existingGroup.id, {
        name: GROUP_NAME,
      });
      logger.info(`Group "${GROUP_NAME}" already exists`);
      return existingGroup;
    }

    // Format agent phones to JID format
    const participantJids = AGENT_PHONES.map(phone => {
      const cleaned = phone.replace(/[^0-9]/g, '');
      return `${cleaned}@s.whatsapp.net`;
    });

    // Create new group (Baileys v6 API)
    const groupId = await sock.groupCreate(GROUP_NAME, participantJids);
    
    logGroupOperation('created', groupId, {
      name: GROUP_NAME,
      participants: participantJids.length,
    });
    
    logger.info(`Created group "${GROUP_NAME}" with ID: ${groupId}`);
    
    return { id: groupId, subject: GROUP_NAME };
  } catch (error) {
    logger.error({ error: error.message }, 'Error creating group');
    throw error;
  }
}

/**
 * Add participants to group
 */
export async function addParticipantsToGroup(sock, groupId, participants) {
  try {
    if (!participants || participants.length === 0) {
      logger.info('No participants to add');
      return;
    }

    await sock.groupParticipantsUpdate(groupId, participants, 'add');
    
    logGroupOperation('participants_added', groupId, {
      count: participants.length,
    });
    
    logger.info(`Added ${participants.length} participant(s) to group ${groupId}`);
  } catch (error) {
    logger.error({ error: error.message }, 'Error adding participants');
    throw error;
  }
}

/**
 * Initialize Minimee TEAM group on connection
 * @param {Object} sock - Baileys socket
 * @param {string} userPhoneJid - Optional: User phone JID to add to group (for Minimee account)
 */
export async function initializeMinimeeTeam(sock, userPhoneJid = null) {
  try {
    logger.info('Initializing Minimee TEAM group...');
    
    let group = await findGroupByName(sock, GROUP_NAME);
    
    if (!group) {
      group = await createMinimeeTeamGroup(sock);
    }
    
    // Get current participants
    const groupInfo = await sock.groupMetadata(group.id);
    const currentParticipantIds = groupInfo.participants.map(p => {
      if (typeof p === 'string') return p;
      if (typeof p === 'object' && p.id) return p.id;
      return String(p);
    });
    
    const participantsToAdd = [];
    
    // Add User phone if provided (for Minimee account initialization)
    if (userPhoneJid && !currentParticipantIds.includes(userPhoneJid)) {
      participantsToAdd.push(userPhoneJid);
      logger.info(`Adding User (${userPhoneJid}) to Minimee TEAM group`);
    }
    
    // Add agent phones if configured
    if (AGENT_PHONES.length > 0) {
      const missingParticipants = AGENT_PHONES
        .map(phone => {
          const cleaned = phone.replace(/[^0-9]/g, '');
          return `${cleaned}@s.whatsapp.net`;
        })
        .filter(jid => !currentParticipantIds.includes(jid) && !participantsToAdd.includes(jid));
      
      participantsToAdd.push(...missingParticipants);
    }
    
    if (participantsToAdd.length > 0) {
      await addParticipantsToGroup(sock, group.id, participantsToAdd);
    } else {
      logger.info('All required participants already in group');
    }
    
    logger.info(`Minimee TEAM group ready: ${group.id}`);
    return group;
  } catch (error) {
    logger.error({ error: error.message }, 'Error initializing Minimee TEAM');
    throw error;
  }
}

/**
 * Send approval request message to Minimee TEAM group
 * Note: Cannot use polls in LID groups (votes can't be decrypted)
 * Using interactive buttons instead
 */
export async function sendApprovalMessageToGroup(sock, approvalData) {
  try {
    const { message_text, options, message_id, approval_id } = approvalData;
    
    // Find Minimee TEAM group
    const group = await findGroupByName(sock, GROUP_NAME);
    if (!group) {
      throw new Error(`Group "${GROUP_NAME}" not found. Please ensure it's initialized.`);
    }
    
    const groupId = group.id;
    
    // Check if group uses LID (Lightweight ID) - if so, use buttons instead of polls
    // LID groups are identified by participants containing "@lid"
    let isLidGroup = false;
    try {
      const groupMetadata = await sock.groupMetadata(groupId);
      if (groupMetadata.participants && groupMetadata.participants.length > 0) {
        // Check if any participant uses LID format
        isLidGroup = groupMetadata.participants.some(p => {
          const participantId = typeof p === 'string' ? p : p.id || String(p);
          return participantId.includes('@lid');
        });
      }
    } catch (e) {
      logger.debug({ error: e.message }, 'Could not check if group is LID');
    }
    
    // Use buttons for LID groups (poll votes can't be decrypted)
    if (isLidGroup) {
      try {
        const buttons = [
          { buttonId: `approve_${approval_id}_A`, buttonText: { displayText: `A) ${options.A?.substring(0, 20) || 'Option A'}` }, type: 1 },
          { buttonId: `approve_${approval_id}_B`, buttonText: { displayText: `B) ${options.B?.substring(0, 20) || 'Option B'}` }, type: 1 },
          { buttonId: `approve_${approval_id}_C`, buttonText: { displayText: `C) ${options.C?.substring(0, 20) || 'Option C'}` }, type: 1 },
          { buttonId: `approve_${approval_id}_NO`, buttonText: { displayText: 'No) Ne pas répondre' }, type: 1 },
        ];
        
        const buttonMessage = {
          text: message_text,
          buttons: buttons,
          headerType: 1,
        };
        
        const sent = await sock.sendMessage(groupId, buttonMessage);
        const group_message_id = sent.key.id;
        
        logger.info({
          message_id,
          approval_id,
          group_message_id,
          method: 'buttons',
          reason: 'LID group - polls not supported',
        }, 'Approval request sent with buttons (LID group)');
        
        return { group_message_id, method: 'buttons', approval_id };
      } catch (buttonError) {
        logger.warn({ 
          error: buttonError.message,
          stack: buttonError.stack 
        }, 'Button message failed, falling back to text');
        
        const sent = await sock.sendMessage(groupId, { text: message_text });
        const group_message_id = sent.key.id;
        
        logger.info({
          message_id,
          approval_id,
          group_message_id,
          method: 'text',
        }, 'Approval request sent as text (fallback)');
        
        return { group_message_id, method: 'text', approval_id };
      }
    }
    
    // Use poll format for non-LID groups
    try {
      // Build poll values from options A, B, C
      // Note: We'll add "No) Ne pas répondre" as a 4th option
      const pollValues = [
        `A) ${options.A || 'Option A'}`,
        `B) ${options.B || 'Option B'}`,
        `C) ${options.C || 'Option C'}`,
        'No) Ne pas répondre',
      ];
      
      // Create poll message
      // The poll message ID will be stored as group_message_id in PendingApproval
      // So we can retrieve approval info later using getPendingApprovalByGroupMessageId
      const pollMessage = {
        poll: {
          name: message_text,
          values: pollValues,
          selectableCount: 1, // Single choice only
        }
      };
      
      const sent = await sock.sendMessage(groupId, pollMessage);
      const group_message_id = sent.key.id;
      
      // Store the poll message structure for later vote decryption
      // sent.message might not contain the full structure, so we construct it properly
      // The structure needed for getAggregateVotesInPollMessage is:
      // { message: { pollCreationMessage: { name, options: [{ optionName }], selectableOptionsCount } } }
      const fullPollMessage = {
        message: {
          pollCreationMessage: {
            name: message_text,
            options: pollValues.map((val) => ({ 
              optionName: val 
            })),
            selectableOptionsCount: 1,
          }
        },
        key: sent.key,
      };
      pollMessageCache.set(group_message_id, fullPollMessage);
      
      logger.info({
        pollMessageId: group_message_id,
        hasPollCreation: !!fullPollMessage.message.pollCreationMessage,
        optionsCount: fullPollMessage.message.pollCreationMessage.options.length,
      }, 'Poll message stored in cache for vote decryption');
      
      // Also try to load from store after a short delay (async, don't wait)
      // The store might have additional metadata needed for decryption
      setTimeout(async () => {
        try {
          if (sock.store && typeof sock.store.loadMessage === 'function') {
            const storedMessage = await sock.store.loadMessage(groupId, group_message_id);
            if (storedMessage && storedMessage.message && storedMessage.message.pollCreationMessage) {
              // Use the stored message if it has the pollCreationMessage
              pollMessageCache.set(group_message_id, storedMessage);
              logger.info({
                pollMessageId: group_message_id,
              }, 'Poll message loaded from store and cached (replacing constructed version)');
            }
          }
        } catch (error) {
          // Store might not have it yet, that's ok - we have the constructed version
          logger.debug({ error: error.message }, 'Could not load poll message from store yet');
        }
      }, 2000);
      
      // Clean old entries (keep only last 100 polls)
      if (pollMessageCache.size > 100) {
        const firstKey = pollMessageCache.keys().next().value;
        pollMessageCache.delete(firstKey);
      }
      
      logger.info({
        message_id,
        approval_id,
        group_message_id,
        method: 'poll',
        pollValues: pollValues,
        cached: true,
      }, 'Approval request sent with poll (cached)');
      
      return { group_message_id, method: 'poll', approval_id };
    } catch (pollError) {
      // Fallback to plain text message if poll fails
      logger.warn({ 
        error: pollError.message,
        stack: pollError.stack 
      }, 'Poll message failed, falling back to text');
      
      const sent = await sock.sendMessage(groupId, { text: message_text });
      const group_message_id = sent.key.id;
      
      logger.info({
        message_id,
        approval_id,
        group_message_id,
        method: 'text',
      }, 'Approval request sent as text (fallback)');
      
      return { group_message_id, method: 'text', approval_id };
    }
  } catch (error) {
    logger.error({ error: error.message, message_id, approval_id }, 'Error sending approval message to group');
    throw error;
  }
}

/**
 * Get poll message from cache by message ID
 */
export function getPollMessageFromCache(pollMessageId) {
  return pollMessageCache.get(pollMessageId) || null;
}

