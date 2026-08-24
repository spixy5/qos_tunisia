import React, { useMemo } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const PALETTE = ['var(--signal-poor)', 'var(--signal-mid)', '#c77dff', '#5b8def', '#f472b6', '#facc15', 'var(--text-faint)']
const MAX_SLICES = 6 // beyond this, remaining causes are grouped into "Autres"

export default function HttpFailureDonutChart({ logs, activeFilter, onCauseClick }) {
  const data = useMemo(() => {
    const counts = {}
    for (const log of logs) {
      if (log.logType !== 'http_failure') continue
      const cause = log.httpStatusLabel || 'Cause inconnue'
      counts[cause] = (counts[cause] || 0) + 1
    }
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1])
    const top = sorted.slice(0, MAX_SLICES)
    const rest = sorted.slice(MAX_SLICES)
    const restTotal = rest.reduce((s, [, v]) => s + v, 0)

    const slices = top.map(([cause, value], i) => ({ cause, value, color: PALETTE[i % PALETTE.length] }))
    if (restTotal > 0) slices.push({ cause: 'Autres causes', value: restTotal, color: PALETTE[PALETTE.length - 1] })
    return slices
  }, [logs])

  const total = data.reduce((s, d) => s + d.value, 0)
  const isActive = (cause) => activeFilter?.type === 'failureCause' && activeFilter.value === cause

  return (
    <div className="panel" style={{ padding: 20 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Repartition des echecs HTTP (cause reelle)</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Cause exacte rapportee par le log (failure_cause), sans regroupement artificiel.
        Cliquez une categorie pour filtrer le tableau.
      </div>
      {total === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 260, color: 'var(--text-faint)', fontSize: 13 }}>
          Aucun echec HTTP dans cette zone
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
