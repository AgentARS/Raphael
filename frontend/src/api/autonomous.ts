const API_BASE = 'http://localhost:8000/api/autonomous';

export interface AutonomousStatus {
  mode: 'manual' | 'autonomous';
  is_running: boolean;
  current_task: string | null;
  pending_tasks: number;
  next_wake: string | null;
  last_maintenance: string | null;
  cpu_max: string;
  ram_max: string;
}

export const autonomousApi = {
  async getStatus(): Promise<AutonomousStatus> {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error('Failed to fetch status');
    return res.json();
  },

  async setMode(mode: 'manual' | 'autonomous'): Promise<void> {
    const res = await fetch(`${API_BASE}/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    if (!res.ok) throw new Error('Failed to set mode');
  },

  async runNow(): Promise<void> {
    const res = await fetch(`${API_BASE}/run-now`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to run maintenance');
  },

  async pause(): Promise<void> {
    const res = await fetch(`${API_BASE}/pause`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to pause maintenance');
  }
};
