import React from 'react'
import { colorForValue } from './SignalMark.jsx'

const OPERATOR_LABELS = { TT: 'Tunisie Telecom', OO: 'Ooredoo', OR: 'Orange' }

export default function OperatorComparisonTable({ rows, scope }) {
  if (!scope) {
    return (
      <div className="panel" style={{ padding: 24 }}>
        <span className="eyebrow">Selectionnez une zone geographique</span>
      </div>
    )
  }

  if (!rows || rows.length === 0) {
    return (
      <div className="panel" style={{ padding: 24 }}>
        <span className="eyebrow">Aucune donnee KPI pour cette zone</span>
      </div>
    )
  }

  return (
    <div className="panel" style={{ overflow: 'hidden' }}>
      <table>
        <thead>
          <tr>
            <th style={{ fontFamily: 'var(--font-body)' }}>Operateur</th>
            <th style={{ fontFamily: 'var(--font-body)' }}>Techno</th>
            <th>TAO</th>
            <th>TAI</th>
            <th>TD</th>
            <th>PCPS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td className="mono" style={{ fontFamily: 'var(--font-body)', fontWeight: 500 }}>
                {OPERATOR_LABELS[row.operator] || row.operator}
              </td>
              <td style={{ fontFamily: 'var(--font-body)', color: 'var(--text-muted)' }}>
                {row.technology || '—'}
              </td>
              <KpiCell value={row.tao} />
              <KpiCell value={row.tai} />
              <KpiCell value={row.td} pending={row.td === null} />
              <KpiCell value={row.pcps} pending={row.pcps === null} bold />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function KpiCell({ value, pending, bold }) {
  if (value === null || value === undefined) {
    return <td style={{ color: 'var(--text-faint)' }}>{pending ? 'en attente' : '—'}</td>
  }
  return (
    <td style={{ color: colorForValue(value), fontWeight: bold ? 600 : 500 }}>
      {value}%
    </td>
  )
}
