import React, { useState, useEffect } from 'react';
import './App.css';
import LoginScreen from './components/LoginScreen';
import Sidebar from './components/Sidebar';
import ChatUI from './components/ChatUI';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [sessionId, setSessionId] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const session = params.get('session');
    if (session) {
      setSessionId(session);
      setIsLoggedIn(true);
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }
    const cookie = document.cookie
      .split('; ')
      .find(row => row.startsWith('session_id='));
    if (cookie) {
      setSessionId(cookie.split('=')[1]);
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogout = async () => {
    try {
      await fetch('http://localhost:8000/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch {}
    document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    setSessionId('');
    setIsLoggedIn(false);
  };

  if (!isLoggedIn) {
    return (
      <div className="app">
        <LoginScreen onLogin={() => setIsLoggedIn(true)} />
      </div>
    );
  }

  return (
    <div className="app logged-in">
      <div className="app-shell">
        <Sidebar onLogout={handleLogout} />
        <ChatUI sessionId={sessionId} />
      </div>
    </div>
  );
}

export default App;
