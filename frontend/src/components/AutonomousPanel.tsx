import React, { useEffect, useState } from 'react';
import { autonomousApi } from '../api/autonomous';
import type { AutonomousStatus } from '../api/autonomous';
import './AutonomousPanel.css';

interface Props {
  onClose: () => void;
  status: AutonomousStatus | null;
  refreshStatus: () => void;
}

export function AutonomousPanel({ onClose, status, refreshStatus }: Props) {
  const [loading, setLoading] = useState(false);

  // Poll status while open
  useEffect(() => {
    const interval = setInterval(refreshStatus, 2000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  if (!status) return null;

  const handleRunNow = async () => {
    setLoading(true);
    await autonomousApi.runNow();
    await refreshStatus();
    setLoading(false);
  };

  const handlePause = async () => {
    setLoading(true);
    await autonomousApi.pause();
    await refreshStatus();
    setLoading(false);
  };

  return (
    <div className="autonomous-modal-overlay" onClick={onClose}>
      <div className="autonomous-modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Autonomous Execution System</h2>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="status-grid">
          <div className="status-item">
            <label>Mode</label>
            <span className={`status-badge ${status.mode}`}>{status.mode}</span>
          </div>
          <div className="status-item">
            <label>Status</label>
            <span className={`status-badge ${status.is_running ? 'running' : 'idle'}`}>
              {status.is_running ? 'Running' : 'Idle'}
            </span>
          </div>
          <div className="status-item">
            <label>Current Task</label>
            <span>{status.current_task || 'None'}</span>
          </div>
          <div className="status-item">
            <label>Pending Tasks</label>
            <span>{status.pending_tasks}</span>
          </div>
          <div className="status-item">
            <label>Next Wake</label>
            <span>{status.next_wake ? new Date(status.next_wake + 'Z').toLocaleString() : 'N/A'}</span>
          </div>
          <div className="status-item">
            <label>Last Maintenance</label>
            <span>{status.last_maintenance ? new Date(status.last_maintenance + 'Z').toLocaleString() : 'Never'}</span>
          </div>
          <div className="status-item">
            <label>Limits</label>
            <span className="limits-text">CPU: {status.cpu_max}% | RAM: {status.ram_max}%</span>
          </div>
        </div>

        <div className="modal-actions">
          <button 
            className="action-btn run-now" 
            onClick={handleRunNow} 
            disabled={loading || status.mode !== 'autonomous'}
          >
            Run Maintenance Now
          </button>
          <button 
            className="action-btn pause" 
            onClick={handlePause} 
            disabled={loading || status.mode === 'manual'}
          >
            Pause Processing
          </button>
        </div>
      </div>
    </div>
  );
}
