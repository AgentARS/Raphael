import { useState, useEffect, useRef } from 'react';
import ForceGraph from 'force-graph';
import { api, type EntityGraph } from '../api/client';
import { EntryCard } from '../components/EntryCard';
import { useEventLogger } from '../hooks/useEventLogger';
import './Entities.css';

const TYPE_COLORS: Record<string, string> = {
  project: '#3b82f6', // blue
  person: '#10b981', // green
  topic: '#8b5cf6', // purple
  organization: '#f59e0b', // orange
  tool: '#ef4444', // red
  task: '#14b8a6', // teal
  idea: '#f43f5e', // rose
  default: '#6b7280' // gray
};

const TYPE_LABELS: Record<string, string> = {
  project: 'Project',
  person: 'Person',
  topic: 'Topic',
  organization: 'Organization',
  tool: 'Tool',
  task: 'Task',
  idea: 'Idea',
};

export function Entities() {
  const { logEvent } = useEventLogger();
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<EntityGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const searchQueryRef = useRef(searchQuery);

  useEffect(() => {
    searchQueryRef.current = searchQuery;
    if (graphRef.current) {
      // Force a redraw by setting the zoom to its current value
      graphRef.current.zoom(graphRef.current.zoom());
    }
  }, [searchQuery]);
  
  // Create a ref for state so the event listener can access the latest updater
  const setSelectedEntityIdRef = useRef(setSelectedEntityId);
  setSelectedEntityIdRef.current = setSelectedEntityId;
  const logEventRef = useRef(logEvent);
  logEventRef.current = logEvent;

  useEffect(() => {
    if (selectedEntityId) {
      logEvent({
        eventType: 'entity_opened',
        objectType: 'entity',
        objectId: selectedEntityId
      });
    }
  }, [selectedEntityId, logEvent]);

  useEffect(() => {
    loadNetwork();
    
    return () => {
      // Cleanup graph on unmount
      if (graphRef.current) {
        graphRef.current._destructor();
      }
    };
  }, []);

  useEffect(() => {
    if (selectedEntityId) {
      loadGraphData(selectedEntityId);
    } else {
      setGraphData(null);
    }
  }, [selectedEntityId]);

  const loadNetwork = async () => {
    try {
      const data = await api.getNetworkGraph();
      
      // Compute max weight for normalization
      const maxWeight = Math.max(1, ...data.links.map((l: any) => l.weight || 1));
      
      if (containerRef.current) {
        const myGraph = ForceGraph()(containerRef.current)
          .graphData(data)
          .nodeLabel('name')
          .nodeRelSize(5)
          .backgroundColor('rgba(0,0,0,0)')
          
          // Custom node rendering with glow
          .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const nodeType = (node.type || '').toLowerCase();
            const color = TYPE_COLORS[nodeType] || TYPE_COLORS.default;
            const confidence = node.confidence !== undefined ? node.confidence : 1.0;
            const radius = 3 + (confidence * 4); // Min 3, Max 7
            const x = node.x;
            const y = node.y;
            
            // Guard: skip rendering if position isn't ready
            if (x == null || y == null || !isFinite(x) || !isFinite(y)) return;
            
            const searchStr = searchQueryRef.current.toLowerCase();
            const isMatch = searchStr ? node.name.toLowerCase().includes(searchStr) : true;
            
            ctx.globalAlpha = isMatch ? 1.0 : 0.15;
            
            // Outer glow
            const gradient = ctx.createRadialGradient(x, y, radius * 0.5, x, y, radius * 3);
            gradient.addColorStop(0, color + '60');
            gradient.addColorStop(1, 'transparent');
            ctx.beginPath();
            ctx.arc(x, y, radius * 3, 0, 2 * Math.PI);
            ctx.fillStyle = gradient;
            ctx.fill();
            
            // Node body
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
            
            // Bright center highlight
            ctx.beginPath();
            ctx.arc(x - radius * 0.2, y - radius * 0.2, radius * 0.35, 0, 2 * Math.PI);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
            ctx.fill();
            
            const label = node.name;
              const fontSize = Math.max(10 / globalScale, 3);
              ctx.font = `${fontSize}px Inter, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
              ctx.fillText(label, x, y + radius + 2);
              
              ctx.globalAlpha = 1.0;
            })
          .nodePointerAreaPaint((node: any, color: string, ctx: CanvasRenderingContext2D) => {
            const confidence = node.confidence !== undefined ? node.confidence : 1.0;
            const radius = 3 + (confidence * 4);
            ctx.beginPath();
            ctx.arc(node.x!, node.y!, radius + 3, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          })
          
          // Link styling based on weight and confidence
          .linkColor((link: any) => {
            const weight = link.weight || 1;
            const confidence = link.confidence !== undefined ? link.confidence : 1.0;
            const baseAlpha = Math.min(0.15 + (weight / maxWeight) * 0.4, 0.5);
            const alpha = baseAlpha * (0.3 + confidence * 0.7);
            return `rgba(255, 255, 255, ${alpha})`;
          })
          .linkWidth((link: any) => {
            const weight = link.weight || 1;
            const confidence = link.confidence !== undefined ? link.confidence : 1.0;
            return (0.5 + (weight / maxWeight) * 3) * (0.5 + confidence * 0.5);
          })
          .linkDirectionalParticles(0)
          .onNodeClick((node: any) => {
            const nodeType = (node.type || '').toLowerCase();
            logEventRef.current({
              eventType: 'graph_node_clicked',
              objectType: 'entity',
              objectId: node.id,
              metadata: { node_type: nodeType }
            });
            if (nodeType !== 'task') {
              setSelectedEntityIdRef.current(node.id);
            }
          });
          
        // Physics: links pull nodes together like a net
        const linkForce = myGraph.d3Force('link');
        if (linkForce) {
          linkForce.distance(50).strength(0.7);
        }
        
        // Gentle repulsion so nodes don't overlap but stay close
        myGraph.d3Force('charge')!.strength(-30);
        
        // Center gravity to keep graph from drifting
        myGraph.d3Force('center', null); // remove default center
        const d3 = await import('d3-force');
        myGraph.d3Force('x', d3.forceX(0).strength(0.02));
        myGraph.d3Force('y', d3.forceY(0).strength(0.02));
        
        // Slow, gentle drift for a living feel
        myGraph.d3Force('drift', () => {
          const time = Date.now() * 0.0003;
          data.nodes.forEach((node: any, i: number) => {
            if (node.x !== undefined && node.y !== undefined) {
              // Unique per-node phase offset
              const phase = i * 2.39996;
              node.vx = (node.vx || 0) + Math.sin(time + phase) * 0.02;
              node.vy = (node.vy || 0) + Math.cos(time * 0.7 + phase) * 0.02;
            }
          });
        });
        
        // High friction so drift is slow and smooth, not chaotic
        myGraph.d3VelocityDecay(0.6);
        
        // Keep the simulation alive forever
        myGraph.d3AlphaDecay(0);

        graphRef.current = myGraph;
      }
    } catch (err) {
      console.error("Failed to load network", err);
    } finally {
      setLoading(false);
    }
  };

  const loadGraphData = async (id: string) => {
    try {
      const data = await api.getEntityGraph(id);
      setGraphData(data);
    } catch (err) {
      console.error("Failed to load entity graph data", err);
    }
  };

  const handleClosePanel = () => {
    setSelectedEntityId(null);
  };

  // Ensure graph resizes when window resizes
  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current) {
        graphRef.current.width(containerRef.current.clientWidth);
        graphRef.current.height(containerRef.current.clientHeight);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="entities-page">
      <div className="graph-container" style={{ position: 'relative' }}>
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        {loading && (
          <div className="loading-state" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg-primary)', zIndex: 5 }}>
            Loading network...
          </div>
        )}
        
        {/* Search Bar */}
        <div className="graph-search-container">
          <input 
            type="text" 
            className="graph-search-input" 
            placeholder="Search nodes..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        
        {/* Legend */}
        <div className="graph-legend">
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <div key={key} className="legend-item">
              <span className="legend-dot" style={{ backgroundColor: TYPE_COLORS[key] }} />
              <span className="legend-label">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className={`side-panel ${selectedEntityId ? 'open' : ''}`}>
        <button className="close-panel-btn" onClick={handleClosePanel}>
          <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
        
        {graphData ? (
          <div className="panel-content">
            <header className="panel-header">
              <h2>{graphData.entity.name}</h2>
              <span className="entity-badge" style={{ backgroundColor: TYPE_COLORS[graphData.entity.type] || TYPE_COLORS.default }}>
                {graphData.entity.type}
              </span>
              
              {graphData.entity.scores && (
                <div className="entity-scores">
                  <div className="score-boxes">
                    <div className="score-box">
                      <span className="score-label">Relevance</span>
                      <span className="score-value">{Math.round(graphData.entity.scores.relevance)}</span>
                      <span className="score-trend" style={{ color: graphData.entity.scores.trend > 0 ? 'var(--color-success, #4caf50)' : 'var(--text-tertiary)' }}>
                        {graphData.entity.scores.trend > 0 ? `↑ +${Math.round(graphData.entity.scores.trend)}` : (graphData.entity.scores.trend < 0 ? `↓ ${Math.round(graphData.entity.scores.trend)}` : 'Stable')}
                      </span>
                    </div>
                    <div className="score-box">
                      <span className="score-label">Significance</span>
                      <span className="score-value">{Math.round(graphData.entity.scores.significance)}</span>
                    </div>
                  </div>
                  {graphData.entity.scores.explanation && (
                    <div className="score-explanation">
                      {graphData.entity.scores.explanation.split('\n').map((line, i) => <div key={i}>{line}</div>)}
                    </div>
                  )}
                </div>
              )}
            </header>

            <div className="panel-sections">
              {graphData.entries.length > 0 && (
                <section className="panel-section">
                  <h3>Notes ({graphData.entries.length})</h3>
                  <div className="entries-list">
                    {graphData.entries.map(entry => (
                      <EntryCard 
                        key={entry.id} 
                        entry={entry} 
                        onDelete={async (id) => {
                          await api.deleteEntry(id);
                          loadGraphData(selectedEntityId!);
                        }} 
                      />
                    ))}
                  </div>
                </section>
              )}

              {graphData.tasks.length > 0 && (
                <section className="panel-section">
                  <h3>Tasks ({graphData.tasks.length})</h3>
                  <div className="task-list">
                    {graphData.tasks.map(task => (
                      <div key={task.id} className={`task-item ${task.status === 'done' ? 'done' : ''}`} style={{ opacity: task.status === 'done' ? 0.6 : 1 }}>
                        <div className="task-indicator">
                          {task.status === 'done' && '✓'}
                        </div>
                        <div className="task-desc" style={{ textDecoration: task.status === 'done' ? 'line-through' : 'none' }}>{task.description}</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </div>
        ) : (
          <div className="panel-loading">Loading details...</div>
        )}
      </div>
    </div>
  );
}
