/**
 * Enhanced logging utility for WhatsApp Bridge
 */
import pino from 'pino';
import dotenv from 'dotenv';

dotenv.config();

const logLevel = process.env.LOG_LEVEL || 'info';

export const logger = pino({
  level: logLevel,
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
      translateTime: 'HH:MM:ss',
      ignore: 'pid,hostname',
    },
  },
});

/**
 * Log WhatsApp message interaction
 */
export function logMessage(type, message, metadata = {}) {
  logger.info({
    type: 'whatsapp_message',
    direction: type, // 'incoming' or 'outgoing'
    ...metadata,
  }, `WhatsApp message ${type}: ${message}`);
}

/**
 * Log group operation
 */
export function logGroupOperation(operation, groupId, metadata = {}) {
  logger.info({
    type: 'group_operation',
    operation,
    groupId,
    ...metadata,
  }, `Group ${operation}: ${groupId}`);
}

/**
 * Log connection event
 */
export function logConnection(event, metadata = {}) {
  logger.info({
    type: 'connection',
    event,
    ...metadata,
  }, `Connection ${event}`);
}

/**
 * Log webhook operation
 */
export function logWebhook(type, endpoint, metadata = {}) {
  logger.info({
    type: 'webhook',
    direction: type, // 'send' or 'receive'
    endpoint,
    ...metadata,
  }, `Webhook ${type} to ${endpoint}`);
}

