const API_BASE = 'http://localhost:8000/api/discussions';

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface DiscussionContext {
  object_type: string;
  section?: string;
  content: string;
  evidence?: any[];
  date?: string;
  sectionKey?: string;
  itemIndex?: number;
}

export interface ChatRequest {
  context: DiscussionContext;
  messages: Message[];
}

export interface FinishResponse {
  summary: string;
  proposal_text: string;
  briefing_action: 'KEEP' | 'EDIT' | 'DELETE';
  new_content?: string;
}

export const discussionsApi = {
  async chat(request: ChatRequest): Promise<{ reply: string }> {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
    if (!res.ok) throw new Error('Failed to send chat message');
    return res.json();
  },

  async finish(request: ChatRequest): Promise<FinishResponse> {
    const res = await fetch(`${API_BASE}/finish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
    if (!res.ok) throw new Error('Failed to finish discussion');
    return res.json();
  }
};
