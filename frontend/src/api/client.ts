const API_BASE = 'http://localhost:8000/api';

export interface KnowledgeScores {
  relevance: number;
  significance: number;
  trend: number;
  explanation: string | null;
}

export interface Entity {
  id: string;
  type: string;
  name: string;
  confidence?: number;
  scores?: KnowledgeScores;
}

export interface Entry {
  id: string;
  content: string;
  created_at: string;
  updated_at: string | null;
  source_type: string;
  extraction_status: string;
  entities: Entity[];
  scores?: KnowledgeScores;
}

export interface Task {
  id: string;
  description: string;
  status: string;
  priority: string;
  assignee_id?: string;
  project_id?: string;
  project_name?: string;
  due_date: string | null;
  source_entry_id: string;
  confidence?: number;
  created_at: string;
  scores?: KnowledgeScores;
}

export interface Idea {
  id: string;
  description: string;
  project_id?: string;
  project_name?: string;
  source_entry_id?: string;
  confidence?: number;
  created_at: string;
  scores?: KnowledgeScores;
}

export interface SearchResult {
  entry: Entry;
  snippet: string | null;
  rank: number | null;
}

export interface EntityRelation {
  id: string;
  from_entity_id: string;
  to_entity_id: string;
  relationship: string;
  source_entry_id: string | null;
  confidence?: number;
  created_at: string;
}

export interface EntityGraph {
  entity: Entity;
  entries: Entry[];
  tasks: Task[];
  ideas: Idea[];
  relations: EntityRelation[];
}

