/**
 * Shared types for Minimee
 */

export interface Message {
  id: string;
  content: string;
  sender: string;
  timestamp: Date;
  source: 'whatsapp' | 'gmail';
  conversationId: string;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  prompt: string;
  style: string;
  enabled: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface Conversation {
  id: string;
  participants: string[];
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface Embedding {
  id: string;
  text: string;
  vector: number[];
  metadata: Record<string, unknown>;
  createdAt: Date;
}

export interface LLMResponse {
  content: string;
  reasoning?: string;
  confidence?: number;
}

export type LLMProvider = 'ollama' | 'vllm' | 'openai';

export interface LLMConfig {
  provider: LLMProvider;
  model: string;
  temperature?: number;
  maxTokens?: number;
}

