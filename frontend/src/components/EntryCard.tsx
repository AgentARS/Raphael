import { useState, useEffect, useRef } from 'react';
import { api, type Entry, type Entity } from '../api/client';
import './EntryCard.css';

interface EntryCardProps {
  entry: Entry;
  onDelete: (id: string) => void;
  onReprocess?: (id: string) => void;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (diffInSeconds < 60) return 'Just now';
  
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`;
  
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`;
  
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays === 1) return 'Yesterday';
  if (diffInDays < 7) return `${diffInDays} days ago`;
  
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function EntryCard({ entry, onDelete, onReprocess }: EntryCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = () => {
    if (confirmDelete) {
      onDelete(entry.id);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000); // Reset after 3 seconds
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'done': return 'var(--accent-success)';
      case 'failed': return 'var(--accent-danger)';
      default: return 'var(--accent-warning)';
    }
  };

  const dateObj = new Date(entry.created_at);
  const fullDate = dateObj.toLocaleString();

  // Local state for entities to allow optimistic updates
  const [localEntities, setLocalEntities] = useState<Entity[]>(entry.entities || []);
  
  // Project Assignment State
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [availableProjects, setAvailableProjects] = useState<Entity[]>([]);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Sync if parent updates
    setLocalEntities(entry.entities || []);
  }, [entry.entities]);

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
    // Prevent duplicates
    if (localEntities.find(e => e.id === project.id)) {
      setIsDropdownOpen(false);
      return;
    }
    setLocalEntities([...localEntities, project]);
    setIsDropdownOpen(false);
    try {
      await api.linkEntityToEntry(entry.id, project.id);
    } catch (err) {
      console.error("Failed to link project", err);
      setLocalEntities(localEntities.filter(e => e.id !== project.id)); // revert
    }
  };

  const handleUnlinkProject = async (projectId: string) => {
    const removed = localEntities.find(e => e.id === projectId);
    setLocalEntities(localEntities.filter(e => e.id !== projectId));
    try {
      await api.unlinkEntityFromEntry(entry.id, projectId);
    } catch (err) {
      console.error("Failed to unlink project", err);
      if (removed) setLocalEntities([...localEntities, removed]); // revert
    }
  };

  const projectEntities = localEntities.filter(e => e.type === 'project' || e.type === 'pending_project');
  const otherEntities = localEntities.filter(e => e.type !== 'project' && e.type !== 'pending_project');

  return (
    <div className="entry-card">
      <div className="entry-card-header">
        <span className="timestamp" title={fullDate}>
          {formatRelativeTime(entry.created_at)}
        </span>
        <div className="actions">
          <div 
            className="status-dot" 
            style={{ backgroundColor: getStatusColor(entry.extraction_status) }}
            title={`Extraction: ${entry.extraction_status}`}
          />
          <button 
            className={`delete-btn ${confirmDelete ? 'confirm' : ''}`}
            onClick={handleDelete}
            title={confirmDelete ? "Click again to delete" : "Delete entry"}
          >
            {confirmDelete ? (
              <span className="confirm-text">Confirm?</span>
            ) : (
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                <line x1="10" y1="11" x2="10" y2="17"></line>
                <line x1="14" y1="11" x2="14" y2="17"></line>
              </svg>
            )}
          </button>
          {onReprocess && (
            <button 
              className="reprocess-btn"
              onClick={() => onReprocess(entry.id)}
              title="Force Reprocess"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-9.21l5.67-1.12"></path>
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="entry-content">
        {entry.content}
      </div>
      
      <div className="entry-tags-container">
        {projectEntities.map(ent => (
          <div key={ent.id} className="project-pill">
            <span title={`Type: ${ent.type}`}>{ent.name}</span>
            <span 
              className="project-pill-remove"
              onClick={() => handleUnlinkProject(ent.id)}
              title="Remove from project"
            >
              ×
            </span>
          </div>
        ))}
        
        <div style={{ position: 'relative' }} ref={dropdownRef}>
          <button className="add-project-btn" onClick={openDropdown} title="Assign to project">
            + Project
          </button>
          
          {isDropdownOpen && (
            <div className="project-dropdown">
              {availableProjects.length === 0 ? (
                <div style={{ padding: '4px', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Loading...</div>
              ) : (
                availableProjects.map(proj => {
                  const isAssigned = localEntities.find(e => e.id === proj.id);
                  if (isAssigned) return null; // Don't show already assigned projects
                  return (
                    <button 
                      key={proj.id} 
                      className="project-dropdown-item"
                      onClick={() => handleLinkProject(proj)}
                    >
                      {proj.name}
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {otherEntities.length > 0 && (
        <div className="entry-entities">
          {otherEntities.map(ent => (
            <span key={ent.id} className={`entity-badge entity-${ent.type}`}>
              {ent.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
