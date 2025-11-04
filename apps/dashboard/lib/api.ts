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

export interface ActionLog {
  id: number;
  action_type: string;
  duration_ms: number | null;
  model: string | null;
  input_data: Record<string, any> | null;
  output_data: Record<string, any> | null;
  metadata: Record<string, any> | null;
  message_id: number | null;
  conversation_id: string | null;
  request_id: string | null;
  user_id: number | null;
  source: string | null;
  status: string | null;
  error_message: string | null;
  timestamp: string;
}

export interface EmbeddingMessageInfo {
  id: number;
  content: string;
  sender: string;
  recipient: string | null;
  recipients: string[] | null;
  source: string;
  conversation_id: string | null;
  timestamp: string;
}

export interface Embedding {
  id: number;
  text: string;
  source: string | null;
  metadata: Record<string, any> | null;
  message_id: number | null;
  message: EmbeddingMessageInfo | null;
  created_at: string;
}

export interface EmbeddingsListResponse {
  embeddings: Embedding[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface UploadStats {
  messages_created: number;
  chunks_created: number;
  summaries_created: number;
  embeddings_created: number;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit & { timeout?: number }
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const timeout = options?.timeout || 10000; // Default 10s timeout (augmenté pour machines lentes)
    
    // Create AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...options?.headers,
        },
      });
      
      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: `HTTP error! status: ${response.status}`,
        }));
        throw new Error(error.detail || "An error occurred");
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(`Request timeout after ${timeout}ms`);
      }
      throw error;
    }
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

  // Logs metadata (available filters)
  async getLogsMetadata() {
    return this.request<{
      levels: string[];
      services: string[];
    }>("/logs/metadata");
  }

  // Logs
  async getLogs(params?: {
    level?: string;
    service?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
    order_by?: string;
    order_dir?: "asc" | "desc";
    group_by_request?: boolean;
  }) {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          queryParams.append(key, String(value));
        }
      });
    }
    const query = queryParams.toString();
    return this.request<{
      logs: Log[];
      total: number;
      page: number;
      limit: number;
      total_pages: number;
    }>(`/logs${query ? `?${query}` : ""}`);
  }

  // Action Logs
  async getActionLogs(params?: {
    action_type?: string;
    request_id?: string;
    message_id?: number;
    conversation_id?: string;
    user_id?: number;
    source?: string;
    status?: string;
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
    return this.request<ActionLog[]>(`/action-logs${query ? `?${query}` : ""}`);
  }

  // Stream Action Logs (SSE)
  subscribeActionLogs(
    onMessage: (log: ActionLog) => void,
    onError?: (error: Error) => void,
    filters?: {
      action_type?: string;
      request_id?: string;
      message_id?: number;
    }
  ) {
    const queryParams = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) {
          queryParams.append(key, String(value));
        }
      });
    }
    const query = queryParams.toString();
    const url = `${this.baseUrl}/logs/stream${query ? `?${query}` : ""}`;

    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as ActionLog;
        onMessage(log);
      } catch (error) {
        onError?.(error as Error);
      }
    };

    eventSource.onerror = (error) => {
      onError?.(new Error("EventSource failed"));
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
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

  // WhatsApp Upload with real-time progress (SSE + Upload progress)
  uploadWhatsAppWithProgress(
    file: File,
    userId: number = 1,
    onProgress: (update: {
      type: "upload" | "progress" | "complete" | "error";
      step?: string;
      data?: {
        step?: string;
        message?: string;
        current?: number;
        total?: number;
        embeddings_created?: number;
        percent?: number;
      };
      uploadPercent?: number;
      message?: string;
      conversation_id?: string;
      stats?: UploadStats;
      warnings?: string[];
    }) => void,
    onError?: (error: Error) => void
  ) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", String(userId));

    const url = `${this.baseUrl}/ingest/whatsapp-upload-stream`;
    
    // Use XMLHttpRequest to track upload progress and handle SSE response
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    
    // Track upload progress
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const uploadPercent = Math.round((event.loaded / event.total) * 100);
        onProgress({
          type: "upload",
          uploadPercent,
          data: {
            step: "uploading",
            message: `Uploading file... ${uploadPercent}%`,
            percent: uploadPercent,
          },
        });
      }
    });
    
    let receivedLength = 0;
    let buffer = "";
    
    // Handle streaming SSE response using readystatechange
    // readyState 3 (LOADING) means response is streaming in
    xhr.addEventListener("readystatechange", () => {
      if (xhr.readyState === 3 || xhr.readyState === 4) {
        // As response arrives, parse SSE events
        const newData = xhr.responseText.slice(receivedLength);
        receivedLength = xhr.responseText.length;
        
        if (newData) {
          buffer += newData;
          
          // Parse complete SSE lines
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                onProgress(data);
                
                if (data.type === "complete" || data.type === "error") {
                  return;
                }
              } catch (e) {
                // Ignore parse errors for heartbeat lines or incomplete data
              }
            }
          }
        }
      }
    });
    
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        // Process any remaining buffer
        const lines = buffer.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              onProgress(data);
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      } else {
        onError?.(new Error(`HTTP error! status: ${xhr.status}`));
      }
    });
    
    xhr.addEventListener("error", () => {
      onError?.(new Error("Upload failed"));
    });
    
    // Send request
    xhr.send(formData);
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
    // Legacy - uses user bridge
    return this.restartUserWhatsAppBridge();
  }

  // User WhatsApp methods
  async getUserWhatsAppStatus() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/user/status`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      status: data.status,
      running: true,
      connected: data.connected,
      has_qr: data.has_qr,
    };
  }

  async getUserWhatsAppQR() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/user/qr`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      qr_available: data.qr_available,
      logs: data.qr_data || null,
      qr_data: data.qr_data,
    };
  }

  async restartUserWhatsAppBridge() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/user/restart`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    return response.json();
  }

  // Minimee WhatsApp methods
  async getMinimeeWhatsAppStatus() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/minimee/status`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      status: data.status,
      running: true,
      connected: data.connected,
      has_qr: data.has_qr,
    };
  }

  async getMinimeeWhatsAppQR() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/minimee/qr`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      qr_available: data.qr_available,
      logs: data.qr_data || null,
      qr_data: data.qr_data,
    };
  }

  async restartMinimeeWhatsAppBridge() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/minimee/restart`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    return response.json();
  }

  // Get user WhatsApp account info (phone number and account type)
  async getUserWhatsAppInfo() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/user-info`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      phone: data.phone,
      account_type: data.account_type || 'standard',
      is_business: data.is_business || false,
    };
  }

  // Get Minimee WhatsApp account info (phone number and account type)
  async getMinimeeWhatsAppInfo() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/minimee/user-info`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return {
      phone: data.phone,
      account_type: data.account_type || 'standard',
      is_business: data.is_business || false,
    };
  }

  // WhatsApp Import History
  async getWhatsAppImportHistory(params?: {
    userId?: number;
    limit?: number;
    offset?: number;
  }) {
    const queryParams = new URLSearchParams();
    if (params?.userId) queryParams.append("user_id", String(params.userId));
    if (params?.limit) queryParams.append("limit", String(params.limit));
    if (params?.offset) queryParams.append("offset", String(params.offset));
    
    const query = queryParams.toString();
    return this.request<{
      items: Array<{
        conversation_id: string;
        messages_count: number;
        embeddings_count: number;
        chunks_count: number;
        summaries_count: number;
        first_import: string;
        last_import: string;
      }>;
      total: number;
      limit: number;
      offset: number;
      has_more: boolean;
    }>(`/ingest/whatsapp-history${query ? `?${query}` : ""}`);
  }

  async startWhatsAppBridge() {
    // Bridge is always running, just restart to get new QR
    return this.restartWhatsAppBridge();
  }

  // Get connected WhatsApp user phone number
  async getConnectedWhatsAppUser() {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/user-info`);
    if (!response.ok) {
      throw new Error(`Bridge API error: ${response.status}`);
    }
    const data = await response.json();
    return data.phone || data.user_id || null;
  }

  // Test WhatsApp message with different formats
  // Messages can be sent from User or Minimee account to either User WhatsApp or Minimee TEAM group
  async testWhatsAppMessage(
    method: string,
    sender: "user" | "minimee",
    destination: "user" | "group",
    userPhone?: string
  ) {
    const bridgeUrl = process.env.NEXT_PUBLIC_BRIDGE_URL || "http://localhost:3003";
    const response = await fetch(`${bridgeUrl}/bridge/test-message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        method,
        sender,
        destination,
        userPhone: destination === "user" ? userPhone : undefined,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        message: `HTTP error! status: ${response.status}`,
      }));
      throw new Error(error.message || "Test failed");
    }

    return response.json();
  }

  // OpenAI Configuration
  async validateOpenAIKey(apiKey: string) {
    // Validation can take up to 10s (API call to OpenAI + DB save), so use 12s timeout
    return this.request<{
      configured: boolean;
      valid: boolean;
      message: string;
      masked_key?: string;
    }>("/openai/validate", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey }),
      timeout: 12000, // 12 seconds for OpenAI API validation
    });
  }

  async getOpenAIStatus() {
    // Status check can take up to 5s for validation, use 8s timeout
    return this.request<{
      configured: boolean;
      valid: boolean;
      message: string;
      masked_key?: string;
    }>("/openai/status", {
      timeout: 8000, // 8 seconds for OpenAI API status check
    });
  }

  async deleteOpenAIKey() {
    return this.request<{ message: string }>("/openai/key", {
      method: "DELETE",
    });
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

  async getModels() {
    return this.request<{
      models: Array<{
        provider: string;
        model: string;
        parameters?: string;
        size?: string;
        context_length?: string;
        modified?: string;
        description?: string;
        available: boolean;
        error?: string;
        location_type?: "local" | "cloud";
        cost?: "free" | "paid";
        cost_info?: string;
      }>;
    }>("/llm/models");
  }

  async getEmbeddingModels() {
    return this.request<{
      models: Array<{
        model: string;
        dimensions: number;
        description: string;
        size?: string;
        available: boolean;
        use_case?: string;
        location_type?: "local" | "cloud";
        cost?: "free" | "paid";
      }>;
    }>("/embeddings/models");
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

  // Chat streaming
  async chatStream(
    content: string,
    userId: number,
    conversationId?: string,
    onToken?: (token: string) => void,
    onComplete?: (response: string, actions: any[], debugInfo?: any) => void,
    onError?: (error: Error) => void
  ) {
    try {
      const response = await fetch(`${this.baseUrl}/minimee/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content,
          user_id: userId,
          conversation_id: conversationId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === "token" && onToken) {
                onToken(data.token);
              } else if (data.type === "done") {
                if (onComplete) {
                  onComplete(data.response || "", data.actions || [], data.debug);
                }
                return;
              } else if (data.type === "error") {
                throw new Error(data.message || "Unknown error");
              }
            } catch (e) {
              // Skip malformed JSON
              if (e instanceof Error && e.message !== "Unexpected end of JSON input") {
                if (onError) {
                  onError(e);
                }
                return;
              }
            }
          }
        }
      }
    } catch (error) {
      if (onError) {
        onError(error instanceof Error ? error : new Error(String(error)));
      }
    }
  }

  // Get conversation messages
  async getConversationMessages(conversationId: string, userId: number = 1) {
    return this.request<Array<{
      id: number;
      content: string;
      sender: string;
      timestamp: string;
      source: string;
      conversation_id: string | null;
    }>>(`/minimee/conversations/${conversationId}/messages?user_id=${userId}`);
  }

  // Embeddings
  async getEmbeddings(params?: {
    source?: string;
    search?: string;
    message_start_date?: string;
    message_end_date?: string;
    embedding_start_date?: string;
    embedding_end_date?: string;
    page?: number;
    limit?: number;
  }) {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          queryParams.append(key, String(value));
        }
      });
    }
    const query = queryParams.toString();
    return this.request<EmbeddingsListResponse>(
      `/embeddings${query ? `?${query}` : ""}`
    );
  }

  async deleteEmbeddings(params?: {
    source?: string;
    search?: string;
    message_start_date?: string;
    message_end_date?: string;
    embedding_start_date?: string;
    embedding_end_date?: string;
  }) {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          queryParams.append(key, String(value));
        }
      });
    }
    const query = queryParams.toString();
    return this.request<{ deleted: number; message: string }>(
      `/embeddings${query ? `?${query}` : ""}`,
      {
        method: "DELETE",
      }
    );
  }
}

export const api = new ApiClient(API_URL);

