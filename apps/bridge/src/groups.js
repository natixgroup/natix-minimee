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
 */
export async function initializeMinimeeTeam(sock) {
  try {
    logger.info('Initializing Minimee TEAM group...');
    
    let group = await findGroupByName(sock, GROUP_NAME);
    
    if (!group) {
      group = await createMinimeeTeamGroup(sock);
    }
    
    // If there are agent phones configured and group exists, ensure they're added
    if (AGENT_PHONES.length > 0 && group) {
      // Get current participants
      const groupInfo = await sock.groupMetadata(group.id);
      const currentParticipantIds = groupInfo.participants.map(p => {
        if (typeof p === 'string') return p;
        if (typeof p === 'object' && p.id) return p.id;
        return String(p);
      });
      
      // Find missing participants
      const missingParticipants = AGENT_PHONES
        .map(phone => {
          const cleaned = phone.replace(/[^0-9]/g, '');
          return `${cleaned}@s.whatsapp.net`;
        })
        .filter(jid => !currentParticipantIds.includes(jid));
      
      if (missingParticipants.length > 0) {
        await addParticipantsToGroup(sock, group.id, missingParticipants);
      } else {
        logger.info('All agents already in group');
      }
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
 * Uses poll format (which works perfectly) instead of buttons
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
    
    // Use poll format for multi-choice approval requests
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
      
      logger.info({
        message_id,
        approval_id,
        group_message_id,
        method: 'poll',
        pollValues: pollValues,
      }, 'Approval request sent with poll');
      
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

