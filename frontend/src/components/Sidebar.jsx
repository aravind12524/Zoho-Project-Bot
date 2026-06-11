import React, { useState, useEffect, useMemo, useRef } from 'react';
import './Sidebar.css';
import { apiFetch } from '../api';

function isSameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function groupConversations(conversations) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups = { Today: [], Yesterday: [], Earlier: [] };

  conversations.forEach(conv => {
    const date = new Date(conv.updated_at);
    if (isSameDay(date, today)) groups.Today.push(conv);
    else if (isSameDay(date, yesterday)) groups.Yesterday.push(conv);
    else groups.Earlier.push(conv);
  });

  return groups;
}

function Sidebar({
  onLogout,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  historyRefresh = 0,
  theme = 'light',
  onToggleTheme,
}) {
  const [conversations, setConversations] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const editInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const fetchHistory = async () => {
      setLoading(true);
      try {
        const res = await apiFetch('/chat/history');
        if (!cancelled && res.ok) {
          const data = await res.json();
          setConversations(data.conversations || []);
        }
      } catch {
        // Sidebar stays usable even if history fails to load
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchHistory();
    return () => {
      cancelled = true;
    };
  }, [historyRefresh]);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter(c => c.title.toLowerCase().includes(q));
  }, [conversations, search]);

  const grouped = useMemo(() => groupConversations(filtered), [filtered]);

  const handleNewConversation = async () => {
    setCreating(true);
    try {
      await onNewConversation();
    } finally {
      setCreating(false);
    }
  };

  const startRename = (conv, e) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditTitle('');
  };

  const saveRename = async (convId) => {
    const trimmed = editTitle.trim();
    if (!trimmed) {
      cancelRename();
      return;
    }

    const existing = conversations.find(c => c.id === convId);
    if (existing && existing.title === trimmed) {
      cancelRename();
      return;
    }

    try {
      const res = await apiFetch(`/chat/conversations/${convId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: trimmed }),
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(prev =>
          prev.map(c => (c.id === convId ? { ...c, title: data.title, updated_at: data.updated_at } : c))
        );
      }
    } catch {
      // Keep local edit state cleared even if save fails
    } finally {
      cancelRename();
    }
  };

  const handleRenameKeyDown = (e, convId) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveRename(convId);
    } else if (e.key === 'Escape') {
      cancelRename();
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <svg viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <span className="logo-text">Zoho Projects</span>
        </div>

        <button
          className="new-chat-btn"
          onClick={handleNewConversation}
          disabled={creating}
        >
          <svg viewBox="0 0 24 24">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          {creating ? 'Starting…' : 'New conversation'}
        </button>

        <div className="history-search">
          <svg viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Search conversations"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="history-list">
        {loading && <div className="history-empty">Loading history…</div>}

        {!loading && filtered.length === 0 && (
          <div className="history-empty">
            {search ? 'No matching conversations' : 'No conversations yet'}
          </div>
        )}

        {Object.entries(grouped).map(([label, items]) =>
          items.length > 0 ? (
            <div key={label} className="history-group">
              <div className="history-group-label">{label}</div>
              {items.map(conv => (
                editingId === conv.id ? (
                  <div key={conv.id} className="history-item editing">
                    <input
                      ref={editInputRef}
                      className="history-rename-input"
                      value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      onBlur={() => saveRename(conv.id)}
                      onKeyDown={e => handleRenameKeyDown(e, conv.id)}
                      aria-label="Rename conversation"
                    />
                  </div>
                ) : (
                  <button
                    key={conv.id}
                    type="button"
                    className={`history-item${activeConversationId === conv.id ? ' active' : ''}`}
                    onClick={() => onSelectConversation(conv.id)}
                    onDoubleClick={e => startRename(conv, e)}
                    title={`${conv.title} — double-click to rename`}
                  >
                    <svg viewBox="0 0 24 24">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                    <span>{conv.title}</span>
                  </button>
                )
              ))}
            </div>
          ) : null
        )}
      </div>

      <div className="sidebar-footer">
        <button
          className="footer-icon-btn theme-toggle"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? (
            <svg viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
        <button className="footer-icon-btn logout" onClick={onLogout} title="Log out">
          <svg viewBox="0 0 24 24">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
