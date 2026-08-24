import React, { useState } from 'react'
import { recomputeKpis } from '../api/client'

export default function RecomputeKpisPanel() {
  const [status, setStatus] = useState(null)
  const [running, setRunning] = useState(false)

  const run = async () => {
    setRunning(true)
    setStatus(null)
    try {
      const res = await recomputeKpis()
      setStatus(`Termine : ${res.combinations} combinaisons secteur/operateur/techno, ${res.kpi_rows_upserted} lignes KPI mises a jour.`)
    } catch (err) {
      setStatus(`Erreur : ${err.response?.data?.detail || err.message}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="panel" style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Recalculer les KPI</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
          A utiliser apres avoir change un seuil, ou si les resultats semblent obsoletes (sans avoir a re-importer un fichier).
        </div>
      </div>
      <button className="btn-primary" onClick={run} disabled={running}>
        {running ? 'Calcul en cours...' : 'Recalculer maintenant'}
      </button>
      {status && (
        <div style={{ fontSize: 12, color: status.startsWith('Erreur') ? 'var(--signal-poor)' : 'var(--signal-good)', maxWidth: 260 }}>
          {status}
        </div>
      )}
    </div>
  )
}
