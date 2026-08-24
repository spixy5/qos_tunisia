import React, { useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import AdminDashboard from './pages/AdminDashboard.jsx'
import UserDashboard from './pages/UserDashboard.jsx'
import AppShell from './components/AppShell.jsx'

function Root() {
  const { ready, isAuthenticated, authError } = useAuth()
  const [view, setView] = useState('user') // 'user' | 'admin'

  if (!ready) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                     background: 'var(--bg)', color: 'var(--text-muted)', fontSize: 13 }}>
        Connexion au serveur...
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                     background: 'var(--bg)', color: 'var(--signal-poor)', fontSize: 13, textAlign: 'center',
                     padding: 24, flexDirection: 'column', gap: 8 }}>
        <div>{authError || 'Connexion impossible.'}</div>
        <div style={{ color: 'var(--text-muted)' }}>Verifiez que le serveur backend (uvicorn) est demarre.</div>
      </div>
    )
  }

  return (
    <AppShell view={view} onViewChange={setView}>
      {view === 'admin' ? <AdminDashboard /> : <UserDashboard />}
    </AppShell>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  )
}
