import React, { useState } from 'react'
import { uploadFile } from '../api/client'

const LOG_TYPES = [
  { value: 'rsrp', label: 'RSRP (mesures signal)' },
  { value: 'http_attempt', label: 'HTTP - tentatives' },
  
]
const OPERATORS = [
  { value: 'TT', label: 'Tunisie Telecom' },
  { value: 'OO', label: 'Ooredoo' },
  { value: 'OR', label: 'Orange' },
]
const TECHNOLOGIES = ['4G', '4G_3G', '5G']
const FREE_TECH_VALUE = 'Unspecified'

export default function FileUploader({ onUploaded }) {
  const [file, setFile] = useState(null)
  const [logType, setLogType] = useState('rsrp')
  const [operator, setOperator] = useState('TT')
  const [technology, setTechnology] = useState('4G')
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)

  const handleLogTypeChange = (value) => {
    setLogType(value)
    if (value !== 'rsrp' && technology === FREE_TECH_VALUE) {
      setTechnology('4G')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setStatus(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('log_type', logType)
      formData.append('operator', operator)
      formData.append('technology', technology)

      const result = await uploadFile(formData)
      setStatus(result)
      onUploaded?.(result)
      setFile(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Echec de l\'import.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="panel" style={{ padding: 24 }}>
      <div className="eyebrow" style={{ marginBottom: 16 }}>Importer un fichier de mesures</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
        <Field label="Type de test">
          <select value={logType} onChange={(e) => handleLogTypeChange(e.target.value)} style={{ width: '100%' }}>
            {LOG_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </Field>
        <Field label="Operateur">
          <select value={operator} onChange={(e) => setOperator(e.target.value)} style={{ width: '100%' }}>
            {OPERATORS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Field>
        <Field label="Technologie">
          <select value={technology} onChange={(e) => setTechnology(e.target.value)} style={{ width: '100%' }}>
            {TECHNOLOGIES.map((t) => <option key={t} value={t}>{t}</option>)}
            {logType === 'rsrp' && <option value={FREE_TECH_VALUE}>Libre (technologie non specifiee)</option>}
          </select>
        </Field>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <input
          type="file"
          accept=".xlsx,.csv"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          style={{ flex: 1 }}
        />
        <button className="btn-primary" onClick={handleUpload} disabled={!file || uploading}>
          {uploading ? 'Import en cours...' : 'Importer'}
        </button>
      </div>

      {error && <div style={{ color: 'var(--signal-poor)', fontSize: 13, marginTop: 12 }}>{error}</div>}

      {status && (
        <div style={{ marginTop: 16, padding: 14, background: 'var(--bg-panel-raised)', borderRadius: 6, fontSize: 13 }}>
          <div style={{ color: 'var(--signal-good)', fontWeight: 600, marginBottom: 6 }}>
            Import reussi — {status.original_filename}
          </div>
          <div className="mono" style={{ color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.8 }}>
            Lignes brutes: {status.row_count_raw} · Lignes nettoyees: {status.row_count_clean}<br />
            Archive: {status.archive_path || 'non archive (secteur non resolu)'}
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label>
      <div className="eyebrow" style={{ marginBottom: 6 }}>{label}</div>
      {children}
    </label>
  )
}
