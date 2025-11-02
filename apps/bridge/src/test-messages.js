/**
 * Test message sending methods for WhatsApp
 * Different formats to test: buttons, interactive, template, poll
 */
import { logger } from './logger.js';

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
 * Test message with buttons format (current format)
 */
export async function sendTestButtons(sock, recipientJid) {
  const testMessage = `[🧪 Test] Message avec boutons classiques

Ceci est un test des boutons interactifs.

Choisissez une option:`;

  const buttons = [
    { 
      buttonId: `test_A`, 
      buttonText: { displayText: 'A) Option A - Test réussi' }, 
      type: 1 
    },
    { 
      buttonId: `test_B`, 
      buttonText: { displayText: 'B) Option B - Test OK' }, 
      type: 1 
    },
    { 
      buttonId: `test_C`, 
      buttonText: { displayText: 'C) Option C - Test validé' }, 
      type: 1 
    },
    { 
      buttonId: `test_NO`, 
      buttonText: { displayText: 'No) Ne pas répondre' }, 
      type: 1 
    },
  ];

  const buttonMessage = {
    text: testMessage,
    buttons: buttons,
    headerType: 1,
  };

  const sent = await sock.sendMessage(recipientJid, buttonMessage);
  return { 
    group_message_id: sent.key.id, 
    format: 'buttons',
    method: 'buttons'
  };
}

/**
 * Test message with interactive format (alternative Baileys format)
 */
export async function sendTestInteractive(sock, recipientJid) {
  const testMessage = `[🧪 Test] Message interactif

Ceci est un test du format interactive de Baileys.

Choisissez une option:`;

  const interactiveMessage = {
    interactive: {
      body: { text: testMessage },
      action: {
        buttons: [
          { 
            type: 'reply', 
            reply: { 
              id: 'test_A', 
              title: 'A) Option A' 
            } 
          },
          { 
            type: 'reply', 
            reply: { 
              id: 'test_B', 
              title: 'B) Option B' 
            } 
          },
          { 
            type: 'reply', 
            reply: { 
              id: 'test_C', 
              title: 'C) Option C' 
            } 
          },
          { 
            type: 'reply', 
            reply: { 
              id: 'test_NO', 
              title: 'No) Ne pas répondre' 
            } 
          },
        ]
      }
    }
  };

  const sent = await sock.sendMessage(recipientJid, interactiveMessage);
  return { 
    group_message_id: sent.key.id, 
    format: 'interactive',
    method: 'interactive'
  };
}

/**
 * Test message with template format (if supported)
 */
export async function sendTestTemplate(sock, recipientJid) {
  // Template format may not be fully supported in personal WhatsApp
  // This is a simplified version
  const testMessage = `[🧪 Test] Message template

Ceci est un test du format template.

Options:
A) Option A
B) Option B  
C) Option C
No) Ne pas répondre

Répondez: A, B, C ou No`;

  // For now, send as regular text since templates require business API
  const sent = await sock.sendMessage(recipientJid, { text: testMessage });
  return { 
    group_message_id: sent.key.id, 
    format: 'text (template non supporté en WhatsApp personnel)',
    method: 'template'
  };
}

/**
 * Test message with poll format (WhatsApp polls)
 */
export async function sendTestPoll(sock, recipientJid) {
  const pollMessage = {
    poll: {
      name: 'Test Multi-choix - Quelle option préférez-vous?',
      values: [
        'Option A - Test réussi',
        'Option B - Test OK',
        'Option C - Test validé',
      ],
      selectableCount: 1, // Single choice
    }
  };

  const sent = await sock.sendMessage(recipientJid, pollMessage);
  return { 
    group_message_id: sent.key.id, 
    format: 'poll',
    method: 'poll'
  };
}

/**
 * Main function to send test message based on method
 */
export async function sendTestMessage(sock, method, recipient) {
  const recipientJid = formatJID(recipient);
  
  logger.info({
    method,
    recipient: recipientJid,
  }, 'Sending test message');

  try {
    switch (method) {
      case 'buttons':
        return await sendTestButtons(sock, recipientJid);
      
      case 'interactive':
        return await sendTestInteractive(sock, recipientJid);
      
      case 'template':
        return await sendTestTemplate(sock, recipientJid);
      
      case 'poll':
        return await sendTestPoll(sock, recipientJid);
      
      default:
        throw new Error(`Unknown test method: ${method}`);
    }
  } catch (error) {
    logger.error({ 
      error: error.message,
      method,
      recipient: recipientJid,
    }, 'Error sending test message');
    throw error;
  }
}

