import React, { useState } from 'react';
import './Sidebar.css';

const NAV_ITEMS = [
  {
    label: 'Chat assistant', key: 'chat',
    icon: <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>,
  },
  {
    label: 'Projects', key: 'projects', badge: '4',
    icon: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></>,
  },
  {
    label: 'My tasks', key: 'tasks', badge: '12',
    icon: <><polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>,
  },
  {
    label: 'Members', key: 'members',
    icon: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>,
  },
  {
    label: 'Reports', key: 'reports',
    icon: <><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></>,
  },
];

const RECENT_ITEMS = ['Sprint 6 — Website', 'Mobile App v2', 'API Integration'];

function Icon({ children }) {
  return (
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      {children}
    </svg>
  );
}

function Sidebar({ onLogout }) {
  const [active, setActive] = useState('chat');

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-mark">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <span className="logo-text">Zoho Projects</span>
      </div>

      {/* Main nav */}
      <div className="sidebar-label">Workspace</div>
      {NAV_ITEMS.map(item => (
        <div
          key={item.key}
          className={`nav-item${active === item.key ? ' active' : ''}`}
          onClick={() => setActive(item.key)}
        >
          <Icon>{item.icon}</Icon>
          {item.label}
          {item.badge && <span className="nav-badge">{item.badge}</span>}
        </div>
      ))}

      <div className="sidebar-spacer" />

      {/* Recent */}
      <div className="sidebar-label" style={{ marginTop: 4 }}>Recent</div>
      {RECENT_ITEMS.map(name => (
        <div key={name} className="recent-item">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style={{ width: 14, height: 14, flexShrink: 0, stroke: 'currentColor', fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          {name}
        </div>
      ))}

      <div className="sidebar-spacer" />

      {/* User */}
      <div className="sidebar-user">
        <div className="user-avatar">AR</div>
        <div className="user-info">
          <div className="user-info-name">Aravind</div>
          <div className="user-info-role">Developer</div>
        </div>
        <button className="logout-btn" onClick={onLogout} title="Log out">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
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
