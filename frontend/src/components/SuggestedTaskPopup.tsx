import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { Task } from '../api/client';
import './PendingTaskPopup.css';

export function SuggestedTaskPopup() {
  const [suggestedTasks, setSuggestedTasks] = useState<Task[]>([]);

  useEffect(() => {
    // Poll for suggested tasks every 5 seconds
    const interval = setInterval(async () => {
      try {
        const tasks = await api.getSuggestedTasks();
        setSuggestedTasks(tasks);
      } catch (err) {
        console.error('Failed to fetch suggested tasks:', err);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (task: Task) => {
    try {
      // Approving it changes the status to 'open' which triggers Google Tasks sync in backend
      await api.updateTaskStatus(task.id, 'open');
      setSuggestedTasks(prev => prev.filter(t => t.id !== task.id));
    } catch (err) {
      console.error('Failed to approve suggested task:', err);
    }
  };

  const handleReject = async (id: string) => {
    try {
      // Rejecting it simply deletes it from the database
      await api.deleteTask(id);
      setSuggestedTasks(prev => prev.filter(t => t.id !== id));
    } catch (err) {
      console.error('Failed to reject suggested task:', err);
    }
  };

  if (suggestedTasks.length === 0) return null;

  return (
    <div className="pending-task-popup-container" style={{ bottom: '20px', top: 'auto', left: '20px', right: 'auto', zIndex: 1000, position: 'fixed' }}>
      {suggestedTasks.map(task => (
        <div key={task.id} className="pending-task-popup">
          <div className="popup-icon" style={{ color: 'var(--accent-warning)' }}>
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
          </div>
          <div className="popup-content">
            <p className="popup-title">
              AI suggests adding a new action item to your tasks:
            </p>
            <p className="popup-task">"{task.description}"</p>
          </div>
          <div className="popup-actions">
            <button className="popup-btn approve" onClick={() => handleApprove(task)}>Add</button>
            <button className="popup-btn reject" onClick={() => handleReject(task.id)}>Ignore</button>
          </div>
        </div>
      ))}
    </div>
  );
}