export interface CalendarEvent {
  id: string;
  summary: string;
  description: string | null;
  start_time: string;
  end_time: string;
  html_link: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

class ApiClient {
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || 'Request failed');
    }
    if (res.status === 204) {
      return undefined as any;
    }
    return res.json();
  }

  async createEntry(data: { content: string; source_type?: string; context_project_id?: string }): Promise<Entry> {
    return this.request('/entries', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getEntries(limit = 50, offset = 0, entityId?: string, sourceType?: string): Promise<Entry[]> {
    let query = `?limit=${limit}&offset=${offset}`;
    if (entityId) query += `&entity_id=${entityId}`;
    if (sourceType && sourceType !== 'all') query += `&source_type=${sourceType}`;
    return this.request(`/entries${query}`);
  }

  async getEntities(type?: string): Promise<Entity[]> {
    const query = type ? `?type=${encodeURIComponent(type)}` : '';
    return this.request(`/entities${query}`);
  }

  async getNetworkGraph(): Promise<{ nodes: {id: string, name: string, type: string, confidence?: number}[], links: {source: string, target: string, label: string, weight: number, confidence?: number}[] }> {
    return this.request('/entities/network');
  }

  async createEntity(data: { name: string, type: string }): Promise<Entity> {
    return this.request('/entities', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getEntity(id: string): Promise<Entity> {
    return this.request(`/entities/${id}`);
  }

  async getEntry(id: string): Promise<Entry> {
    return this.request(`/entries/${id}`);
  }

  async updateEntry(id: string, data: { content: string }): Promise<Entry> {
    return this.request(`/entries/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteEntry(id: string): Promise<void> {
    await this.request(`/entries/${id}`, { method: 'DELETE' });
  }

  async search(query: string): Promise<SearchResult[]> {
    return this.request(`/search?q=${encodeURIComponent(query)}`);
  }

  async getTasks(projectId?: string): Promise<Task[]> {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.request(`/tasks${query}`);
  }

  async getSuggestedTasks(): Promise<Task[]> {
    return this.request('/tasks/suggested');
  }

  async updateTaskStatus(taskId: string, status: string): Promise<Task> {
    return this.request(`/tasks/${taskId}/status?status=${encodeURIComponent(status)}`, {
      method: 'PUT',
    });
  }

  async updateTask(taskId: string, updates: Partial<Task>): Promise<Task> {
    return this.request(`/tasks/${taskId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.request(`/tasks/${taskId}`, { method: 'DELETE' });
  }

  async syncTasks(): Promise<{ status: string, synced: number }> {
    return this.request('/tasks/sync', { method: 'POST' });
  }

  async createTask(data: { description: string, project_id?: string, due_date?: string }): Promise<Task> {
    return this.request('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getCalendarEvents(maxResults: number = 10): Promise<CalendarEvent[]> {
    return this.request(`/calendar/events?max_results=${maxResults}`);
  }

  async createCalendarEvent(data: { summary: string, start_time: string, end_time: string, description?: string, recurrence?: string[], color_id?: string }): Promise<CalendarEvent> {
    return this.request('/calendar/events', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCalendarEvent(eventId: string, data: { summary?: string, start_time?: string, end_time?: string, description?: string, recurrence?: string[], color_id?: string }): Promise<CalendarEvent> {
    return this.request(`/calendar/events/${eventId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteCalendarEvent(eventId: string): Promise<void> {
    await this.request(`/calendar/events/${eventId}`, { method: 'DELETE' });
  }

  async getPendingTaskUpdates(): Promise<any[]> {
    return this.request('/tasks/pending-updates');
  }

  async semanticTaskUpdate(data: { semantic_description: string, action: 'mark_done' | 'delete' }): Promise<void> {
    await this.request('/tasks/semantic-update', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async approvePendingTaskUpdate(id: string): Promise<void> {
    await this.request(`/tasks/pending-updates/${id}/approve`, { method: 'POST' });
  }

  async rejectPendingTaskUpdate(id: string): Promise<void> {
    await this.request(`/tasks/pending-updates/${id}/reject`, { method: 'DELETE' });
  }

  // --- Ideas ---

  async getIdeas(projectId?: string): Promise<Idea[]> {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.request(`/ideas${query}`);
  }

  async createIdea(data: { description: string, project_id?: string }): Promise<Idea> {
    return this.request('/ideas', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateIdea(id: string, updates: Partial<Idea>): Promise<Idea> {
    return this.request(`/ideas/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteIdea(id: string): Promise<void> {
    await this.request(`/ideas/${id}`, { method: 'DELETE' });
  }


  
  async reprocessEntry(id: string): Promise<Entry> {
    return this.request(`/entries/${id}/reprocess`, {
      method: 'POST'
    });
  }

  async updateEntity(id: string, updates: Partial<Entity>): Promise<Entity> {
    return this.request(`/entities/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  }

  async deleteEntity(id: string): Promise<void> {
    await this.request(`/entities/${id}`, { method: 'DELETE' });
  }

  async linkEntityToEntry(entryId: string, entityId: string): Promise<void> {
    await this.request(`/entries/${entryId}/entities/${entityId}`, { method: 'POST' });
  }

  async unlinkEntityFromEntry(entryId: string, entityId: string): Promise<void> {
    await this.request(`/entries/${entryId}/entities/${entityId}`, { method: 'DELETE' });
  }

  async getEntityGraph(id: string): Promise<EntityGraph> {
    return this.request(`/entities/${id}/graph`);
  }

  // Uses native fetch because it streams
  async *chatStream(messages: ChatMessage[], signal?: AbortSignal): AsyncGenerator<string, void, unknown> {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, stream: true }),
      signal
    });
    
    if (!res.ok) {
      throw new Error('Chat request failed');
    }
    
    if (!res.body) {
      throw new Error('Response body is null');
    }
    
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  }

  // --- Experience Engine (Logging) ---
  async logEvent(data: { event_type: string, object_type?: string, object_id?: string, session_id: string, metadata?: any, duration_ms?: number, source?: string }): Promise<void> {
    try {
      // "Fire and forget" pattern. We catch all errors so it never blocks the UI.
      await fetch(`${API_BASE}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...data,
          source: data.source || 'frontend'
        }),
      });
    } catch (e) {
      console.warn("Passive logging failed, swallowing error.", e);
    }
  }
}

export const api = new ApiClient();
