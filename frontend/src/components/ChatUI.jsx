import React, { useState, useRef, useEffect, useMemo } from 'react';
import './ChatUI.css';
import ConfirmationModal from './ConfirmationModal';
import { apiFetch } from '../api';

const QUICK_COMMANDS = [
  {
    label: 'Projects',
    cmd: 'projects',
    icon: (
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></svg>
    ),
  },
  {
    label: 'My tasks',
    cmd: 'tasks',
    icon: (
      <svg viewBox="0 0 24 24"><polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
    ),
  },
  {
    label: 'Members',
    cmd: 'members',
    icon: (
      <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>
    ),
  },
  {
    label: 'Workload',
    cmd: 'workload report',
    icon: (
      <svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>
    ),
  },
  {
    label: 'Create task',
    cmd: 'create task ',
    icon: (
      <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
    ),
  },
  {
    label: 'Overdue',
    cmd: 'overdue tasks',
    icon: (
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
    ),
  },
];

const WELCOME_MESSAGE =
  "Hi! I'm your Zoho Projects assistant.\nAsk me about your projects, tasks, or team members — I'm here to help.";

const AI_AVATAR = '/avatars/ai-avatar.svg';
const USER_AVATAR = '/avatars/user-avatar.svg';

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function MessageContent({ content }) {
  const lines = content.split('\n');

  const parseInlineMarkdown = (text) => {
    const tokens = [];
    let remaining = text;
    
    // Match bold (**text**), italic (*text*), inline code (`code`)
    const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/;
    
    let keyIdx = 0;
    while (remaining) {
      const match = remaining.match(regex);
      if (!match) {
        tokens.push(remaining);
        break;
      }
      
      const matchIndex = match.index;
      if (matchIndex > 0) {
        tokens.push(remaining.substring(0, matchIndex));
      }
      
      const tokenText = match[0];
      if (tokenText.startsWith('**') && tokenText.endsWith('**')) {
        tokens.push(<strong key={keyIdx++}>{tokenText.slice(2, -2)}</strong>);
      } else if (tokenText.startsWith('*') && tokenText.endsWith('*')) {
        tokens.push(<em key={keyIdx++}>{tokenText.slice(1, -1)}</em>);
      } else if (tokenText.startsWith('`') && tokenText.endsWith('`')) {
        tokens.push(<code key={keyIdx++}>{tokenText.slice(1, -1)}</code>);
      } else {
        tokens.push(tokenText);
      }
      
      remaining = remaining.substring(matchIndex + tokenText.length);
    }
    return tokens;
  };

  return (
    <div className="message-content">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={i} className="msg-spacer" />;
        }

        // Horizontal Rule
        if (trimmed === '***' || trimmed === '---' || trimmed === '___') {
          return <hr key={i} className="msg-hr" />;
        }

        // Headers
        if (trimmed.startsWith('### ')) {
          return <h4 key={i} className="msg-h4">{parseInlineMarkdown(trimmed.slice(4))}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={i} className="msg-h3">{parseInlineMarkdown(trimmed.slice(3))}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={i} className="msg-h2">{parseInlineMarkdown(trimmed.slice(2))}</h2>;
        }

        // Bullet lists
        if (trimmed.startsWith('•') || trimmed.startsWith('- ')) {
          const contentText = trimmed.replace(/^[•\-]\s*/, '');
          return (
            <div key={i} className="msg-bullet">
              <span className="msg-bullet-dot" aria-hidden="true">•</span>
              <span>{parseInlineMarkdown(contentText)}</span>
            </div>
          );
        }

        // Default paragraph
        return <p key={i} className="msg-line">{parseInlineMarkdown(line)}</p>;
      })}
    </div>
  );
}

function MessageAvatar({ role }) {
  const src = role === 'bot' ? AI_AVATAR : USER_AVATAR;
  const alt = role === 'bot' ? 'AI assistant' : 'You';
  return (
    <div className={`msg-avatar ${role}`}>
      <img src={src} alt={alt} />
    </div>
  );
}

