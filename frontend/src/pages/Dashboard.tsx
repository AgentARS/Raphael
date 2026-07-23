import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { Task, Idea, CalendarEvent } from '../api/client';
import { TaskCard } from '../components/TaskCard';
import { IdeaCard } from '../components/IdeaCard';
import { useEventLogger } from '../hooks/useEventLogger';
import './Dashboard.css';

export function Dashboard() {
  const { logEvent } = useEventLogger();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [fetchedTasks, fetchedIdeas, fetchedEvents] = await Promise.all([
          api.getTasks(),
          api.getIdeas(),
          api.getCalendarEvents()
        ]);
        
        setTasks(fetchedTasks);
        setIdeas(fetchedIdeas);
        setCalendarEvents(fetchedEvents);
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadDashboard();

    // Background sync
    api.syncTasks().then((res) => {
      if (res.synced > 0) {
        api.getTasks().then(setTasks);
      }
    }).catch(err => console.error("Sync failed:", err));
  }, []);

  const handleDeleteTask = async (taskId: string) => {
    setTasks(prev => prev.filter(t => t.id !== taskId));
  };

  const handleUpdateTask = (updatedTask: Task) => {
    setTasks(prev => prev.map(t => {
      if (t.id === updatedTask.id) {
        if (t.status !== updatedTask.status) {
          logEvent({
            eventType: updatedTask.status === 'done' ? 'task_completed' : 'task_reopened',
            objectType: 'task',
            objectId: updatedTask.id
          });
        }
        return updatedTask;
      }
      return t;
    }));
  };

  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [newTaskDesc, setNewTaskDesc] = useState('');
  const [newTaskDate, setNewTaskDate] = useState('');

  const handleCreateTask = async () => {
    if (!newTaskDesc.trim()) return;
    
    try {
      const created = await api.createTask({
        description: newTaskDesc,
        due_date: newTaskDate || undefined
      });
      logEvent({
        eventType: 'task_created',
        objectType: 'task',
        objectId: created.id
      });
      setTasks(prev => [created, ...prev]);
      setIsCreatingTask(false);
      setNewTaskDesc('');
      setNewTaskDate('');
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  };

  const handleDeleteIdea = async (ideaId: string) => {
    setIdeas(prev => prev.filter(i => i.id !== ideaId));
  };

  const handleUpdateIdea = (updatedIdea: Idea) => {
    setIdeas(prev => prev.map(i => i.id === updatedIdea.id ? updatedIdea : i));
  };

  const [isCreatingIdea, setIsCreatingIdea] = useState(false);
  const [newIdeaDesc, setNewIdeaDesc] = useState('');

  const handleCreateIdea = async () => {
    if (!newIdeaDesc.trim()) return;
    
    try {
      const created = await api.createIdea({
        description: newIdeaDesc
      });
      setIdeas(prev => [created, ...prev]);
      setIsCreatingIdea(false);
      setNewIdeaDesc('');
    } catch (err) {
      console.error("Failed to create idea:", err);
    }
  };

  if (isLoading) {
    return <div className="dashboard-loading">Loading insights...</div>;
  }

  const pendingTasks = tasks.filter(t => t.status !== 'done');
  const completedTasks = tasks.filter(t => t.status === 'done');

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p className="subtitle">Your extracted knowledge and action items.</p>
      </div>

      <div className="dashboard-grid">
        <section className="dashboard-section tasks-section">
          <div className="section-header-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>
              <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
              Action Items
            </h2>
            <button className="new-task-btn" onClick={() => setIsCreatingTask(true)} style={{ background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', padding: 'var(--space-1) var(--space-3)', fontSize: '0.85rem', cursor: 'pointer' }}>
              + New Task
            </button>
          </div>
          
          <div className="task-list">
            {isCreatingTask && (
              <div className="task-card" style={{ padding: 'var(--space-3)' }}>
                <div className="task-edit-form">
                  <input 
                    type="text" 
                    value={newTaskDesc} 
                    onChange={(e) => setNewTaskDesc(e.target.value)} 
                    placeholder="What needs to be done?"
                    className="task-edit-input"
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateTask()}
                  />
                  <div className="task-edit-actions">
                    <input 
                      type="date" 
                      value={newTaskDate} 
                      onChange={(e) => setNewTaskDate(e.target.value)} 
                      className="task-edit-date"
                    />
                    <button className="task-save-btn" onClick={handleCreateTask}>Add</button>
                    <button className="task-cancel-btn" onClick={() => setIsCreatingTask(false)}>Cancel</button>
                  </div>
                </div>
              </div>
            )}
            {!isCreatingTask && pendingTasks.length === 0 && <p className="empty-state">No pending tasks found.</p>}
            {pendingTasks.map(task => (
              <TaskCard 
                key={task.id} 
                task={task} 
                onUpdate={handleUpdateTask} 
                onDelete={handleDeleteTask} 
              />
            ))}
          </div>

          {completedTasks.length > 0 && (
            <div className="completed-tasks">
              <h3>Completed</h3>
              <div className="task-list">
                {completedTasks.map(task => (
                  <TaskCard 
                    key={task.id} 
                    task={task} 
                    onUpdate={handleUpdateTask} 
                    onDelete={handleDeleteTask} 
                  />
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="dashboard-section calendar-section">
          <h2>
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
            Upcoming
          </h2>
          <div className="calendar-list">
            {calendarEvents.length === 0 && <p className="empty-state">No upcoming events found.</p>}
            {calendarEvents.map(event => {
              const isAllDay = !event.start_time.includes('T');
              const startDate = new Date(event.start_time);
              
              const today = new Date();
              const tomorrow = new Date(today);
              tomorrow.setDate(tomorrow.getDate() + 1);
              
              const isToday = startDate.getDate() === today.getDate() && startDate.getMonth() === today.getMonth() && startDate.getFullYear() === today.getFullYear();
              const isTomorrow = startDate.getDate() === tomorrow.getDate() && startDate.getMonth() === tomorrow.getMonth() && startDate.getFullYear() === tomorrow.getFullYear();
              
              let dayIndicator = "";
              if (isToday) dayIndicator = "Today";
              else if (isTomorrow) dayIndicator = "Tomorrow";
              else dayIndicator = startDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
              
              return (
                <div key={event.id} className="calendar-card">
                  <div className="calendar-time">
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '2px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{dayIndicator}</div>
                    <div>{isAllDay ? 'All Day' : startDate.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</div>
                  </div>
                  <div className="calendar-details">
                    <div className="calendar-summary">
                      <a href={event.html_link} target="_blank" rel="noopener noreferrer">{event.summary}</a>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="dashboard-section decisions-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ margin: 0 }}>
              <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
              Recent Ideas
            </h2>
            <button className="add-task-btn" onClick={() => setIsCreatingIdea(true)}>
              + Add Idea
            </button>
          </div>
          
          <div className="task-list">
            {isCreatingIdea && (
              <div className="task-card">
                <div style={{ width: '12px' }}></div>
                <div className="task-edit-form" style={{ width: '100%' }}>
                  <input 
                    type="text" 
                    value={newIdeaDesc} 
                    onChange={(e) => setNewIdeaDesc(e.target.value)} 
                    placeholder="What's your idea?"
                    className="task-edit-input"
                    autoFocus
                  />
                  <div className="task-edit-actions">
                    <button className="task-save-btn" onClick={handleCreateIdea}>Add</button>
                    <button className="task-cancel-btn" onClick={() => setIsCreatingIdea(false)}>Cancel</button>
                  </div>
                </div>
              </div>
            )}
            {!isCreatingIdea && ideas.length === 0 && <p className="empty-state">No ideas recorded yet.</p>}
            {ideas.map(idea => (
              <IdeaCard 
                key={idea.id} 
                idea={idea} 
                onUpdate={handleUpdateIdea} 
                onDelete={handleDeleteIdea} 
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
