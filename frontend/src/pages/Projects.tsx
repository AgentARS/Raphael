import { useState, useEffect } from 'react';
import { api, type Entity, type Task, type Idea, type Entry } from '../api/client';
import { EntryCard } from '../components/EntryCard';
import { EntryCapture } from '../components/EntryCapture';
import { TaskCard } from '../components/TaskCard';
import { IdeaCard } from '../components/IdeaCard';
import DetailsPanel from '../components/DetailsPanel';
import './Projects.css';
import './Dashboard.css';

export function Projects() {
  const [projects, setProjects] = useState<Entity[]>([]);
  const [pendingProjects, setPendingProjects] = useState<Entity[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  
  const [tasks, setTasks] = useState<Task[]>([]);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [filterSource, setFilterSource] = useState('all');
  
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [newIdeaDesc, setNewIdeaDesc] = useState('');
  const [isCreatingIdea, setIsCreatingIdea] = useState(false);
  
  const [selectedPanelItem, setSelectedPanelItem] = useState<{
    title: string;
    type: string;
    scores?: any;
    metadata?: any[];
  } | null>(null);

  // Function to refresh projects globally
  const refreshProjects = async () => {
    try {
      const [projData, pendingData] = await Promise.all([
        api.getEntities('project'),
        api.getEntities('pending_project')
      ]);
      setProjects(projData);
      setPendingProjects(pendingData);
      return projData;
    } catch (err) {
      console.error("Failed to load projects:", err);
      return [];
    }
  };

  useEffect(() => {
    async function loadProjects() {
      setIsLoading(true);
      const projData = await refreshProjects();
      if (projData.length > 0) {
        setSelectedProjectId(projData[0].id);
      }
      setIsLoading(false);
    }
    loadProjects();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    
    async function loadProjectDetails() {
      setIsLoadingDetails(true);
      try {
        const [tasksData, ideasData] = await Promise.all([
          api.getTasks(selectedProjectId!),
          api.getIdeas(selectedProjectId!)
        ]);
        const entriesData = await api.getEntries(50, 0, selectedProjectId || undefined, filterSource);
        
        setTasks(tasksData);
        setIdeas(ideasData);
        setEntries(entriesData);
      } catch (err) {
        console.error("Failed to load project details:", err);
      } finally {
        setIsLoadingDetails(false);
      }
    }
    loadProjectDetails();

    // Background sync
    api.syncTasks().then((res) => {
      if (res.synced > 0) {
        api.getTasks(selectedProjectId!).then(setTasks);
      }
    }).catch(err => console.error("Sync failed:", err));
  }, [selectedProjectId, filterSource]);

  // Poll for updates if any entry is pending extraction
  useEffect(() => {
    if (!selectedProjectId) return;
    const hasPending = entries.some(e => e.extraction_status === 'pending');
    if (!hasPending) return;

    const intervalId = setInterval(async () => {
      try {
        const data = await api.getEntries(50, 0, selectedProjectId);
        setEntries(data);
      } catch (err) {
        console.error('Polling failed:', err);
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [entries, selectedProjectId]);

  // --- Task Management Logic (similar to Dashboard) ---
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [newTaskDesc, setNewTaskDesc] = useState('');
  const [newTaskDate, setNewTaskDate] = useState('');

  const handleCreateTask = async () => {
    if (!newTaskDesc.trim() || !selectedProjectId) return;
    try {
      const created = await api.createTask({
        description: newTaskDesc,
        project_id: selectedProjectId,
        due_date: newTaskDate || undefined
      });
      setTasks(prev => [created, ...prev]);
      setIsCreatingTask(false);
      setNewTaskDesc('');
      setNewTaskDate('');
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  };

  const handleUpdateTask = (updatedTask: Task) => {
    setTasks(prev => prev.map(t => t.id === updatedTask.id ? updatedTask : t));
  };

  const handleDeleteTask = async (taskId: string) => {
    setTasks(prev => prev.filter(t => t.id !== taskId));
    try {
      await api.deleteTask(taskId);
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  // --- Ideas Handlers ---
  const handleUpdateIdea = (updatedIdea: Idea) => {
    setIdeas(prev => prev.map(i => i.id === updatedIdea.id ? updatedIdea : i));
  };

  const handleCreateIdea = async () => {
    if (!newIdeaDesc.trim() || !selectedProjectId) return;
    try {
      const created = await api.createIdea({
        description: newIdeaDesc,
        project_id: selectedProjectId
      });
      setIdeas(prev => [created, ...prev]);
      setIsCreatingIdea(false);
      setNewIdeaDesc('');
    } catch (err) {
      console.error("Failed to create idea:", err);
    }
  };

  const handleDeleteIdea = async (ideaId: string) => {
    setIdeas(prev => prev.filter(d => d.id !== ideaId));
    try {
      await api.deleteIdea(ideaId);
    } catch (err) {
      console.error("Failed to delete idea:", err);
    }
  };

  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      const created = await api.createEntity({
        name: newProjectName,
        type: 'project'
      });
      setProjects(prev => {
        const updated = [...prev, created];
        updated.sort((a, b) => a.name.localeCompare(b.name));
        return updated;
      });
      setSelectedProjectId(created.id);
      setIsCreatingProject(false);
      setNewProjectName('');
    } catch (err) {
      console.error("Failed to create project:", err);
    }
  };

  // --- Note Management Logic ---
  const handleCaptureEntry = async (content: string) => {
    if (!selectedProjectId) return;
    try {
      const created = await api.createEntry({ 
        content, 
        source_type: 'manual', 
        context_project_id: selectedProjectId 
      });
      setEntries(prev => [created, ...prev]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteEntry = async (id: string) => {
    try {
      await api.deleteEntry(id);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (err) {
      console.error("Failed to delete entry:", err);
    }
  };

  const handleReprocessEntry = async (id: string) => {
    // Optimistic UI update for status
    setEntries(prev => prev.map(e => e.id === id ? { ...e, extraction_status: 'pending' } : e));
    try {
      await api.reprocessEntry(id);
    } catch (err) {
      console.error("Failed to reprocess entry:", err);
    }
  };

  // --- Project Edit / Delete Logic ---
  const [isEditingProject, setIsEditingProject] = useState(false);
  const [editProjectName, setEditProjectName] = useState('');

  const handleStartEditProject = () => {
    if (selectedProject) {
      setEditProjectName(selectedProject.name);
      setIsEditingProject(true);
    }
  };

  const handleUpdateProject = async () => {
    if (!selectedProjectId || !editProjectName.trim()) return;
    try {
      const updated = await api.updateEntity(selectedProjectId, { name: editProjectName });
      setProjects(prev => prev.map(p => p.id === selectedProjectId ? updated : p));
      setIsEditingProject(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteProject = async (id: string) => {
    try {
      await api.deleteEntity(id);
      setProjects(prev => prev.filter(p => p.id !== id));
      if (selectedProjectId === id) setSelectedProjectId(projects.find(p => p.id !== id)?.id || null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleApproveProject = async (id: string) => {
    try {
      const approved = await api.updateEntity(id, { type: 'project' });
      setPendingProjects(prev => prev.filter(p => p.id !== id));
      setProjects(prev => [...prev, approved]);
      setSelectedProjectId(id);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRejectProject = async (id: string) => {
    try {
      await api.deleteEntity(id);
      setPendingProjects(prev => prev.filter(p => p.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  if (isLoading) {
    return <div className="projects-container"><div className="projects-loading">Loading projects...</div></div>;
  }

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  return (
    <div className="projects-container">
      <div className="projects-sidebar">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
          <h2 className="projects-sidebar-title" style={{ marginBottom: 0 }}>My Projects</h2>
          <button onClick={() => setIsCreatingProject(true)} style={{ background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', padding: 'var(--space-1) var(--space-2)', fontSize: '0.75rem', cursor: 'pointer' }}>
            + New
          </button>
        </div>
        
        {isCreatingProject && (
          <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
            <input 
              type="text" 
              value={newProjectName} 
              onChange={e => setNewProjectName(e.target.value)} 
              placeholder="Project Name..."
              autoFocus
              onKeyDown={e => e.key === 'Enter' && handleCreateProject()}
              style={{ flex: 1, padding: 'var(--space-2)', fontSize: '0.85rem' }}
            />
            <button onClick={handleCreateProject} style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-2)', cursor: 'pointer', color: 'var(--text-primary)' }}>
              Save
            </button>
            <button onClick={() => setIsCreatingProject(false)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
              ×
            </button>
          </div>
        )}

        {pendingProjects.length > 0 && (
          <div className="pending-projects-section" style={{ marginBottom: 'var(--space-4)', paddingBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-default)' }}>
            <h3 style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>Pending Approvals</h3>
            <div className="projects-list">
              {pendingProjects.map(p => (
                <div key={p.id} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', background: 'var(--bg-tertiary)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                  <span style={{ fontWeight: 500, fontSize: '0.9rem' }}>{p.name}</span>
                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button onClick={() => handleApproveProject(p.id)} style={{ flex: 1, background: 'var(--accent-primary)', color: 'white', border: 'none', padding: 'var(--space-1) 0', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '0.8rem' }}>Approve</button>
                    <button onClick={() => handleRejectProject(p.id)} style={{ flex: 1, background: 'transparent', border: '1px solid var(--border-default)', color: 'var(--text-secondary)', padding: 'var(--space-1) 0', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '0.8rem' }}>Reject</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="projects-list">
          {projects.length === 0 ? (
            <p className="no-projects">No projects found yet. Let the AI extract some from your notes!</p>
          ) : (
            projects.map(p => (
              <button 
                key={p.id} 
                className={`project-list-item ${selectedProjectId === p.id ? 'active' : ''}`}
                onClick={() => setSelectedProjectId(p.id)}
              >
                <div className="project-list-icon">
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                  </svg>
                </div>
                <span className="project-list-name">{p.name}</span>
              </button>
            ))
          )}
        </div>
      </div>
      
      <div className="project-detail">
        {!selectedProject ? (
          <div className="no-project-selected">Select a project to view details</div>
        ) : isLoadingDetails ? (
          <div className="project-detail-loading">Loading project data...</div>
        ) : (
          <>
            <div className="project-detail-header">
              {isEditingProject ? (
                <div style={{ display: 'flex', gap: 'var(--space-3)', width: '100%', alignItems: 'center' }}>
                  <input 
                    type="text" 
                    value={editProjectName}
                    onChange={e => setEditProjectName(e.target.value)}
                    style={{ fontSize: '1.5rem', fontWeight: 600, padding: 'var(--space-2)', flex: 1 }}
                    autoFocus
                  />
                  <button onClick={handleUpdateProject} style={{ background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-4)', cursor: 'pointer' }}>Save</button>
                  <button onClick={() => setIsEditingProject(false)} style={{ background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-4)', cursor: 'pointer' }}>Cancel</button>
                </div>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                  <header className="project-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <h1 className="project-title">{selectedProject.name}</h1>
                    <button 
                      className="task-action-btn" 
                      onClick={() => setSelectedPanelItem({
                        title: selectedProject.name,
                        type: 'Project',
                        scores: undefined,
                        metadata: [
                          { label: 'Created At', value: new Date(selectedProject.created_at).toLocaleString() },
                          { label: 'Metadata', value: JSON.stringify(selectedProject.metadata) }
                        ]
                      })}
                      title="View Project Details"
                    >
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                      </svg>
                    </button>
                  </header>
                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button onClick={handleStartEditProject} style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-default)', padding: 'var(--space-2) var(--space-3)', borderRadius: 'var(--radius-md)', cursor: 'pointer', color: 'var(--text-secondary)' }}>Rename</button>
                    <button onClick={() => handleDeleteProject(selectedProject.id)} style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-default)', padding: 'var(--space-2) var(--space-3)', borderRadius: 'var(--radius-md)', cursor: 'pointer', color: 'var(--accent-warning)' }}>Delete</button>
                  </div>
                </div>
              )}
            </div>
            
            <div className="project-dashboard">
              <div className="project-column">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                  <h3 className="project-section-title" style={{ marginBottom: 0 }}>Open Tasks</h3>
                  <button className="new-task-btn" onClick={() => setIsCreatingTask(true)} style={{ background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', padding: 'var(--space-1) var(--space-3)', fontSize: '0.85rem', cursor: 'pointer' }}>
                    + New Task
                  </button>
                </div>
                
                <div className="project-items-list task-list">
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

                  {!isCreatingTask && tasks.filter(t => t.status !== 'done').length === 0 ? (
                    <p className="empty-state">No open tasks for this project.</p>
                  ) : (
                    tasks.filter(t => t.status !== 'done').map(task => (
                      <TaskCard 
                        key={task.id}
                        task={task}
                        onUpdate={handleUpdateTask}
                        onDelete={handleDeleteTask}
                        onClickInfo={() => setSelectedPanelItem({
                          title: task.description,
                          type: 'Task',
                          scores: task.scores,
                          metadata: [
                            { label: 'Created At', value: new Date(task.created_at).toLocaleString() },
                            { label: 'Source', value: task.source_entry_id ? 'Original Note' : 'Manual' }
                          ]
                        })}
                      />
                    ))
                  )}
                </div>
                
                {tasks.filter(t => t.status === 'done').length > 0 && (
                  <>
                    <h3 className="project-section-title" style={{ marginTop: 'var(--space-4)' }}>Completed Tasks</h3>
                    <div className="project-items-list task-list">
                      {tasks.filter(t => t.status === 'done').map(task => (
                        <TaskCard 
                          key={task.id}
                          task={task}
                          onUpdate={handleUpdateTask}
                          onDelete={handleDeleteTask}
                          onClickInfo={() => setSelectedPanelItem({
                            title: task.description,
                            type: 'Task',
                            scores: task.scores,
                            metadata: [
                              { label: 'Created At', value: new Date(task.created_at).toLocaleString() },
                              { label: 'Source', value: task.source_entry_id ? 'Original Note' : 'Manual' }
                            ]
                          })}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="project-column">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                  <h3 className="project-section-title" style={{ margin: 0 }}>Ideas</h3>
                  <button className="primary-button" style={{ padding: '4px 8px', fontSize: '0.8rem' }} onClick={() => setIsCreatingIdea(true)}>
                    + Add
                  </button>
                </div>
                
                <div className="project-items-list">
                  {isCreatingIdea && (
                    <div className="task-card">
                      <div className="task-edit-form">
                        <input 
                          type="text" 
                          placeholder="What's your idea?"
                          value={newIdeaDesc} 
                          onChange={(e) => setNewIdeaDesc(e.target.value)} 
                          className="task-edit-input"
                          autoFocus
                          onKeyDown={(e) => e.key === 'Enter' && handleCreateIdea()}
                        />
                        <div className="task-edit-actions" style={{ marginTop: '8px' }}>
                          <button className="task-save-btn" onClick={handleCreateIdea}>Add</button>
                          <button className="task-cancel-btn" onClick={() => setIsCreatingIdea(false)}>Cancel</button>
                        </div>
                      </div>
                    </div>
                  )}

                  {!isCreatingIdea && ideas.length === 0 ? (
                    <p className="empty-state">No ideas recorded yet.</p>
                  ) : (
                    ideas.map(idea => (
                      <IdeaCard 
                        key={idea.id} 
                        idea={idea} 
                        onUpdate={handleUpdateIdea} 
                        onDelete={handleDeleteIdea}
                        onClickInfo={() => setSelectedPanelItem({
                          title: idea.description,
                          type: 'Idea',
                          scores: idea.scores,
                          metadata: [
                            { label: 'Created At', value: new Date(idea.created_at).toLocaleString() },
                            { label: 'Source', value: idea.source_entry_id ? 'Original Note' : 'Manual' }
                          ]
                        })}
                      />
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="project-notes-section" style={{ marginTop: 'var(--space-6)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                <h3 className="project-section-title" style={{ margin: 0 }}>Associated Notes</h3>
                <div className="source-filter-segment" style={{ display: 'flex', gap: '4px', background: 'var(--bg-secondary)', padding: '4px', borderRadius: 'var(--radius-lg)' }}>
                  <button 
                    className={filterSource === 'all' ? 'active' : ''} 
                    onClick={() => setFilterSource('all')}
                    style={{ padding: '4px 12px', borderRadius: 'var(--radius-md)', background: filterSource === 'all' ? 'var(--bg-primary)' : 'transparent', border: 'none', color: filterSource === 'all' ? 'var(--text-primary)' : 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
                  >All</button>
                  <button 
                    className={filterSource === 'manual' ? 'active' : ''} 
                    onClick={() => setFilterSource('manual')}
                    style={{ padding: '4px 12px', borderRadius: 'var(--radius-md)', background: filterSource === 'manual' ? 'var(--bg-primary)' : 'transparent', border: 'none', color: filterSource === 'manual' ? 'var(--text-primary)' : 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
                  >My Notes</button>
                  <button 
                    className={filterSource === 'chat' ? 'active' : ''} 
                    onClick={() => setFilterSource('chat')}
                    style={{ padding: '4px 12px', borderRadius: 'var(--radius-md)', background: filterSource === 'chat' ? 'var(--bg-primary)' : 'transparent', border: 'none', color: filterSource === 'chat' ? 'var(--text-primary)' : 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
                  >Chat's Notes</button>
                </div>
              </div>
              <div style={{ marginBottom: 'var(--space-4)' }}>
                <EntryCapture onSubmit={handleCaptureEntry} />
              </div>
              <div className="project-notes-list">
                {entries.length === 0 ? (
                  <p className="empty-state">No notes found mentioning this project.</p>
                ) : (
                  entries.map(entry => (
                    <EntryCard 
                      key={entry.id} 
                      entry={entry} 
                      onDelete={handleDeleteEntry}
                      onReprocess={handleReprocessEntry}
                    />
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>

      <DetailsPanel
        isOpen={!!selectedPanelItem}
        onClose={() => setSelectedPanelItem(null)}
        title={selectedPanelItem?.title || ''}
        type={selectedPanelItem?.type || ''}
        scores={selectedPanelItem?.scores}
        metadata={selectedPanelItem?.metadata}
      />
    </div>
  );
}
