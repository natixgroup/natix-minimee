/**
 * Shared utility functions
 */

export function formatTimestamp(date: Date): string {
  return date.toISOString();
}

export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

