import React, { useState } from 'react';
import './LoginScreen.css';

function LoginScreen({ onLogin }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('http://localhost:8000/auth/login', {
        method: 'GET',
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          window.location.href = data.auth_url;
        } else {
          onLogin?.();
        }
      } else {
        setError('Unable to reach the server. Make sure the backend is running.');
      }
    } catch {
      setError('Connection failed. Check that the backend is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-mark">
            <svg viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <span className="login-logo-text">Zoho Projects</span>
        </div>

        <h1 className="login-heading">Welcome back</h1>
        <p className="login-sub">Sign in with your Zoho account to continue to the project assistant.</p>

        <button className="login-btn" onClick={handleLogin} disabled={loading}>
          {loading ? (
            <>Redirecting…</>
          ) : (
            <>
              <svg viewBox="0 0 24 24">
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <polyline points="10 17 15 12 10 7" />
                <line x1="15" y1="12" x2="3" y2="12" />
              </svg>
              Sign in with Zoho
            </>
          )}
        </button>

        {error && <div className="login-error">{error}</div>}

        <div className="login-divider">or</div>
        <p className="login-note">Your session is secured via Zoho OAuth 2.0.<br />We never store your credentials.</p>
      </div>
    </div>
  );
}

export default LoginScreen;
