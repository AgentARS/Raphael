import { useState, useRef, useEffect } from 'react';
import type { FormEvent } from 'react';
import './EntryCapture.css';

interface EntryCaptureProps {
  onSubmit: (content: string) => Promise<void>;
}

export function EntryCapture({ onSubmit }: EntryCaptureProps) {
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-expand textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.max(120, textareaRef.current.scrollHeight)}px`;
    }
  }, [content]);

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!content.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onSubmit(content);
      setContent('');
      // Trigger a subtle success animation here if desired
    } catch (err) {
      console.error('Failed to save entry', err);
    } finally {
      setIsSubmitting(false);
      // Reset height
      if (textareaRef.current) {
        textareaRef.current.style.height = '120px';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form className="entry-capture" onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Write a note... (⌘+Enter to save)"
        disabled={isSubmitting}
      />
      <div className="entry-capture-footer">
        <span className="char-count">{content.length} characters</span>
        <button 
          type="submit" 
          disabled={!content.trim() || isSubmitting}
          className={isSubmitting ? 'submitting' : ''}
        >
          {isSubmitting ? 'Saving...' : 'Save'}
        </button>
      </div>
    </form>
  );
}
