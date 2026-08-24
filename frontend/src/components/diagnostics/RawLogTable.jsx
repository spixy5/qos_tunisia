import React, { useMemo, useState } from 'react'
import { rsrpBin } from './RsrpHistogramChart.jsx'

const PAGE_SIZE_OPTIONS = [10, 15, 25]

function rsrpBadgeColor(rsrp) {
  if (rsrp > -85) return 'var(--signal-good)'
  if (rsrp >= -100) return 'var(--signal-mid)'
  return 'var(--signal-poor)'
}

function statusBadgeColor(row) {
  if (row.logType === 'http_attempt') return 'var(--signal-good)'
  if (row.logType === 'http_failure') return 'var(--signal-poor)'
  return 'var(--text-faint)'
}

function Badge({ color, children }) {
  return (
    <span
      style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
        color, background: `${color}22`, border: `1px solid ${color}55`,
      }}
    >
      {children}
    </span>
  )
}

function exportToCsv(rows) {
  const headers = ['Timestamp', 'Operateur', 'Secteur', 'Type de test', 'Type de log', 'RSRP (dBm)', 'Statut / Cause HTTP', 'Resultat']
  const csvRows = rows.map((r) => [
    r.timestamp, r.operator, r.secteurName || '', r.testType,
    r.logType === 'rsrp' ? 'RSRP' : r.logType === 'http_attempt' ? 'HTTP succes' : 'HTTP echec',
    r.rsrp ?? '', r.httpStatusLabel || '', r.result,
  ])
  const csv = [headers, ...csvRows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `qos_logs_export_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * NOTE: resultFilter and logTypeFilter are CONTROLLED props (owned by
 * LogDiagnostics, sent to the backend as real query params) - not local
 * state filtered client-side. See LogDiagnostics.jsx for why: client-side
 * filtering of a capped "most recent N" fetch badly undercounted
 * failures vs. the map's true count. operatorFilter and search stay
 * local/client-side since they only ever narrow an already-correct set.
 */
export default function RawLogTable({
  logs, loading, crossFilter, onClearFilter,
  resultFilter, onResultFilterChange, logTypeFilter, onLogTypeFilterChange,
}) {
  const [search, setSearch] = useState('')
  const [operatorFilter, setOperatorFilter] = useState('ALL')
  const [sortKey, setSortKey] = useState('timestamp')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const filtered = useMemo(() => {
    let rows = logs

    if (crossFilter?.type === 'rsrpBin') {
      rows = rows.filter((r) => r.rsrp !== null && r.rsrp !== undefined && rsrpBin(r.rsrp) === crossFilter.value)
    } else if (crossFilter?.type === 'failureCause') {
      rows = rows.filter((r) => r.httpStatusLabel === crossFilter.value)
    }

    if (operatorFilter !== 'ALL') rows = rows.filter((r) => r.operator === operatorFilter)

    if (search.trim()) {
      const q = search.trim().toLowerCase()
      rows = rows.filter(
        (r) =>
          (r.secteurName || '').toLowerCase().includes(q) ||
          r.operator.toLowerCase().includes(q) ||
          (r.httpStatusLabel || '').toLowerCase().includes(q)
      )
    }

    const sorted = [...rows].sort((a, b) => {
      let cmp = 0
      if (sortKey === 'timestamp') cmp = a.timestamp < b.timestamp ? -1 : a.timestamp > b.timestamp ? 1 : 0
      else if (sortKey === 'rsrp') cmp = (a.rsrp ?? -999) - (b.rsrp ?? -999)
      else if (sortKey === 'result') cmp = a.result.localeCompare(b.result)
      return sortDir === 'asc' ? cmp : -cmp
    })

    return sorted
  }, [logs, crossFilter, operatorFilter, search, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const pageRows = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
    setPage(1)
  }

  const SortHeader = ({ label, sortKeyName }) => (
    <th
      onClick={() => toggleSort(sortKeyName)}
      style={{ fontFamily: 'var(--font-body)', cursor: 'pointer', userSelect: 'none' }}
    >
      {label} {sortKey === sortKeyName ? (sortDir === 'asc' ? '↑' : '↓') : ''}
    </th>
  )

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div className="eyebrow">
          Journal detaille des tests ({filtered.length}{loading ? '...' : ''})
        </div>
        <button className="btn-ghost" onClick={() => exportToCsv(filtered)}>
          Exporter en CSV
        </button>
      </div>

      {crossFilter && (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '8px 12px',
            background: 'var(--accent-soft)', borderRadius: 6, fontSize: 12, color: 'var(--text-primary)',
          }}
        >
          Filtre actif : <strong>{crossFilter.type === 'rsrpBin' ? 'RSRP' : 'Cause HTTP'} = {crossFilter.value}</strong>
          <button className="btn-ghost" onClick={onClearFilter} style={{ padding: '2px 8px', fontSize: 11 }}>
            Effacer
          </button>
        </div>
      )}

      <div className="panel" style={{ padding: 16, marginBottom: 12, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Recherche globale (secteur, operateur, cause...)"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          style={{ flex: 1, minWidth: 220 }}
        />
        <select value={operatorFilter} onChange={(e) => { setOperatorFilter(e.target.value); setPage(1) }}>
          <option value="ALL">Tous les operateurs</option>
          <option value="TT">Tunisie Telecom</option>
          <option value="OO">Ooredoo</option>
          <option value="OR">Orange</option>
        </select>
        <select value={logTypeFilter} onChange={(e) => { onLogTypeFilterChange(e.target.value); setPage(1) }}>
          <option value="ALL">Tous les types de log</option>
          <option value="rsrp">RSRP</option>
          <option value="http_attempt">HTTP succes</option>
          <option value="http_failure">HTTP echec</option>
        </select>
        <select value={resultFilter} onChange={(e) => { onResultFilterChange(e.target.value); setPage(1) }}>
          <option value="ALL">Tous les resultats</option>
          <option value="Pass">Reussi</option>
          <option value="Fail">Echec</option>
        </select>
      </div>

      <div className="panel" style={{ overflow: 'auto' }}>
        <table>
          <thead>
            <tr>
              <SortHeader label="Horodatage" sortKeyName="timestamp" />
              <th style={{ fontFamily: 'var(--font-body)' }}>Operateur</th>
              <th style={{ fontFamily: 'var(--font-body)' }}>Secteur</th>
              <th style={{ fontFamily: 'var(--font-body)' }}>Type de test</th>
              <SortHeader label="RSRP" sortKeyName="rsrp" />
              <th style={{ fontFamily: 'var(--font-body)' }}>Statut / Cause HTTP</th>
              <SortHeader label="Resultat" sortKeyName="result" />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-faint)', fontFamily: 'var(--font-body)' }}>
                Chargement...
              </td></tr>
            )}
            {!loading && pageRows.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-faint)', fontFamily: 'var(--font-body)' }}>
                Aucun log ne correspond aux filtres actuels
              </td></tr>
            )}
            {!loading && pageRows.map((r) => (
              <tr key={r.id}>
                <td>{r.timestamp}</td>
                <td style={{ fontFamily: 'var(--font-body)' }}>{r.operator}</td>
                <td style={{ fontFamily: 'var(--font-body)' }}>{r.secteurName || '—'}</td>
                <td style={{ fontFamily: 'var(--font-body)' }}>{r.testType}</td>
                <td>{r.rsrp !== null && r.rsrp !== undefined
                  ? <Badge color={rsrpBadgeColor(r.rsrp)}>{r.rsrp} dBm</Badge>
                  : <span style={{ color: 'var(--text-faint)' }}>—</span>}
                </td>
                <td style={{ fontSize: 12 }}>{r.httpStatusLabel
                  ? <Badge color={statusBadgeColor(r)}>{r.httpStatusLabel}</Badge>
                  : <span style={{ color: 'var(--text-faint)' }}>—</span>}
                </td>
                <td><Badge color={r.result === 'Pass' ? 'var(--signal-good)' : 'var(--signal-poor)'}>{r.result === 'Pass' ? 'Reussi' : 'Echec'}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          Lignes par page:
          <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1) }}>
            {PAGE_SIZE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="btn-ghost" disabled={currentPage <= 1} onClick={() => setPage((p) => p - 1)}>Precedent</button>
          Page {currentPage} / {totalPages}
          <button className="btn-ghost" disabled={currentPage >= totalPages} onClick={() => setPage((p) => p + 1)}>Suivant</button>
        </div>
      </div>
    </div>
  )
}
