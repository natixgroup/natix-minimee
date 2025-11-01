/**
 * API client for backend communication
 */
import { getEnv } from "./env";

const API_URL = getEnv().apiUrl;

export interface Agent {
  id: number;
  name: string;
  role: string;
  prompt: string;
  style: string | null;
  enabled: boolean;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface Setting {
  id: number;
  key: string;
  value: Record<string, any>;
  user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface Policy {
  id: number;
  name: string;
  rules: Record<string, any>;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface Log {
  id: number;
  level: string;
  message: string;
  metadata: Record<string, any> | null;
  service: string | null;
  timestamp: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP error! status: ${response.status}`,
      }));
      throw new Error(error.detail || "An error occurred");
    }

    return response.json();
  }

  // Health
  async getHealth() {
    return this.request<{ status: string }>("/health");
  }

  // Agents
  async getAgents(userId?: number) {
    const params = userId ? `?user_id=${userId}` : "";
    return this.request<Agent[]>(`/agents${params}`);
  }

  async getAgent(id: number) {
    return this.request<Agent>(`/agents/${id}`);
  }

  async createAgent(data: {
    name: string;
    role: string;
    prompt: string;
    style?: string;
    enabled?: boolean;
    user_id: number;
  }) {
    return this.request<Agent>("/agents", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateAgent(id: number, data: Partial<Agent>) {
    return this.request<Agent>(`/agents/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteAgent(id: number) {
    return this.request<{ message: string }>(`/agents/${id}`, {
      method: "DELETE",
    });
  }

  // Settings
  async getSettings(userId?: number) {
    const params = userId ? `?user_id=${userId}` : "";
    return this.request<Setting[]>(`/settings${params}`);
  }

  async getSetting(key: string, userId?: number) {
    const params = userId ? `?user_id=${userId}` : "";
    return this.request<Setting>(`/settings/${key}${params}`);
  }

  async createSetting(data: {
    key: string;
    value: Record<string, any>;
    user_id?: number;
  }) {
    return this.request<Setting>("/settings", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Policies
  async getPolicies(userId?: number) {
    const params = userId ? `?user_id=${userId}` : "";
    return this.request<Policy[]>(`/policy${params}`);
  }

  async createPolicy(data: {
    name: string;
    rules: Record<string, any>;
    user_id: number;
  }) {
    return this.request<Policy>("/policy", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updatePolicy(id: number, data: Partial<Policy>) {
    return this.request<Policy>(`/policy/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  // Logs
  async getLogs(params?: {
    level?: string;
    service?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          queryParams.append(key, String(value));
        }
      });
    }
    const query = queryParams.toString();
    return this.request<Log[]>(`/logs${query ? `?${query}` : ""}`);
  }

  // WhatsApp Upload
  async uploadWhatsApp(file: File, userId: number = 1) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", String(userId));

    const url = `${this.baseUrl}/ingest/whatsapp-upload`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP error! status: ${response.status}`,
      }));
      throw new Error(error.detail || "Upload failed");
    }

    return response.json();
  }

  // Gmail
  async startGmailOAuth(userId: number = 1) {
    return this.request<{ authorization_url: string; state: string }>(
      `/auth/gmail/start?user_id=${userId}`
    );
  }

  async fetchGmailThreads(
    days: number = 30,
    onlyReplied: boolean = true,
    userId: number = 1
  ) {
    return this.request<any[]>(
      `/gmail/fetch?days=${days}&only_replied=${onlyReplied}&user_id=${userId}`
    );
  }

  async checkGmailStatus(userId: number = 1) {
    return this.request<{ connected: boolean; has_token: boolean }>(
      `/gmail/status?user_id=${userId}`
    );
  }

  async handleGmailCallback(code: string, state: string, userId: number = 1) {
    return this.request<{ message: string; status: string }>(
      `/auth/gmail/callback?code=${code}&state=${state}&user_id=${userId}`
    );
  }

  // WhatsApp - Connect directly to bridge
  async getWhatsAppStatus() {
    // Bridge API runs on port 3003
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/status`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      status: data.status,
      running: true, // Bridge container is always running
      connected: data.connected,
      has_qr: data.has_qr,
    };
  }

  async getWhatsAppQR() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/qr`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      qr_available: data.qr_available,
      logs: data.qr_data || null, // Use QR image data directly
      qr_data: data.qr_data,
    };
  }

  async restartWhatsAppBridge() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/restart`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    return response.json();
  }

  async startWhatsAppBridge() {
    // Bridge is always running, just restart to get new QR
    return this.restartWhatsAppBridge();
  }

  // Model Status
  async getModelStatus() {
    return this.request<{
      available: boolean;
      provider: string;
      model?: string;
      error?: string;
      size?: string;
      modified?: string;
    }>("/llm/status");
  }

  // Minimee Message & Approval
  async processMessage(data: {
    content: string;
    sender: string;
    timestamp: string;
    conversation_id?: string;
    user_id: number;
    source?: string;
  }) {
    return this.request<{
      message_id: number;
      conversation_id?: string;
      options: string[];
    }>("/minimee/message", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async approveMessage(
    messageId: number,
    optionIndex: number,
    action: "yes" | "no" | "maybe" = "yes",
    type: "whatsapp_message" | "email_draft" = "whatsapp_message",
    emailThreadId?: string
  ) {
    return this.request<{ status: string; message: string; sent: boolean }>(
      "/minimee/approve",
      {
        method: "POST",
        body: JSON.stringify({
          message_id: messageId,
          option_index: optionIndex,
          action: action,
          type: type,
          email_thread_id: emailThreadId,
        }),
      }
    );
  }
}

export const api = new ApiClient(API_URL);

