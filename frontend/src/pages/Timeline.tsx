import { useState, useEffect } from 'react';
import { api, type Entry, type SearchResult } from '../api/client';
import { EntryCapture } from '../components/EntryCapture';
import { EntryCard } from '../components/EntryCard';
import { SearchBar } from '../components/SearchBar';
import { useEventLogger } from '../hooks/useEventLogger';
import './Timeline.css';

export function Timeline() {
  const { logEvent } = useEventLogger();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSource, setFilterSource] = useState('all');

  const loadEntries = async () => {
    try {
      setIsLoading(true);
      const data = await api.getEntries(50, 0, undefined, filterSource);
      setEntries(data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Failed to load entries. Is the backend running?');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEntries();
  }, [filterSource]);

  // Poll for updates if any entry is pending extraction
  useEffect(() => {
    if (isSearching) return; // Don't poll while viewing search results
    
    const hasPending = entries.some(e => e.extraction_status === 'pending');
    if (!hasPending) return;

    const intervalId = setInterval(async () => {
      try {
        const data = await api.getEntries(50, 0, undefined, filterSource);
        setEntries(data);
      } catch (err) {
        console.error('Polling failed:', err);
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [entries, isSearching]);

  const handleSearch = async (query: string) => {
    if (!query.trim()) {
      setIsSearching(false);
      setSearchResults([]);
      return;
    }

    try {
      setIsSearching(true);
      const results = await api.search(query);
      setSearchResults(results);
    } catch (err) {
      console.error('Search failed', err);
    }
  };

  const handleCreateEntry = async (content: string) => {
    const entry = await api.createEntry({ content });
    logEvent({
      eventType: 'note_created',
      objectType: 'entry',
      objectId: entry.id
    });
    // Reload to get the new entry and its extraction status
    await loadEntries();
  };

  const handleReprocess = async (id: string) => {
    try {
      await api.reprocessEntry(id);
      // Force a reload to see pending status
      await loadEntries();
    } catch (err) {
      console.error('Failed to reprocess entry:', err);
    }
  };

  const handleDeleteEntry = async (id: string) => {
    try {
      await api.deleteEntry(id);
      // Optimistic UI update
      setEntries(entries.filter(e => e.id !== id));
      if (isSearching) {
        setSearchResults(searchResults.filter(r => r.entry.id !== id));
      }
    } catch (err) {
      console.error('Failed to delete entry', err);
    }
  };

  return (
    <div className="timeline-page">
      <header className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
          <h1>Notes</h1>
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
        <SearchBar onSearch={handleSearch} />
      </header>

      <div className="capture-section">
        <EntryCapture onSubmit={handleCreateEntry} />
      </div>

      <div className="entries-list">
        {error && <div className="error-message">{error}</div>}
        
        {isLoading && !isSearching && (
          <>
            <div className="skeleton-card" />
            <div className="skeleton-card" />
            <div className="skeleton-card" />
          </>
        )}

        {!isLoading && !isSearching && entries.length === 0 && !error && (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" strokeWidth="1" fill="none" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            <h2>No entries yet</h2>
            <p>Write your first note above to start building your knowledge base.</p>
          </div>
        )}

        {isSearching && searchResults.length === 0 && (
          <div className="empty-state">
            <p>No results found for your search.</p>
          </div>
        )}

        {isSearching ? (
          searchResults.map((result) => (
            <div key={result.entry.id} className="search-result">
              <EntryCard entry={result.entry} onDelete={handleDeleteEntry} onReprocess={handleReprocess} />
              {result.snippet && (
                <div 
                  className="search-snippet"
                  dangerouslySetInnerHTML={{ __html: result.snippet }}
                />
              )}
            </div>
          ))
        ) : (
          entries.map((entry) => (
            <EntryCard key={entry.id} entry={entry} onDelete={handleDeleteEntry} onReprocess={handleReprocess} />
          ))
        )}
      </div>
    </div>
  );
}
