import React, { useState, useRef, useEffect } from 'react';
import './ChatUI.css';
import ConfirmationModal from './ConfirmationModal';

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

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function cleanText(text) {
  return text.replace(/\*\*/g, '');
}

function ChatUI({ sessionId }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [confirmationData, setConfirmationData] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages, loading]);

  // Fetch welcome message on mount
  useEffect(() => {
    const fetchWelcome = async () => {
      try {
        const res = await fetch('http://localhost:8000/chat/welcome', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          addMessage('bot', data.bot_message);
        } else {
          addMessage('bot', "👋 Hi! I'm your Zoho Projects assistant.\nAsk me about your projects, tasks, or team members.");
        }
      } catch {
        addMessage('bot', "👋 Hi! I'm your Zoho Projects assistant.\nAsk me about your projects, tasks, or team members.");
      }
    };
    fetchWelcome();
  }, []);

  const addMessage = (role, content) => {
    setMessages(prev => [...prev, { role, content, time: new Date() }]);
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
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          message: messageOverride ?? inputValue,
          confirmation_response: confirmationResponse,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        addMessage('bot', `❌ Error ${response.status}: ${errData.detail || 'Request failed'}`);
        return;
      }

      const data = await response.json();
      addMessage('bot', data.bot_message);

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
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="status-dot" />
          <div>
            <div className="chat-header-title">AI Assistant</div>
            <div className="chat-header-sub">Connected to Zoho Projects</div>
          </div>
        </div>
        <div className="chat-header-actions">
          <button className="icon-btn" title="Search">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
          </button>
          <button className="icon-btn" title="Settings">
            <svg viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        <div className="sys-msg">Today · {formatTime(new Date())}</div>

        {messages.map((msg, idx) => (
          <div key={idx} className={`msg-row ${msg.role}`}>
            <div className={`msg-avatar ${msg.role}`}>
              {msg.role === 'bot' ? 'AI' : 'AR'}
            </div>
            <div className="bubble-wrap">
              <div className="bubble">
                {cleanText(msg.content).split('\n').map((line, i, arr) => (
                  <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
                ))}
              </div>
              <span className="msg-time">{formatTime(msg.time)}</span>
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg-row bot">
            <div className="msg-avatar bot">AI</div>
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

      {/* Quick chips */}
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

      {/* Input */}
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
          <button className="attach-btn" title="Attach file">
            <svg viewBox="0 0 24 24">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
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
