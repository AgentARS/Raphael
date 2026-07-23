import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api, type ChatMessage } from '../api/client';
import { useEventLogger } from '../hooks/useEventLogger';
import './Chat.css';

export function Chat() {
  const { logEvent } = useEventLogger();
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const saved = localStorage.getItem('chat_messages');
    return saved ? JSON.parse(saved) : [];
  });
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsTyping(false);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages, isTyping]);

  const handleClearChat = () => {
    setMessages([]);
    localStorage.removeItem('chat_messages');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;

    const userMsg: ChatMessage = { role: 'user', content: input.trim() };
    
    if (messages.length === 0) {
      logEvent({ eventType: 'chat_started' });
    }
    
    logEvent({ 
      eventType: 'chat_message_sent',
      metadata: { content_length: userMsg.content.length }
    });

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setIsTyping(true);

    try {
      // Add empty assistant message that we will stream into
      setMessages([...newMessages, { role: 'assistant', content: '' }]);
      
      abortControllerRef.current = new AbortController();
      const stream = api.chatStream(newMessages, abortControllerRef.current.signal);
      let assistantContent = '';
      
      for await (const chunk of stream) {
        assistantContent += chunk;
        
        // Hide the JSON commands block from the user while streaming
        let displayContent = assistantContent;
        const jsonStartIndex = Math.max(
          displayContent.indexOf('```json'),
          displayContent.indexOf("'''json")
        );
        
        if (jsonStartIndex !== -1) {
          displayContent = displayContent.substring(0, jsonStartIndex).trim();
        }
        
        setMessages([...newMessages, { role: 'assistant', content: displayContent }]);
      }
      
      logEvent({
        eventType: 'chat_response_generated',
        metadata: { response_length: assistantContent.length }
      });

      // After streaming finishes, check for commands block using both backticks and single quotes
      const commandRegex = /(?:```|''')json\s*\n\s*(\{\s*"commands".*?\})\s*\n\s*(?:```|''')/is;
      const match = assistantContent.match(commandRegex);
      if (match) {
        try {
          const jsonStr = match[1];
          const data = JSON.parse(jsonStr);
          
          if (data.commands && Array.isArray(data.commands)) {
            for (const cmd of data.commands) {
              if (cmd.type === 'create_task') {
                await api.createTask({ description: cmd.description });
              } else if (cmd.type === 'create_project') {
                await api.createEntity({ name: cmd.name, type: 'project' });
              } else if (cmd.type === 'create_note') {
                await api.createEntry({ content: cmd.content, source_type: 'chat' });
              } else if (cmd.type === 'task_update') {
                await api.semanticTaskUpdate({ semantic_description: cmd.semantic_description, action: cmd.action });
              } else if (cmd.type === 'create_calendar_event') {
                await api.createCalendarEvent({ 
                  summary: cmd.summary, 
                  description: cmd.description,
                  start_time: cmd.start_time,
                  end_time: cmd.end_time,
                  recurrence: cmd.recurrence,
                  color_id: cmd.color_id 
                });
              } else if (cmd.type === 'update_calendar_event') {
                await api.updateCalendarEvent(cmd.id, {
                  summary: cmd.summary,
                  description: cmd.description,
                  start_time: cmd.start_time,
                  end_time: cmd.end_time,
                  recurrence: cmd.recurrence,
                  color_id: cmd.color_id
                });
              } else if (cmd.type === 'delete_calendar_event') {
                await api.deleteCalendarEvent(cmd.id);
              }
            }
          }
          
          // Strip the JSON block from the displayed message
          const cleanContent = assistantContent.replace(commandRegex, '').trim();
          setMessages([...newMessages, { role: 'assistant', content: cleanContent }]);
        } catch (e: any) {
          console.error("Failed to parse or execute commands:", e);
          let cleanContent = assistantContent;
          const jsonStartIndex = Math.max(
            cleanContent.indexOf('```json'),
            cleanContent.indexOf("'''json")
          );
          if (jsonStartIndex !== -1) {
            cleanContent = cleanContent.substring(0, jsonStartIndex).trim();
          }
          setMessages([...newMessages, 
            { role: 'assistant', content: cleanContent },
            { role: 'assistant', content: `⚠️ **Action Failed:** ${e.message || e}` }
          ]);
        }
      } else {
         // Final fallback strip in case it was malformed
         let cleanContent = assistantContent;
         const jsonStartIndex = Math.max(
           cleanContent.indexOf('```json'),
           cleanContent.indexOf("'''json")
         );
         if (jsonStartIndex !== -1) {
           cleanContent = cleanContent.substring(0, jsonStartIndex).trim();
         }
         setMessages([...newMessages, { role: 'assistant', content: cleanContent }]);
      }
    } catch (err: any) {
      if (err.name === 'AbortError' || err.message?.includes('aborted')) {
        console.log('Stream aborted by user');
      } else {
        console.error("Chat error", err);
        setMessages([...newMessages, { role: 'assistant', content: 'Sorry, I encountered an error connecting to the AI.' }]);
      }
    } finally {
      setIsTyping(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="chat-page">
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Chat with Raphael</h1>
          <p style={{ color: 'var(--text-tertiary)', fontSize: '0.9rem' }}>
            Ask questions based on your notes and tasks.
          </p>
        </div>
        <button 
          onClick={handleClearChat}
          style={{
            background: 'transparent',
            border: '1px solid var(--border-default)',
            color: 'var(--text-secondary)',
            padding: 'var(--space-2) var(--space-4)',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer'
          }}
        >
          Clear Chat
        </button>
      </header>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Hi! I'm Raphael, your personal AI assistant.</p>
              <p>Try asking me about your current projects, upcoming tasks, or notes.</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.role}`}>
                <div className="message-bubble">
                  {msg.role === 'assistant' && msg.content === '' && isTyping && idx === messages.length - 1 ? (
                    <div className="typing-indicator">
                      <span></span><span></span><span></span>
                    </div>
                  ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-area" onSubmit={handleSubmit}>
          <input
            type="text"
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your notes..."
            disabled={isTyping}
          />
          {isTyping ? (
            <button type="button" className="chat-send-btn stop-btn" onClick={handleStop}>
              <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" />
              </svg>
            </button>
          ) : (
            <button type="submit" className="chat-send-btn" disabled={!input.trim()}>
              <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
