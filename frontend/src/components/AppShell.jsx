import React from 'react'
import { useTheme } from '../context/ThemeContext.jsx'
import SignalMark from './SignalMark.jsx'

export default function AppShell({ children, view, onViewChange }) {
  const { theme, toggleTheme } = useTheme()

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <aside
        style={{
          width: 220,
          borderRight: '1px solid var(--border)',
          background: 'var(--bg-panel)',
          display: 'flex',
          flexDirection: 'column',
          padding: '20px 16px',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32, paddingLeft: 4 }}>
          <SignalMark bars={4} size={22} color="var(--signal-good)" />
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15, lineHeight: 1 }}>
              QoS Tunisie
            </div>
            <div className="eyebrow" style={{ marginTop: 2 }}>Supervision reseaux mobiles</div>
          </div>
        </div>

        <button
          className="btn-ghost"
          onClick={toggleTheme}
          style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}
        >
          {theme === 'dark' ? '☀ Mode clair' : '🌙 Mode sombre'}
        </button>
      </aside>

      <main style={{ flex: 1, padding: '28px 36px', overflow: 'auto', position: 'relative', height: '100vh' }}>
        <div
          style={{
            position: 'absolute', top: 20, right: 36, zIndex: 2000,
            display: 'flex', gap: 4, background: 'var(--bg-panel)',
            border: '1px solid var(--border)', borderRadius: 8, padding: 4,
          }}
        >
          <ViewButton active={view === 'user'} onClick={() => onViewChange('user')} label="Supervision" />
          <ViewButton active={view === 'admin'} onClick={() => onViewChange('admin')} label="Admin" />
        </div>

        {children}
      </main>
    </div>
  )
}

function ViewButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? 'var(--accent-soft)' : 'transparent',
        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
        border: 'none', borderRadius: 6, padding: '8px 16px', fontSize: 13, fontWeight: 500,
      }}
    >
      {label}
    </button>
  )
}
