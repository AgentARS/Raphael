const API_BASE = 'http://localhost:8000/api/briefing';

export interface BriefingItem {
  content: string;
  explanation?: string;
  evidence?: any[];
}

export interface BriefingSection {
  title: string;
  items: BriefingItem[];
}

export interface DailyBriefing {
  date: string;
  status: 'generating' | 'ready';
  last_updated?: string;
  overview: BriefingSection;
  current_state: BriefingSection;
  needs_attention: BriefingSection;
  suggested_plan: BriefingSection;
  open_loops: BriefingSection;
  insight: BriefingSection;
  upcoming: BriefingSection;
}

export const briefingApi = {
  async getToday(): Promise<DailyBriefing> {
    const res = await fetch(`${API_BASE}/today`);
    if (!res.ok) throw new Error('Failed to fetch briefing');
    return res.json();
  },
  
  async regenerate(): Promise<void> {
    const res = await fetch(`${API_BASE}/generate`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to regenerate briefing');
  },

  async updateItem(date: string, sectionKey: string, itemIndex: number, action: 'KEEP' | 'EDIT' | 'DELETE', newContent?: string): Promise<void> {
    const res = await fetch(`${API_BASE}/update_item`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, section_key: sectionKey, item_index: itemIndex, action, new_content: newContent })
    });
    if (!res.ok) throw new Error('Failed to update briefing item');
  }
};
