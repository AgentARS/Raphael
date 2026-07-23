import { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';
import type { Idea, Entity } from '../api/client';

interface IdeaCardProps {
  idea: Idea;
  onUpdate: (idea: Idea) => void;
  onDelete: (ideaId: string) => void;
}

export function IdeaCard({ idea, onUpdate, onDelete }: IdeaCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editDesc, setEditDesc] = useState(idea.description);
  
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
    const previousProjectId = idea.project_id;
    const previousProjectName = idea.project_name;
    onUpdate({ ...idea, project_id: project.id, project_name: project.name });
    
    try {
      await api.updateIdea(idea.id, { project_id: project.id });
    } catch (err) {
      console.error("Failed to link project", err);
      // Revert on failure
      onUpdate({ ...idea, project_id: previousProjectId, project_name: previousProjectName });
    }
  };

  const handleUnlinkProject = async () => {
    const previousProjectId = idea.project_id;
    const previousProjectName = idea.project_name;
    onUpdate({ ...idea, project_id: undefined, project_name: undefined });
    
    try {
      await api.updateIdea(idea.id, { project_id: null as any }); // null to clear it
    } catch (err) {
      console.error("Failed to unlink project", err);
      onUpdate({ ...idea, project_id: previousProjectId, project_name: previousProjectName });
    }
  };

  const handleSaveEdit = async () => {
    if (!editDesc.trim()) return;
    
    onUpdate({ ...idea, description: editDesc });
    setIsEditing(false);
    
    try {
      await api.updateIdea(idea.id, { description: editDesc });
    } catch (err) {
      console.error("Failed to update idea:", err);
    }
  };

  const handleDelete = async () => {
    onDelete(idea.id);
    try {
      await api.deleteIdea(idea.id);
    } catch (err) {
      console.error("Failed to delete idea:", err);
    }
  };

  return (
    <div className="task-card idea-card">
      <div style={{ width: '12px' }}></div>
      
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
            <button className="task-save-btn" onClick={handleSaveEdit}>Save</button>
            <button className="task-cancel-btn" onClick={() => setIsEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <>
          <div className="task-details">
            <span className="task-desc">{idea.description}</span>
            <div className="task-metadata-row" style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginTop: '4px' }}>
              
              {idea.project_id ? (
                <div className="project-pill" style={{ margin: 0, padding: '2px 8px', fontSize: '0.75rem' }}>
                  <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="2" fill="none" style={{ marginRight: '4px' }}>
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                  </svg>
                  {idea.project_name || 'Project'}
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
            <button className="task-action-btn" onClick={() => setIsEditing(true)} title="Edit idea">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
            <button className="task-action-btn delete" onClick={handleDelete} title="Delete idea">
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
