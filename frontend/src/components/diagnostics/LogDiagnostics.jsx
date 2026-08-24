import React, { useEffect, useState } from 'react'
import { getRawLogs } from '../../api/client'
import DiagnosticsSection from './DiagnosticsSection.jsx'
import RawLogTable from './RawLogTable.jsx'

/**
 * Owns the shared cross-filter state AND the result/log_type filters.
 * IMPORTANT: result/log_type are sent to the backend (not just applied
 * client-side) - see dashboard_router.py's raw_logs() for why: filtering
 * "Echec" client-side against an arbitrary "most recent N rows" fetch
 * badly undercounted failures compared to the map's true count. Sending
 * these as real query params makes the counts consistent.
 */
export default function LogDiagnostics({ level, id, operator }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [crossFilter, setCrossFilter] = useState(null) // { type: 'rsrpBin'|'failureCause', value } | null
  const [resultFilter, setResultFilter] = useState('ALL') // 'ALL' | 'Pass' | 'Fail'
  const [logTypeFilter, setLogTypeFilter] = useState('ALL') // 'ALL' | 'rsrp' | 'http_attempt' | 'http_failure'

  useEffect(() => {
    setCrossFilter(null)
  }, [level, id, operator])

  useEffect(() => {
    if (!level || !id) {
      setLogs([])
      return
    }
    setLoading(true)
    setError(null)
    getRawLogs({
      level, id, operator,
      result: resultFilter !== 'ALL' ? resultFilter : undefined,
      logType: logTypeFilter !== 'ALL' ? logTypeFilter : undefined,
      limit: 1500,
    })
      .then((rows) => setLogs(rows.map((r) => ({ ...r, testType: 'Outdoor' }))))
      .catch((err) => {
        console.error('raw-logs fetch failed:', err)
        setLogs([])
        setError(err.response
          ? `Erreur ${err.response.status}: ${err.response.data?.detail || 'echec de la requete'}`
          : 'Impossible de contacter le serveur.')
      })
      .finally(() => setLoading(false))
  }, [level, id, operator, resultFilter, logTypeFilter])

  const handleBinClick = (bin) => {
    setCrossFilter((prev) =>
      prev?.type === 'rsrpBin' && prev.value === bin ? null : { type: 'rsrpBin', value: bin }
    )
  }

  const handleCauseClick = (cause) => {
    setCrossFilter((prev) =>
      prev?.type === 'failureCause' && prev.value === cause ? null : { type: 'failureCause', value: cause }
    )
  }

  if (!level || !id) {
    return (
      <div className="panel" style={{ padding: 24, textAlign: 'center' }}>
        <span className="eyebrow">Selectionnez une zone geographique pour voir le diagnostic detaille</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ color: 'var(--signal-poor)', fontSize: 13, padding: '10px 14px',
                     background: 'var(--signal-poor-dim)', borderRadius: 6 }}>
        {error}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <DiagnosticsSection
        logs={logs}
        crossFilter={crossFilter}
        onBinClick={handleBinClick}
        onCauseClick={handleCauseClick}
      />
      <RawLogTable
        logs={logs}
        loading={loading}
        crossFilter={crossFilter}
        onClearFilter={() => setCrossFilter(null)}
        resultFilter={resultFilter}
        onResultFilterChange={setResultFilter}
        logTypeFilter={logTypeFilter}
        onLogTypeFilterChange={setLogTypeFilter}
      />
    </div>
  )
}
