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
 * Tries to use interactive buttons, falls back to text if not supported
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
    
    // Try to send with interactive buttons (Baileys supports buttons)
    try {
      // Baileys button format: array of buttons with id and displayText
      const buttons = [
        { buttonId: `approve_${approval_id}_A`, buttonText: { displayText: 'A) Option A' }, type: 1 },
        { buttonId: `approve_${approval_id}_B`, buttonText: { displayText: 'B) Option B' }, type: 1 },
        { buttonId: `approve_${approval_id}_C`, buttonText: { displayText: 'C) Option C' }, type: 1 },
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
      }, 'Approval request sent with buttons');
      
      return { group_message_id, method: 'buttons' };
    } catch (buttonError) {
      // Fallback to plain text message
      logger.warn({ error: buttonError.message }, 'Button message failed, falling back to text');
      
      const sent = await sock.sendMessage(groupId, { text: message_text });
      const group_message_id = sent.key.id;
      
      logger.info({
        message_id,
        approval_id,
        group_message_id,
        method: 'text',
      }, 'Approval request sent as text (fallback)');
      
      return { group_message_id, method: 'text' };
    }
  } catch (error) {
    logger.error({ error: error.message, message_id, approval_id }, 'Error sending approval message to group');
    throw error;
  }
}

