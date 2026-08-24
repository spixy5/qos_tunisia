import React from 'react'
import SignalMark, { colorForValue } from './SignalMark.jsx'

export default function RatingCard({ overview, scope, loading, compact = false }) {
  const iconSize = compact ? 44 : 64
  const valueSize = compact ? 26 : 36
  const padding = compact ? 18 : 24

  if (loading) {
    return (
      <div className="panel" style={{ padding, display: 'flex', alignItems: 'center', justifyContent: 'center', height: compact ? '100%' : 140 }}>
        <span className="eyebrow">Chargement...</span>
      </div>
    )
  }

  if (!scope) {
    return (
      <div className="panel" style={{ padding, display: 'flex', alignItems: 'center', justifyContent: 'center', height: compact ? '100%' : 140, textAlign: 'center' }}>
        <span className="eyebrow">Selectionnez un gouvernorat, une delegation ou un secteur</span>
      </div>
    )
  }

  if (!overview) {
    return (
      <div className="panel" style={{ padding, display: 'flex', alignItems: 'center', justifyContent: 'center', height: compact ? '100%' : 140, textAlign: 'center' }}>
        <span className="eyebrow">Aucune donnee disponible pour cette zone</span>
      </div>
    )
  }

  const { overall_rating, gouvernorat_name } = overview
  const locationLine = scope === 'secteur'
    ? [overview.secteur_name, overview.delegation_name, gouvernorat_name].filter(Boolean).join(' · ')
    : [overview.delegation_name, gouvernorat_name].filter(Boolean).join(' · ')

  const scopeLabel = scope === 'secteur' ? 'Note globale QoS — Secteur' : 'Note globale QoS — Delegation'

  return (
    <div className="panel" style={{ padding, display: 'flex', alignItems: 'center', gap: compact ? 16 : 24, height: compact ? '100%' : 'auto' }}>
      <SignalMark value={overall_rating} bars={5} size={iconSize} />
      <div>
        <div className="eyebrow">{scopeLabel}</div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: valueSize, fontWeight: 600, color: colorForValue(overall_rating), lineHeight: 1.1 }}>
          {overall_rating !== null && overall_rating !== undefined ? `${overall_rating}` : '—'}
          {overall_rating !== null && overall_rating !== undefined && <span style={{ fontSize: valueSize * 0.5, opacity: 0.6 }}> / 100</span>}
        </div>
        <div style={{ fontSize: compact ? 12 : 13, color: 'var(--text-muted)', marginTop: 4 }}>
          {locationLine}
          {scope === 'delegation' && overview.secteurs_with_data !== undefined && (
            <span style={{ color: 'var(--text-faint)' }}> · {overview.secteurs_with_data} secteur(s)</span>
          )}
        </div>
        {(overall_rating === null || overall_rating === undefined) && !compact && (
          <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 4 }}>
            Pas encore de donnees KPI pour cette zone (aucun fichier importe ici, ou TD en attente)
          </div>
        )}
      </div>
    </div>
  )
}
