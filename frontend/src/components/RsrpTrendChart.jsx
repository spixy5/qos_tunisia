import React, { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { getRsrpTrend } from '../api/client'

export default function RsrpTrendChart({ level, id, operator }) {
  const [bucket, setBucket] = useState('hour')
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!level || !id) { setData([]); return }
    setLoading(true)
    setError(null)
    getRsrpTrend({ level, id, operator, bucket })
      .then(setData)
      .catch((err) => {
        console.error('rsrp-trend fetch failed:', err)
        setData([])
        setError('Impossible de charger la tendance RSRP.')
      })
      .finally(() => setLoading(false))
  }, [level, id, operator, bucket])

  return (
    <div className="panel" style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="eyebrow">Tendance RSRP</div>
        <div style={{ display: 'flex', gap: 4 }}>
          <BucketButton active={bucket === 'hour'} onClick={() => setBucket('hour')} label="Par heure" />
          <BucketButton active={bucket === 'day'} onClick={() => setBucket('day')} label="Par jour" />
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        RSRP moyen (dBm) dans la zone selectionnee, dans le temps.
      </div>

      {!level || !id ? (
        <EmptyState text="Selectionnez une zone geographique" />
      ) : loading ? (
        <EmptyState text="Chargement..." />
      ) : error ? (
        <EmptyState text={error} color="var(--signal-poor)" />
      ) : data.length === 0 ? (
        <EmptyState text="Aucune donnee RSRP pour cette zone" />
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" />
            <XAxis dataKey="bucket" tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                   axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
            <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border)' }}
                   tickLine={false} domain={[-120, 0]} />
            <Tooltip
              contentStyle={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: 'var(--text-primary)' }}
              formatter={(value, name) => [name === 'avgRsrp' ? `${value} dBm` : value, name === 'avgRsrp' ? 'RSRP moyen' : 'Echantillons']}
            />
            <Line type="monotone" dataKey="avgRsrp" stroke="var(--accent)" strokeWidth={2}
                  dot={{ r: 2, fill: 'var(--accent)' }} activeDot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

function BucketButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? 'var(--accent-soft)' : 'transparent',
        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
        border: '1px solid var(--border)', borderRadius: 6, padding: '4px 10px', fontSize: 11, fontWeight: 500,
      }}
    >
      {label}
    </button>
  )
}

function EmptyState({ text, color = 'var(--text-faint)' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220, color, fontSize: 13 }}>
      {text}
    </div>
  )
}