function ChatUI({
  sessionId,
  conversationId,
  initialWelcome,
  onConversationIdChange,
  onHistoryRefresh,
}) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [confirmationData, setConfirmationData] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const buildWelcomeMessage = () => ({
    id: 'welcome',
    role: 'bot',
    content: initialWelcome?.text || WELCOME_MESSAGE,
    time: new Date(),
  });

  useEffect(() => { scrollToBottom(); }, [messages, loading, conversationId]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;

    const loadConversation = async () => {
      setLoadingConversation(true);

      if (initialWelcome?.conversationId === conversationId) {
        setMessages([
          {
            id: 'welcome',
            role: 'bot',
            content: initialWelcome.text,
            time: new Date(),
          },
        ]);
      } else {
        setMessages([]);
      }

      try {
        const res = await apiFetch(`/chat/conversations/${conversationId}`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          const loaded = data.messages.map((m, idx) => ({
            id: `${m.timestamp}-${idx}`,
            role: m.role,
            content: m.content,
            time: new Date(m.timestamp),
          }));
          setMessages(loaded.length > 0 ? loaded : [buildWelcomeMessage()]);
        } else if (!cancelled) {
          setMessages([buildWelcomeMessage()]);
        }
      } catch {
        if (!cancelled) setMessages([buildWelcomeMessage()]);
      } finally {
        if (!cancelled) setLoadingConversation(false);
      }
    };

    loadConversation();
    return () => {
      cancelled = true;
    };
  }, [conversationId, initialWelcome]);

  const displayMessages = useMemo(() => {
    if (messages.length > 0) return messages;
    if (!conversationId && !loadingConversation) return [buildWelcomeMessage()];
    return messages;
  }, [messages, conversationId, loadingConversation, initialWelcome]);

  const addMessage = (role, content) => {
    setMessages(prev => [
      ...prev,
      { id: `${Date.now()}-${prev.length}`, role, content, time: new Date() },
    ]);
  };

  const handleSend = async (messageOverride = null, confirmationResponse = null) => {
    const msgToSend = messageOverride ?? inputValue;
    if (!msgToSend.trim() && !confirmationResponse) return;

    if (!confirmationResponse) {
      addMessage('user', msgToSend);
      setInputValue('');
    } else {
      addMessage('user', `(Confirmed: ${confirmationResponse})`);
    }

    setLoading(true);

    try {
      const response = await apiFetch('/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: messageOverride ?? inputValue,
          confirmation_response: confirmationResponse,
          conversation_id: conversationId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        addMessage('bot', `❌ Error ${response.status}: ${errData.detail || 'Request failed'}`);
        return;
      }

      const data = await response.json();
      addMessage('bot', data.bot_message);

      if (data.conversation_id && data.conversation_id !== conversationId) {
        onConversationIdChange?.(data.conversation_id);
      }
      onHistoryRefresh?.();

      if (data.requires_confirmation) {
        setConfirmationData(data.confirmation_details);
        setShowConfirmation(true);
      }
    } catch (error) {
      addMessage('bot', `❌ Network error: ${error.message}`);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleConfirmation = async (approved) => {
    setShowConfirmation(false);
    const confirmText = approved
      ? (confirmationData?.action === 'delete_task' ? 'yes to delete' : 'yes')
      : 'no';
    await handleSend('', confirmText);
  };

  const handleQuickCommand = (cmd) => {
    if (cmd.endsWith(' ')) {
      setInputValue(cmd);
      inputRef.current?.focus();
    } else {
      handleSend(cmd);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-area">
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="status-dot" />
          <div>
            <div className="chat-header-title">AI Assistant</div>
            <div className="chat-header-sub">Connected to Zoho Projects</div>
          </div>
        </div>
      </div>

      <div className="chat-messages">
        <div className="sys-msg">Today · {formatTime(new Date())}</div>

        {loadingConversation && displayMessages.length === 0 && (
          <div className="history-empty-msg">Loading conversation…</div>
        )}

        {displayMessages.map(msg => (
          <div key={msg.id} className={`msg-row ${msg.role}`}>
            <MessageAvatar role={msg.role} />
            <div className="bubble-wrap">
              <div className="bubble">
                <MessageContent content={msg.content} />
              </div>
              <span className="msg-time">{formatTime(msg.time)}</span>
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg-row bot">
            <MessageAvatar role="bot" />
            <div className="bubble-wrap">
              <div className="bubble">
                <div className="typing-indicator">
                  <span className="t-dot" /><span className="t-dot" /><span className="t-dot" />
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="quick-bar">
        {QUICK_COMMANDS.map(({ label, cmd, icon }) => (
          <button
            key={cmd}
            className="chip"
            onClick={() => handleQuickCommand(cmd)}
            disabled={loading}
          >
            {icon}{label}
          </button>
        ))}
      </div>

      <div className="input-area">
        <div className="input-wrap">
          <input
            ref={inputRef}
            type="text"
            className="chat-input"
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about projects, tasks, members…"
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={() => handleSend()}
            disabled={loading || !inputValue.trim()}
            aria-label="Send message"
          >
            <svg viewBox="0 0 24 24">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>

      {showConfirmation && (
        <ConfirmationModal
          details={confirmationData}
          onConfirm={() => handleConfirmation(true)}
          onCancel={() => handleConfirmation(false)}
        />
      )}
    </div>
  );
}

export default ChatUI;
