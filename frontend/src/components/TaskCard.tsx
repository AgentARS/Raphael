import { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';
import type { Task, Entity } from '../api/client';
import { formatDate } from '../utils/format';

interface TaskCardProps {
  task: Task;
  onUpdate: (task: Task) => void;
  onDelete: (taskId: string) => void;
  onClickInfo?: () => void;
}

export function TaskCard({ task, onUpdate, onDelete, onClickInfo }: TaskCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editDesc, setEditDesc] = useState(task.description);
  const [editDate, setEditDate] = useState(task.due_date || '');
  
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [availableProjects, setAvailableProjects] = useState<Entity[]>([]);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const openDropdown = async () => {
    setIsDropdownOpen(!isDropdownOpen);
    if (!isDropdownOpen && availableProjects.length === 0) {
      try {
        const [projects, pending] = await Promise.all([
          api.getEntities('project'),
          api.getEntities('pending_project')
        ]);
        setAvailableProjects([...projects, ...pending]);
      } catch (err) {
        console.error("Failed to load projects", err);
      }
    }
  };

  const handleLinkProject = async (project: Entity) => {
    setIsDropdownOpen(false);
    
    // Optimistic update
    const previousProjectId = task.project_id;
    const previousProjectName = task.project_name;
    onUpdate({ ...task, project_id: project.id, project_name: project.name });
    
    try {
      await api.updateTask(task.id, { project_id: project.id });
    } catch (err) {
      console.error("Failed to link project", err);
      // Revert on failure
      onUpdate({ ...task, project_id: previousProjectId, project_name: previousProjectName });
    }
  };

  const handleUnlinkProject = async () => {
    const previousProjectId = task.project_id;
    const previousProjectName = task.project_name;
    onUpdate({ ...task, project_id: undefined, project_name: undefined });
    
    try {
      await api.updateTask(task.id, { project_id: null as any }); // null to clear it
    } catch (err) {
      console.error("Failed to unlink project", err);
      onUpdate({ ...task, project_id: previousProjectId, project_name: previousProjectName });
    }
  };

  const toggleStatus = async () => {
    const newStatus = task.status === 'done' ? 'open' : 'done';
    onUpdate({ ...task, status: newStatus });
    try {
      await api.updateTaskStatus(task.id, newStatus);
    } catch (err) {
      console.error("Failed to toggle task", err);
      onUpdate({ ...task, status: task.status }); // revert
    }
  };

  const handleSaveEdit = async () => {
    if (!editDesc.trim()) return;
    
    const newDate = editDate || null;
    onUpdate({ ...task, description: editDesc, due_date: newDate });
    setIsEditing(false);
    
    try {
      await api.updateTask(task.id, { description: editDesc, due_date: newDate });
    } catch (err) {
      console.error("Failed to update task:", err);
    }
  };

  const handleDelete = async () => {
    onDelete(task.id);
    try {
      await api.deleteTask(task.id);
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  return (
    <div className={`task-card ${task.status === 'done' ? 'completed' : ''}`}>
      <button 
        className={`task-checkbox ${task.status === 'done' ? 'checked' : ''}`}
        onClick={toggleStatus}
      >
        {task.status === 'done' && <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="3" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg>}
      </button>
      
      {isEditing ? (
        <div className="task-edit-form">
          <input 
            type="text" 
            value={editDesc} 
            onChange={(e) => setEditDesc(e.target.value)} 
            className="task-edit-input"
            autoFocus
          />
          <div className="task-edit-actions">
            <input 
              type="date" 
              value={editDate} 
              onChange={(e) => setEditDate(e.target.value)} 
              className="task-edit-date"
            />
            <button className="task-save-btn" onClick={handleSaveEdit}>Save</button>
            <button className="task-cancel-btn" onClick={() => setIsEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <>
          <div className="task-details">
            <span className="task-desc">{task.description}</span>
            <div className="task-metadata-row" style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginTop: '4px' }}>
              {task.due_date && <span className="task-due">Due: {formatDate(task.due_date)}</span>}
              
              {task.project_id ? (
                <div className="project-pill" style={{ margin: 0, padding: '2px 8px', fontSize: '0.75rem' }}>
                  <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="2" fill="none" style={{ marginRight: '4px' }}>
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                  </svg>
                  {task.project_name || 'Project'}
                  <button 
                    className="project-pill-remove"
                    onClick={(e) => { e.stopPropagation(); handleUnlinkProject(); }}
                    title="Remove from project"
                  >
                    ×
                  </button>
                </div>
              ) : (
                <div className="entry-projects" style={{ marginTop: 0 }} ref={dropdownRef}>
                  <button className="add-project-btn" onClick={openDropdown} title="Assign to project" style={{ padding: '2px 6px', fontSize: '0.75rem' }}>
                    + Project
                  </button>
                  {isDropdownOpen && (
                    <div className="project-dropdown" style={{ top: '100%', left: 0 }}>
                      {availableProjects.length === 0 ? (
                        <div className="project-dropdown-empty">No projects found</div>
                      ) : (
                        availableProjects.map(proj => (
                          <div 
                            key={proj.id} 
                            className="project-dropdown-item"
                            onClick={() => handleLinkProject(proj)}
                          >
                            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none">
                              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                            </svg>
                            {proj.name}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          
          <div className="task-actions-group">
            {onClickInfo && (
              <button className="task-action-btn" onClick={onClickInfo} title="View details">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="16" x2="12" y2="12"></line>
                  <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
              </button>
            )}
            <button className="task-action-btn" onClick={() => setIsEditing(true)} title="Edit task">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
            <button className="task-action-btn delete" onClick={handleDelete} title="Delete task">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
