import React, { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const BIN_ORDER = ['Excellent', 'Fair', 'Poor']

export function rsrpBin(rsrp) {
  if (rsrp > -85) return 'Excellent'
  if (rsrp >= -100) return 'Fair'
  return 'Poor'
}

export default function RsrpHistogramChart({ logs, activeFilter, onBinClick }) {
  const data = useMemo(() => {
    const counts = { Excellent: { pass: 0, fail: 0 }, Fair: { pass: 0, fail: 0 }, Poor: { pass: 0, fail: 0 } }
    for (const log of logs) {
      if (log.rsrp === null || log.rsrp === undefined) continue // HTTP-only rows carry no RSRP reading
      const bin = rsrpBin(log.rsrp)
      if (log.result === 'Pass') counts[bin].pass += 1
      else counts[bin].fail += 1
    }
    return BIN_ORDER.map((bin) => ({ bin, ...counts[bin] }))
  }, [logs])

  const isBinActive = (bin) => activeFilter?.type === 'rsrpBin' && activeFilter.value === bin

  return (
    <div className="panel" style={{ padding: 20 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Histogramme RSRP</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Isole si les echecs viennent d'une mauvaise couverture radio ou d'un probleme applicatif.
        Cliquez une barre pour filtrer le tableau.
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" />
          <XAxis dataKey="bin" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
          <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
          <Tooltip
            contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: 'var(--text-primary)' }}
          />
          <Bar dataKey="pass" name="Reussi (TAI)" stackId="a" fill="var(--signal-good)"
               cursor="pointer" onClick={(d) => onBinClick(d.bin)}>
            {data.map((d) => (
              <Cell key={d.bin} fillOpacity={isBinActive(d.bin) || !activeFilter ? 1 : 0.35} />
            ))}
          </Bar>
          <Bar dataKey="fail" name="Echec (TAI)" stackId="a" fill="var(--signal-poor)" radius={[4, 4, 0, 0]}
               cursor="pointer" onClick={(d) => onBinClick(d.bin)}>
            {data.map((d) => (
              <Cell key={d.bin} fillOpacity={isBinActive(d.bin) || !activeFilter ? 1 : 0.35} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
