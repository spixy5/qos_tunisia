import React from 'react'
import { useTheme } from '../context/ThemeContext.jsx'
import { LAYERS } from './MapView.jsx'

const POINT_TYPE_OPTIONS = [
  { key: 'all', label: 'Tous' },
  { key: 'rsrp', label: 'RSRP' },
  { key: 'http_attempt', label: 'HTTP' },
]

export default function MapControlsPanel({
  layerKey, onLayerChange, showBadPoints, onToggleBadPoints, badPointsCount,
  pointsFilter, onPointsFilterChange,
}) {
  const { theme } = useTheme()

  const layerOptions = [
    { key: 'auto', label: LAYERS.auto[theme].label },
    { key: 'streets', label: LAYERS.streets.label },
    { key: 'satellite', label: LAYERS.satellite.label },
  ]

  return (
    <div className="panel" style={{ padding: 18, height: '100%', display: 'flex', flexDirection: 'column', gap: 18, boxSizing: 'border-box' }}>
      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Fond de carte</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {layerOptions.map((opt) => {
            const active = layerKey === opt.key
            return (
              <button
                key={opt.key}
                onClick={() => onLayerChange(opt.key)}
                style={{
                  textAlign: 'left',
                  background: active ? 'var(--accent-soft)' : 'transparent',
                  color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                  border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px',
                  fontSize: 13, fontWeight: 500,
                }}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      <div>
        {/* CHANGED: label + count now reflect what onBadPointsChange
            actually reports (count of bad points specifically), even
            though the map itself renders good points too now. */}
        <div className="eyebrow" style={{ marginBottom: 8 }}>Points de mesure</div>
        <button
          onClick={onToggleBadPoints}
          style={{
            width: '100%', textAlign: 'left',
            background: showBadPoints ? 'rgba(229,72,77,0.12)' : 'transparent',
            color: showBadPoints ? 'var(--signal-poor)' : 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px',
            fontSize: 13, fontWeight: 500,
          }}
        >
          {showBadPoints ? '● Affiches' : '○ Masques'} ({badPointsCount} mauvais)
        </button>
      </div>

      {/* Filter by source type - purely which table a point came from.
          No longer tied to marker color (see MapView: color now shows
          good/bad status instead), so these buttons are plain/neutral. */}
      {showBadPoints && (
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Type de points</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {POINT_TYPE_OPTIONS.map((opt) => {
              const active = pointsFilter === opt.key
              return (
                <button
                  key={opt.key}
                  onClick={() => onPointsFilterChange(opt.key)}
                  style={{
                    textAlign: 'left',
                    background: active ? 'var(--accent-soft)' : 'transparent',
                    color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                    border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px',
                    fontSize: 13, fontWeight: 500,
                  }}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}