import React, { useEffect, useState } from 'react';
import { briefingApi, type DailyBriefing, type BriefingSection } from '../api/briefing';
import { useGlobalDiscussion } from '../contexts/DiscussionContext';
import './Briefing.css';

export function Briefing() {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  
  const { openDiscussion } = useGlobalDiscussion();

  useEffect(() => {
    fetchBriefing();
    // Refresh every minute to pick up dynamic task/calendar changes or applied discussion updates
    const interval = setInterval(fetchBriefing, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchBriefing = async () => {
    try {
      const data = await briefingApi.getToday();
      setBriefing(data);
      setError(null);
    } catch (err) {
      setError('Failed to load briefing.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDiscuss = (sectionKey: string, sectionTitle: string, index: number, content: string, evidence?: any[]) => {
    if (!briefing) return;
    openDiscussion({
      object_type: 'briefing_item',
      section: sectionTitle,
      content,
      evidence,
      date: briefing.date,
      sectionKey,
      itemIndex: index
    });
  };

  if (loading && !briefing) {
    return <div className="briefing-loading">Gathering context...</div>;
  }

  if (error) {
    return <div className="briefing-error">{error}</div>;
  }

  if (briefing?.status === 'generating') {
    return (
      <div className="briefing-generating">
        <div className="spinner"></div>
        <h2>Generating your Daily Briefing...</h2>
        <p>Raphael is synthesizing your projects, notes, and calendar.</p>
        <p className="subtext">This usually takes 30-60 seconds.</p>
      </div>
    );
  }

  if (!briefing) return null;

  const handleRegenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      await briefingApi.regenerate();
      await fetchBriefing();
    } catch (err) {
      console.error(err);
      setError('Failed to regenerate briefing.');
      setLoading(false);
    }
  };

  const renderSection = (key: string, section: BriefingSection, icon: string, layout: 'list' | 'card' = 'list') => {
    if (!section || !section.items) return null;
    
    // Filter out items with empty content
    const validItems = section.items.filter(item => item.content && item.content.trim() !== '');
    if (validItems.length === 0) return null;

    return (
      <div className={`briefing-section section-${key} layout-${layout}`}>
        <h3><span className="section-icon">{icon}</span> {section.title}</h3>
        <ul className="briefing-items">
          {validItems.map((item, idx) => {
            const itemId = `${key}-${idx}`;
            const isExpanded = expandedItems.has(itemId);
            return (
              <li key={idx} className="briefing-item">
                <div className="item-content">{item.content}</div>
                <div className="item-actions">
                  <button className="discuss-btn" onClick={() => handleDiscuss(key, section.title, idx, item.content, item.evidence)}>
                    💬 Discuss
                  </button>
                  {item.explanation && (
                    <button className="explain-btn" onClick={() => toggleExpand(itemId)}>
                      {isExpanded ? 'Hide reasoning' : 'Why?'}
                    </button>
                  )}
                </div>
                {item.explanation && isExpanded && (
                  <div className="item-explanation">
                    {item.explanation}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    );
  };

  return (
    <div className="briefing-page-layout">
      <div className="briefing-container">
        <header className="briefing-header">
          <div className="header-content">
            <h1>Daily Briefing</h1>
            <button className="regenerate-btn" onClick={handleRegenerate} disabled={loading} title="Update Briefing">
              🔄 Update
            </button>
            <p className="briefing-date">
              {new Date(briefing.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
            </p>
          </div>
          <div className="header-meta">
            <span className="last-updated">
              Last analyzed: {new Date(briefing.last_updated + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </header>

        <div className="briefing-grid">
          <div className="briefing-main-col">
            <div className="hero-sections">
              {renderSection('overview', briefing.overview, '🧭', 'card')}
              {renderSection('current_state', briefing.current_state, '📊', 'card')}
            </div>
            
            <div className="action-sections">
              {renderSection('suggested_plan', briefing.suggested_plan, '🎯')}
              {renderSection('needs_attention', briefing.needs_attention, '⚠️')}
            </div>
          </div>
          
          <div className="briefing-side-col">
            <div className="insight-card">
              <h3><span className="section-icon">💡</span> {briefing.insight?.title || 'Insight'}</h3>
              <div className="insight-content">
                "{briefing.insight?.items?.[0]?.content || 'No insights today.'}"
              </div>
            </div>
            
            {renderSection('upcoming', briefing.upcoming, '📅')}
            {renderSection('open_loops', briefing.open_loops, '🔄')}
          </div>
        </div>
      </div>
    </div>
  );
}
