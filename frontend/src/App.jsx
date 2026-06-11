import React, { useState, useEffect } from 'react';
import './theme.css';
import './App.css';
import LoginScreen from './components/LoginScreen';
import Sidebar from './components/Sidebar';
import ChatUI from './components/ChatUI';
import { apiFetch } from './api';

const THEME_KEY = 'zoho-chat-theme';

function getInitialTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function clearSessionCookie() {
  document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
}

async function validateSession() {
  const res = await apiFetch('/auth/me');
  return res.ok;
}

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [initialWelcome, setInitialWelcome] = useState(null);
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  useEffect(() => {
    const initAuth = async () => {
      const params = new URLSearchParams(window.location.search);
      const sessionFromUrl = params.get('session');
      if (sessionFromUrl) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      const cookie = document.cookie
        .split('; ')
        .find(row => row.startsWith('session_id='));

      if (!sessionFromUrl && !cookie) {
        setAuthChecked(true);
        return;
      }

      if (sessionFromUrl) {
        setSessionId(sessionFromUrl);
      } else if (cookie) {
        setSessionId(cookie.split('=')[1]);
      }

      try {
        const ok = await validateSession();
        if (ok) {
          setIsLoggedIn(true);
        } else {
          clearSessionCookie();
          setSessionId('');
        }
      } catch {
        clearSessionCookie();
        setSessionId('');
      } finally {
        setAuthChecked(true);
      }
    };

    initAuth();
  }, []);

  useEffect(() => {
    if (!isLoggedIn || conversationId) return;

    const initConversation = async () => {
      try {
        const newRes = await apiFetch('/chat/new', { method: 'POST' });
        if (newRes.ok) {
          const data = await newRes.json();
          setInitialWelcome({
            conversationId: data.conversation_id,
            text: data.welcome_message,
          });
          setConversationId(data.conversation_id);
          setHistoryRefresh(n => n + 1);
        }
      } catch {
        // ChatUI shows a local welcome fallback if init fails
      }
    };

    initConversation();
  }, [isLoggedIn, conversationId]);

  const handleLogout = async () => {
    try {
      await apiFetch('/auth/logout', { method: 'POST' });
    } catch {
      // Even if the server call fails, log out locally
    }
    clearSessionCookie();
    setSessionId('');
    setConversationId(null);
    setInitialWelcome(null);
    setIsLoggedIn(false);
  };

  const handleNewConversation = async () => {
    const res = await apiFetch('/chat/new', { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    setInitialWelcome({
      conversationId: data.conversation_id,
      text: data.welcome_message,
    });
    setConversationId(data.conversation_id);
    setHistoryRefresh(n => n + 1);
  };

  const handleSelectConversation = (id) => {
    setInitialWelcome(null);
    setConversationId(id);
  };

  const handleHistoryRefresh = () => {
    setHistoryRefresh(n => n + 1);
  };

  if (!authChecked) {
    return (
      <div className="app">
        <div className="auth-loading">Loading…</div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="app">
        <LoginScreen />
      </div>
    );
  }

  return (
    <div className="app logged-in">
      <div className="app-shell">
        <Sidebar
          onLogout={handleLogout}
          activeConversationId={conversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          historyRefresh={historyRefresh}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
        <ChatUI
          sessionId={sessionId}
          conversationId={conversationId}
          initialWelcome={initialWelcome}
          onConversationIdChange={setConversationId}
          onHistoryRefresh={handleHistoryRefresh}
        />
      </div>
    </div>
  );
}

export default App;
