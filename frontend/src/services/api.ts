import {
  User,
  Conversation,
  Message,
  ApprovalRequest,
  AuditLogEntry,
  IntegrationStatusResponse,
  RunEvent
} from '../types';

const API_BASE = typeof window !== 'undefined' && window.location.port === '5173' ? 'http://localhost:8000' : '';

class ApiService {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('auth_token');
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  getToken(): string | null {
    return this.token;
  }

  private getHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...extraHeaders
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  // --- Auth Endpoints ---
  async listDemoUsers(): Promise<User[]> {
    const res = await fetch(`${API_BASE}/api/auth/users`);
    if (!res.ok) throw new Error('Failed to load demo identities');
    return res.json();
  }

  async login(email: string): Promise<{ access_token: string; user: User }> {
    const res = await fetch(`${API_BASE}/api/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Authentication failed');
    }
    const data = await res.json();
    this.setToken(data.access_token);
    return data;
  }

  async getCurrentUser(): Promise<User> {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error('Failed to get current user');
    return res.json();
  }

  // --- Conversations ---
  async listConversations(): Promise<Conversation[]> {
    const res = await fetch(`${API_BASE}/api/conversations`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error('Failed to list conversations');
    return res.json();
  }

  async createConversation(title?: string): Promise<Conversation> {
    const res = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ title: title || 'New Requisition' })
    });
    if (!res.ok) throw new Error('Failed to create conversation');
    return res.json();
  }

  async getConversation(id: string): Promise<{ conversation: Conversation; messages: Message[] }> {
    const res = await fetch(`${API_BASE}/api/conversations/${id}`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch conversation');
    return res.json();
  }

  // --- SSE Streaming Agent Run ---
  async streamRun(
    conversationId: string,
    content: string,
    onEvent: (event: RunEvent) => void,
    onError: (err: string) => void,
    onComplete: () => void
  ) {
    try {
      const response = await fetch(`${API_BASE}/api/runs`, {
        method: 'POST',
        headers: this.getHeaders({
          'Accept': 'text/event-stream'
        }),
        body: JSON.stringify({
          conversation_id: conversationId,
          content
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Run failed' }));
        throw new Error(errorData.detail || `Server returned ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Failed to initialize stream reader');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const block of parts) {
          if (!block.trim()) continue;
          let eventData = '';

          const lines = block.split('\n');
          for (const line of lines) {
            if (line.startsWith('data:')) {
              eventData += line.substring(5).trim();
            }
          }

          if (eventData) {
            try {
              const parsed: RunEvent = JSON.parse(eventData);
              onEvent(parsed);
              if (parsed.event_type === 'stream_end') {
                onComplete();
              }
            } catch (err) {
              console.warn('Failed to parse SSE JSON:', eventData, err);
            }
          }
        }
      }
      onComplete();
    } catch (e: any) {
      onError(e.message || 'Stream connection error');
    }
  }

  // --- Approvals ---
  async listPendingApprovals(): Promise<ApprovalRequest[]> {
    const res = await fetch(`${API_BASE}/api/approvals`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error('Failed to list approvals');
    return res.json();
  }

  async decideApproval(
    approvalId: string,
    decision: 'APPROVE' | 'REJECT',
    reason: string
  ): Promise<any> {
    const res = await fetch(`${API_BASE}/api/approvals/${approvalId}/decision`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ decision, reason })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Approval decision failed' }));
      throw new Error(err.detail || 'Approval decision rejected');
    }
    return res.json();
  }

  // --- Governance & Documents ---
  async listDocuments(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/api/documents`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  }

  // --- Integrations & Audit ---
  async getIntegrationStatus(): Promise<IntegrationStatusResponse> {
    const res = await fetch(`${API_BASE}/api/integrations/status`);
    if (!res.ok) throw new Error('Failed to fetch integration status');
    return res.json();
  }

  async getAuditLogs(): Promise<AuditLogEntry[]> {
    const res = await fetch(`${API_BASE}/api/audit/logs`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch audit trail');
    return res.json();
  }
}

export const api = new ApiService();
