import React, { useMemo } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

// NOTE: the source export only ever records a binary "Test status"
// (Success / Fail - see parsers.py:_normalize_status). There is no
// per-attempt failure-cause field anywhere upstream (checked the raw
// exports and the DB: test_status is always exactly "Success" or
// "Failure"), so a "cause breakdown" pie can only ever render one
// slice. This chart now shows the real signal that exists - the
// Succes/Echec split of HTTP attempts - instead of promising a
// cause-level detail the data can't back up.
const COLOR_BY_LABEL = {
  Succes: 'var(--signal-good)',
  Failure: 'var(--signal-poor)',
}
const FALLBACK_PALETTE = ['var(--signal-mid)', '#c77dff', '#5b8def', '#facc15', 'var(--text-faint)']

export default function HttpFailureDonutChart({ logs, activeFilter, onCauseClick }) {
  const data = useMemo(() => {
    const counts = {}
    for (const log of logs) {
      if (log.logType !== 'http_attempt' && log.logType !== 'http_failure') continue
      const label = log.httpStatusLabel || 'Statut inconnu'
      counts[label] = (counts[label] || 0) + 1
    }
    let fallbackIdx = 0
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([label, value]) => ({
        cause: label,
        value,
        color: COLOR_BY_LABEL[label] || FALLBACK_PALETTE[fallbackIdx++ % FALLBACK_PALETTE.length],
      }))
  }, [logs])

  const total = data.reduce((s, d) => s + d.value, 0)
  const isActive = (cause) => activeFilter?.type === 'failureCause' && activeFilter.value === cause

  return (
    <div className="panel" style={{ padding: 20 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Repartition des tests HTTP (Succes / Echec)</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Le statut brut du test (test_status) ne distingue que Succes/Echec - aucune cause
        detaillee n'est fournie par l'export. Cliquez une categorie pour filtrer le tableau.
      </div>
      {total === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 260, color: 'var(--text-faint)', fontSize: 13 }}>
          Aucun test HTTP dans cette zone
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="cause"
              innerRadius={55}
              outerRadius={90}
              paddingAngle={2}
              cursor="pointer"
              onClick={(d) => d.cause !== 'Autres causes' && onCauseClick(d.cause)}
            >
              {data.map((d) => (
                <Cell key={d.cause} fill={d.color} fillOpacity={isActive(d.cause) || !activeFilter ? 1 : 0.3} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
              formatter={(value, name) => [`${value} (${((value / total) * 100).toFixed(1)}%)`, name]}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)' }}
              formatter={(value) => <span style={{ color: 'var(--text-muted)' }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}