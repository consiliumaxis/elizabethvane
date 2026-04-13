import React, { useState, useEffect, useRef } from 'react';
import { apiFetchJson } from '../../lib/api';
import './ChatAI.css';

export default function ChatAI({ user, t }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [chatId, setChatId] = useState(null);
  
  const [showHistory, setShowHistory] = useState(false);
  const [historyList, setHistoryList] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const messagesEndRef = useRef(null);
  const messagesAreaRef = useRef(null);
  const textareaRef = useRef(null);
  const hasInitialPositioned = useRef(false);

  const scrollToBottom = (behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    if (!messages.length && !isThinking) return;

    if (!hasInitialPositioned.current) {
      hasInitialPositioned.current = true;
      if (messagesAreaRef.current) messagesAreaRef.current.scrollTop = 0;
      return;
    }

    scrollToBottom('smooth');
  }, [messages, isThinking]);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  useEffect(() => {
    const fetchActiveChat = async () => {
      try {
        const data = await apiFetchJson('/api/ai/chat/active', {
          method: 'POST',
          body: JSON.stringify({})
        });
        
        if (data.status === 'success') {
          setChatId(data.chat_id);
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages.map(m => ({
              id: m.id,
              role: m.role,
              text: m.content,
              timestamp: m.timestamp
            })));
          } else {
            setMessages([{
              id: 1,
              role: 'ai',
              text: t.chat.welcome,
              timestamp: new Date().toISOString(),
            }]);
          }
        }
      } catch (e) {
        console.error(e);
      }
    };

    fetchActiveChat();
  }, [user]);

  const handleInput = (e) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 100)}px`;
    }
  };

  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isThinking || !chatId) return;

    const newUserMsg = {
      id: Date.now(),
      role: 'user',
      text: trimmed,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setInputValue('');
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    setIsThinking(true);

    try {
      const data = await apiFetchJson('/api/ai/chat/send', {
        method: 'POST',
        body: JSON.stringify({ chat_id: chatId, text: trimmed })
      });
      
      if (data.status === 'success') {
        setMessages((prev) => [...prev, {
          id: Date.now() + 1,
          role: 'ai',
          text: data.response,
          timestamp: new Date().toISOString(),
        }]);
      }
    } catch (e) {
      console.error(e);
      const fallbackText = e?.message || 'AI service is temporarily unavailable. Please try again in a moment.';
      setMessages((prev) => [...prev, {
        id: Date.now() + 2,
        role: 'ai',
        text: fallbackText,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = async () => {
    try {
      const data = await apiFetchJson('/api/ai/chat/new', {
        method: 'POST',
        body: JSON.stringify({})
      });
      
      if (data.status === 'success') {
        setChatId(data.chat_id);
        setMessages([
          {
            id: Date.now(),
            role: 'ai',
            text: t.chat.cleared,
            timestamp: new Date().toISOString(),
          }
        ]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleHistoryOpen = async () => {
    setShowHistory(true);
    setIsLoadingHistory(true);
    
    try {
      const data = await apiFetchJson('/api/ai/chat/history', {
        method: 'POST',
        body: JSON.stringify({})
      });
      if (data.status === 'success') {
        setHistoryList(data.chats);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleLoadChat = async (id) => {
    setShowHistory(false);
    
    try {
      const data = await apiFetchJson('/api/ai/chat/load', {
        method: 'POST',
        body: JSON.stringify({ chat_id: id })
      });
      
      if (data.status === 'success') {
        setChatId(data.chat_id);
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages.map(m => ({
            id: m.id,
            role: m.role,
            text: m.content,
            timestamp: m.timestamp
          })));
        } else {
          setMessages([{
            id: Date.now(),
            role: 'ai',
            text: t.chat.loaded,
            timestamp: new Date().toISOString(),
          }]);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return '';
    let d;
    if (isoString.includes('Z') || isoString.includes('T')) {
      d = new Date(isoString);
    } else {
      d = new Date(isoString.replace(' ', 'T') + 'Z');
    }
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (isoString) => {
    if (!isoString) return '';
    let d;
    if (isoString.includes('Z') || isoString.includes('T')) {
      d = new Date(isoString);
    } else {
      d = new Date(isoString.replace(' ', 'T') + 'Z');
    }
    return d.toLocaleDateString([], { day: '2-digit', month: '2-digit', year: 'numeric' }) + ' ' + formatTime(isoString);
  };

  const formatMessage = (text) => {
    if (!text) return '';
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index} style={{ color: 'var(--accent)', fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <span key={index} style={{ 
            background: 'rgba(139, 107, 44, 0.14)', 
            color: 'var(--accent)', 
            padding: '2px 6px', 
            borderRadius: '4px',
            fontVariantNumeric: 'tabular-nums',
            fontSize: '0.9em'
          }}>
            {part.slice(1, -1)}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="chat-container-fixed">
      <div className="chat-wrapper">
        
        <div className="chat-header-bar">
          <div className="chat-title-info">
            <div className="ai-avatar-mini" aria-hidden="true">AI</div>
            <div>
              <h2 className="chat-header-title">AI Assistant</h2>
              <span className="chat-status">{isThinking ? t.chat.thinking : t.chat.online}</span>
            </div>
          </div>
          <div className="chat-header-actions">
            <button className="icon-action-btn" onClick={handleHistoryOpen} title={t.chat.historyTooltip}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
            </button>
            <button className="icon-action-btn" onClick={handleNewChat} title={t.chat.newChatTooltip}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                <path d="M3 3v5h5"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="chat-messages-area" ref={messagesAreaRef}>
          {messages.map((msg) => (
            <div key={msg.id} className={`message-row ${msg.role === 'user' ? 'is-user' : 'is-ai'}`}>
              <div className={`message-bubble fade-in-up`}>
                <div className="message-text">{formatMessage(msg.text)}</div>
                <div className="message-time">{formatTime(msg.timestamp)}</div>
              </div>
            </div>
          ))}

          {isThinking && (
            <div className="message-row is-ai fade-in-up">
              <div className="message-bubble typing-bubble">
                <div className="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              value={inputValue}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder={t.chat.placeholder}
              rows={1}
            />
            <button 
              className={`chat-send-btn ${inputValue.trim() ? 'active' : ''}`} 
              onClick={handleSend}
              disabled={!inputValue.trim() || isThinking}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>

      </div>

      {showHistory && (
        <div className="chat-history-overlay" onClick={() => setShowHistory(false)}>
          <div className="chat-history-modal fade-in-up" onClick={e => e.stopPropagation()}>
            <h3 className="chat-history-title">{t.chat.historyModalTitle}</h3>
            
            {isLoadingHistory ? (
              <div className="chat-history-loading">{t.chat.loading}</div>
            ) : historyList.length > 0 ? (
              <div className="chat-history-list">
                {historyList.map(chat => (
                  <div key={chat.id} className={`chat-history-item ${chat.id === chatId ? 'active' : ''}`} onClick={() => handleLoadChat(chat.id)}>
                    <div className="chat-history-item-title">{chat.title}</div>
                    <div className="chat-history-item-date">{formatDate(chat.updated_at)}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="chat-history-empty">{t.chat.emptyHistory}</div>
            )}
            
            <button className="chat-history-close" onClick={() => setShowHistory(false)}>{t.chat.closeBtn}</button>
          </div>
        </div>
      )}
    </div>
  );
}


