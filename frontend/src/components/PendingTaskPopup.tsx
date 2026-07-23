import { useState, useEffect } from 'react';
import { api } from '../api/client';
import './PendingTaskPopup.css';

interface PendingTaskUpdate {
  id: string;
  task_id: string;
  task_description: string;
  action: 'mark_done' | 'delete';
  source_entry_id: string | null;
  created_at: string;
}

export function PendingTaskPopup() {
  const [pendingUpdates, setPendingUpdates] = useState<PendingTaskUpdate[]>([]);

  useEffect(() => {
    // Poll for pending task updates every 5 seconds
    const interval = setInterval(async () => {
      try {
        const updates = await api.getPendingTaskUpdates();
        setPendingUpdates(updates);
      } catch (err) {
        console.error('Failed to fetch pending task updates:', err);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (id: string) => {
    try {
      await api.approvePendingTaskUpdate(id);
      setPendingUpdates(prev => prev.filter(u => u.id !== id));
    } catch (err) {
      console.error('Failed to approve update:', err);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await api.rejectPendingTaskUpdate(id);
      setPendingUpdates(prev => prev.filter(u => u.id !== id));
    } catch (err) {
      console.error('Failed to reject update:', err);
    }
  };

  if (pendingUpdates.length === 0) return null;

  return (
    <div className="pending-task-popup-container">
      {pendingUpdates.map(update => (
        <div key={update.id} className="pending-task-popup">
          <div className="popup-icon">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </div>
          <div className="popup-content">
            <p className="popup-title">
              AI suggests to <strong>{update.action === 'mark_done' ? 'complete' : 'delete'}</strong> a task based on your notes:
            </p>
            <p className="popup-task">"{update.task_description}"</p>
          </div>
          <div className="popup-actions">
            <button className="popup-btn approve" onClick={() => handleApprove(update.id)}>Approve</button>
            <button className="popup-btn reject" onClick={() => handleReject(update.id)}>Ignore</button>
          </div>
        </div>
      ))}
    </div>
  );
}
