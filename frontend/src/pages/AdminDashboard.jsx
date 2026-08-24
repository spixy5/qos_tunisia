import React, { useState } from 'react'
import FileUploader from '../components/FileUploader.jsx'
import AdminSettingsForm from '../components/AdminSettingsForm.jsx'
import AdminDeleteTools from '../components/AdminDeleteTools.jsx'
import RecomputeKpisPanel from '../components/RecomputeKpisPanel.jsx'

const TABS = [
  { id: 'upload', label: 'Import de fichiers' },
  { id: 'settings', label: 'Parametres KPI' },
  { id: 'delete', label: 'Gestion des donnees' },
]

export default function AdminDashboard() {
  const [tab, setTab] = useState('upload')

  return (
    <div style={{ maxWidth: 900, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Administration</h1>
        <p style={{ color: 'var(--text-muted)', margin: 0 }}>
          Import, parametrage et gestion des donnees de mesure.
        </p>
      </div>

      <RecomputeKpisPanel />

      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: 'none',
              border: 'none',
              padding: '10px 16px',
              fontSize: 13,
              fontWeight: 500,
              color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'upload' && <FileUploader />}
      {tab === 'settings' && <AdminSettingsForm />}
      {tab === 'delete' && <AdminDeleteTools />}
    </div>
  )
}
