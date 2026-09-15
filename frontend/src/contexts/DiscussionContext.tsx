import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { type Message, type DiscussionContext as ApiDiscussionContext } from '../api/discussions';

interface GlobalDiscussionState {
  context: ApiDiscussionContext | null;
  messages: Message[];
  input: string;
  isCollapsed: boolean;
  width: number;
  proposal: { text: string; action: 'KEEP' | 'EDIT' | 'DELETE'; newContent?: string } | null;
}

interface GlobalDiscussionContextType {
  state: GlobalDiscussionState;
  openDiscussion: (context: ApiDiscussionContext) => void;
  closeDiscussion: () => void;
  setCollapsed: (collapsed: boolean) => void;
  setWidth: (width: number) => void;
  setMessages: (messages: Message[]) => void;
  setInput: (input: string) => void;
  setProposal: (proposal: GlobalDiscussionState['proposal']) => void;
  clearState: () => void;
}

const DiscussionGlobalContext = createContext<GlobalDiscussionContextType | undefined>(undefined);

export const DiscussionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<GlobalDiscussionState>(() => {
    const saved = localStorage.getItem('raphael_discussion_state');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error('Failed to parse saved discussion state', e);
      }
    }
    return {
      context: null,
      messages: [],
      input: '',
      isCollapsed: false,
      width: 750,
      proposal: null
    };
  });

  useEffect(() => {
    localStorage.setItem('raphael_discussion_state', JSON.stringify(state));
  }, [state]);

  const openDiscussion = (context: ApiDiscussionContext) => {
    setState(prev => ({
      ...prev,
      context,
      messages: [],
      input: '',
      proposal: null,
      isCollapsed: false
    }));
  };

  const closeDiscussion = () => {
    setState(prev => ({ ...prev, context: null, proposal: null, messages: [], input: '' }));
  };

  const setCollapsed = (collapsed: boolean) => {
    setState(prev => ({ ...prev, isCollapsed: collapsed }));
  };

  const setWidth = (width: number) => {
    setState(prev => ({ ...prev, width }));
  };

  const setMessages = (messages: Message[]) => {
    setState(prev => ({ ...prev, messages }));
  };

  const setInput = (input: string) => {
    setState(prev => ({ ...prev, input }));
  };

  const setProposal = (proposal: GlobalDiscussionState['proposal']) => {
    setState(prev => ({ ...prev, proposal }));
  };

  const clearState = () => {
    setState(prev => ({ ...prev, context: null, messages: [], input: '', proposal: null }));
  };

  return (
    <DiscussionGlobalContext.Provider value={{
      state,
      openDiscussion,
      closeDiscussion,
      setCollapsed,
      setWidth,
      setMessages,
      setInput,
      setProposal,
      clearState
    }}>
      {children}
    </DiscussionGlobalContext.Provider>
  );
};

export const useGlobalDiscussion = () => {
  const context = useContext(DiscussionGlobalContext);
  if (context === undefined) {
    throw new Error('useGlobalDiscussion must be used within a DiscussionProvider');
  }
  return context;
};
