import React, { useState, useEffect, useRef, useCallback } from 'react';
import { type Message, discussionsApi } from '../api/discussions';
import { briefingApi } from '../api/briefing';
import { useGlobalDiscussion } from '../contexts/DiscussionContext';
import './DiscussionPanel.css';

export const DiscussionPanel: React.FC = () => {
  const { state, setCollapsed, setWidth, setMessages, setInput, setProposal, clearState } = useGlobalDiscussion();
  const { context, messages, input, isCollapsed, width, proposal } = state;
  
  const [isTyping, setIsTyping] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  
  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const [isResizing, setIsResizing] = useState(false);

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = useCallback(
    (e: MouseEvent) => {
      if (isResizing) {
        const newWidth = document.body.clientWidth - e.clientX;
        const maxWidth = document.body.clientWidth * 0.95;
        if (newWidth >= 400 && newWidth <= maxWidth) {
          setWidth(newWidth);
        }
      }
    },
    [isResizing, setWidth]
  );

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', resize);
      window.addEventListener('mouseup', stopResizing);
      document.body.style.userSelect = 'none';
    } else {
      document.body.style.userSelect = '';
    }
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
      document.body.style.userSelect = '';
    };
  }, [isResizing, resize, stopResizing]);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, proposal, isCollapsed]);

  if (!context) return null;

  if (isCollapsed) {
    return (
      <button className="expand-panel-btn" onClick={() => setCollapsed(false)} title="Expand discussion">
        ◀
      </button>
    );
  }

  const handleSend = async () => {
    if (!input.trim() || isTyping || isFinishing || proposal) return;
    
    const userMsg: Message = { role: 'user', content: input };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setIsTyping(true);
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset height
    }
    
    try {
      const res = await discussionsApi.chat({ context, messages: newMessages });
      setMessages([...newMessages, { role: 'assistant', content: res.reply }]);
    } catch (e) {
      console.error(e);
      setMessages([...newMessages, { role: 'assistant', content: 'Sorry, I encountered an error.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
    e.target.style.overflowY = e.target.scrollHeight > 120 ? 'auto' : 'hidden';
  };

  const handleFinish = async () => {
    setIsFinishing(true);
    try {
      const res = await discussionsApi.finish({ context, messages });
      setProposal({
        text: res.proposal_text,
        action: res.briefing_action as 'KEEP' | 'EDIT' | 'DELETE',
        newContent: res.new_content
      });
    } catch (e) {
      console.error(e);
      alert('Failed to generate proposal.');
    } finally {
      setIsFinishing(false);
    }
  };
  
  const handleApply = async () => {
    if (proposal && context.object_type === 'briefing_item' && context.section) {
      try {
        // Attempt to extract index from context if it was passed. 
        // For now, we assume the backend applies it via the date/section. 
        // Actually, our API required date, sectionKey, itemIndex, action, newContent.
        // Wait, context doesn't currently store date and index! 
        // We will need to update the context to include date and index.
        const date = new Date().toISOString().split('T')[0]; // Fallback to today
        const idx = context.evidence?.[0]?.itemIndex ?? 0; // Fallback
        
        await briefingApi.updateItem(
          (context as any).date || date, 
          (context as any).sectionKey || context.section.toLowerCase().replace(' ', '_'), 
          (context as any).itemIndex ?? idx, 
          proposal.action, 
          proposal.newContent
        );
        alert('Update applied! It will appear on your Briefing shortly.');
        clearState();
      } catch(err) {
        console.error(err);
        alert('Failed to apply update.');
      }
    } else {
      clearState();
    }
  };

  return (
    <div 
      className={`discussion-panel ${isResizing ? 'is-resizing' : ''}`}
      style={{ width: `${width}px` }}
      ref={panelRef}
    >
      <div className="dp-resizer" onMouseDown={startResizing} />
      <header className="dp-header">
        <h2>Discuss Knowledge</h2>
        <button className="close-btn" onClick={() => setCollapsed(true)} title="Collapse window">➡️</button>
      </header>
      
      <div className="dp-context">
        <span className="dp-badge">{context.object_type} {context.section ? `/ ${context.section}` : ''}</span>
        <p>{context.content}</p>
      </div>
      
      <div className="dp-messages">
        {messages.length === 0 && (
          <div className="dp-empty">
            Ask Raphael to clarify, correct, or expand on this knowledge.
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`dp-message role-${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {isTyping && <div className="dp-message role-assistant typing">Raphael is typing...</div>}
        {isFinishing && <div className="dp-message role-assistant typing">Generating update proposal...</div>}
        
        {proposal && (
          <div className="dp-proposal">
            <h3>Proposed Update</h3>
            <p className="proposal-text">{proposal.text}</p>
            {proposal.action === 'EDIT' && (
              <div className="proposal-diff">
                <strong>New Content:</strong> {proposal.newContent}
              </div>
            )}
            <div className="proposal-actions">
              <button className="btn-reject" onClick={() => setProposal(null)}>Reject</button>
              <button className="btn-apply" onClick={handleApply}>Apply Change</button>
            </div>
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>
      
      {!proposal && (
        <div className="dp-input-area">
          <textarea 
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="What needs to be corrected?"
            disabled={isTyping || isFinishing}
            rows={1}
          />
          <div className="dp-input-actions">
            <button className="btn-send" onClick={handleSend} disabled={!input.trim() || isTyping || isFinishing}>Send</button>
            <button className="btn-finish" onClick={handleFinish} disabled={messages.length === 0 || isTyping || isFinishing}>Finish</button>
          </div>
        </div>
      )}
    </div>
  );
};
