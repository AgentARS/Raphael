import { useEffect } from 'react';
import { Routes, Route, NavLink, Navigate } from 'react-router';
import { Timeline } from './pages/Timeline';
import { Dashboard } from './pages/Dashboard';
import { Projects } from './pages/Projects';
import { Entities } from './pages/Entities';
import { Chat } from './pages/Chat';
import { PendingTaskPopup } from './components/PendingTaskPopup';
import { SuggestedTaskPopup } from './components/SuggestedTaskPopup';
import { AutonomousPanel } from './components/AutonomousPanel';
import { Briefing } from './pages/Briefing';
import { useEventLogger } from './hooks/useEventLogger';
import { autonomousApi } from './api/autonomous';
import type { AutonomousStatus } from './api/autonomous';
import { useState } from 'react';
import { DiscussionProvider } from './contexts/DiscussionContext';
import { DiscussionPanel } from './components/DiscussionPanel';
import './App.css';

function App() {
  const { logEvent } = useEventLogger();

  useEffect(() => {
    logEvent({
      eventType: 'app_opened',
      metadata: { url: window.location.href }
    });
    
    const handleBeforeUnload = () => {
      logEvent({ eventType: 'app_closed' });
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [logEvent]);

  const [autoStatus, setAutoStatus] = useState<AutonomousStatus | null>(null);
  const [showAutoPanel, setShowAutoPanel] = useState(false);

  useEffect(() => {
    // Initial fetch of autonomous status
    autonomousApi.getStatus().then(setAutoStatus).catch(console.error);
  }, []);

  const refreshAutoStatus = async () => {
    try {
      const status = await autonomousApi.getStatus();
      setAutoStatus(status);
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleAutoMode = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const newMode = e.target.checked ? 'autonomous' : 'manual';
    await autonomousApi.setMode(newMode);
    await refreshAutoStatus();
  };

  return (
    <DiscussionProvider>
      <div className="app-container">
        <aside className="sidebar">
          <div className="sidebar-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 className="app-title">Raphael</h1>
            <div className="auto-mode-toggle" title="Autonomous Mode Settings">
              <label className="switch">
                <input 
                  type="checkbox" 
                  checked={autoStatus?.mode === 'autonomous'} 
                  onChange={handleToggleAutoMode}
                />
                <span className="slider round"></span>
              </label>
              <button className="auto-settings-btn" onClick={() => setShowAutoPanel(true)}>
                ⚙️
              </button>
            </div>
          </div>
          
          <nav className="sidebar-nav">
            <NavLink to="/dashboard" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
              Dashboard
            </NavLink>
            
            <NavLink to="/briefing" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
              </svg>
              Briefing
            </NavLink>
            
            <NavLink to="/timeline" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              Notes
            </NavLink>
            
            <NavLink to="/projects" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
              Projects
            </NavLink>
            
            <NavLink to="/entities" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
              Entities
            </NavLink>
            
            <NavLink to="/chat" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              Chat
            </NavLink>
          </nav>
        </aside>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/briefing" element={<Briefing />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/entities" element={<Entities />} />
            <Route path="/chat" element={<Chat />} />
          </Routes>
        </main>
        <PendingTaskPopup />
        <SuggestedTaskPopup />
        {showAutoPanel && (
          <AutonomousPanel 
            status={autoStatus} 
            onClose={() => setShowAutoPanel(false)} 
            refreshStatus={refreshAutoStatus} 
          />
        )}
        <DiscussionPanel />
      </div>
    </DiscussionProvider>
  );
}

export default App;
