import React from 'react';
import './DetailsPanel.css';
import { TYPE_COLORS } from '../pages/Entities';

export interface ScoreData {
  relevance: number;
  significance: number;
  trend: number;
  explanation?: string;
}

export interface MetadataItem {
  label: string;
  value: React.ReactNode;
}

interface DetailsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  type: string;
  scores?: ScoreData | null;
  metadata?: MetadataItem[];
}

const DetailsPanel: React.FC<DetailsPanelProps> = ({ isOpen, onClose, title, type, scores, metadata }) => {
  return (
    <div className={`side-panel ${isOpen ? 'open' : ''}`}>
      <button className="close-panel-btn" onClick={onClose}>
        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
      
      <div className="panel-content">
        <header className="panel-header">
          <h2>{title}</h2>
          <span className="entity-badge" style={{ backgroundColor: TYPE_COLORS[type.toLowerCase()] || '#9e9e9e' }}>
            {type}
          </span>
          
          {scores && (
            <div className="entity-scores">
              <div className="score-boxes">
                <div className="score-box">
                  <span className="score-label">Relevance</span>
                  <span className="score-value">{Math.round(scores.relevance)}</span>
                  <span className="score-trend" style={{ color: scores.trend > 0 ? 'var(--color-success, #4caf50)' : 'var(--text-tertiary)' }}>
                    {scores.trend > 0 ? `↑ +${Math.round(scores.trend)}` : (scores.trend < 0 ? `↓ ${Math.round(Math.abs(scores.trend))}` : 'Stable')}
                  </span>
                </div>
                <div className="score-box">
                  <span className="score-label">Significance</span>
                  <span className="score-value">{Math.round(scores.significance)}</span>
                </div>
              </div>
              {scores.explanation && (
                <div className="score-explanation">
                  {scores.explanation.split('\n').map((line, i) => <div key={i}>{line}</div>)}
                </div>
              )}
            </div>
          )}
        </header>

        {metadata && metadata.length > 0 && (
          <div className="panel-sections">
            <section className="panel-section">
              <h3>Details</h3>
              {metadata.map((item, i) => (
                <div key={i} className="metadata-row">
                  <span className="metadata-label">{item.label}</span>
                  <span className="metadata-value">{item.value}</span>
                </div>
              ))}
            </section>
          </div>
        )}
      </div>
    </div>
  );
};

export default DetailsPanel;
