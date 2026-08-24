import React, { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, useMap } from 'react-leaflet'
import { getBoundary, getAreaQuality, getBadRsrpPoints } from '../api/client'
import { useTheme } from '../context/ThemeContext.jsx'

const TUNISIA_CENTER = [34.0, 9.5]

// quality_pct is 0-100 (share of RSRP samples passing best_rsrp+Taux_aff>seuil).
// Red (0) -> yellow (50) -> green (100).
function qualityColor(pct) {
  if (pct === null || pct === undefined) return '#5b6673' // no data - neutral gray
  const t = Math.max(0, Math.min(1, pct / 100))
  let r, g
  if (t < 0.5) {
    r = 255
    g = Math.round(255 * (t * 2))
  } else {
    r = Math.round(255 * (1 - (t - 0.5) * 2))
    g = 255
  }
  return `rgb(${r},${g},40,0.1)`
}

export const LAYERS = {
  auto: {
    dark: {
      label: 'Sombre',
      url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      attribution: '&copy; OpenStreetMap &copy; CARTO',
    },
    light: {
      label: 'Clair',
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      attribution: '&copy; OpenStreetMap &copy; CARTO',
    },
  },
  streets: {
    label: 'Routes',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
  satellite: {
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
  },
}

function FitToBounds({ geojson }) {
  const map = useMap()
  useEffect(() => {
    if (!geojson) return
    const layer = window.L.geoJSON(geojson)
    const bounds = layer.getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30] })
  }, [geojson, map])
  return null
}

/**
 * Layer choice and the bad-RSRP-points toggle are now CONTROLLED props
 * (owned by the parent, rendered in a separate MapControlsPanel) rather
 * than internal state with floating buttons on the map itself - keeps the
 * map surface uncluttered.
 */
export default function MapView({
  secteurId, delegationId, gouvernoratId, operator = 'ALL', height = 320,
  layerKey = 'auto', showBadPoints = true, onBadPointsChange,
}) {
  const { theme } = useTheme()
  const [geojson, setGeojson] = useState(null)
  const [quality, setQuality] = useState(null)
  const [badPoints, setBadPoints] = useState([])

  const level = secteurId ? 'secteur' : delegationId ? 'delegation' : gouvernoratId ? 'gouvernorat' : null
  const id = secteurId || delegationId || gouvernoratId || null

  useEffect(() => {
    if (!level) { setGeojson(null); return }
    getBoundary(level, id).then(setGeojson).catch(() => setGeojson(null))
  }, [level, id])

  useEffect(() => {
    if (!level) { setQuality(null); return }
    getAreaQuality({ level, id, operator }).then(setQuality).catch(() => setQuality(null))
  }, [level, id, operator])

  useEffect(() => {
    if (!level) {
      setBadPoints([])
      onBadPointsChange?.(0)
      return
    }
    getBadRsrpPoints({ level, id, operator })
      .then((pts) => { setBadPoints(pts); onBadPointsChange?.(pts.length) })
      .catch(() => { setBadPoints([]); onBadPointsChange?.(0) })
  }, [level, id, operator])

  const activeLayer = layerKey === 'auto' ? LAYERS.auto[theme] : LAYERS[layerKey]
  const fillColor = qualityColor(quality?.quality_pct)

  return (
    <div className="panel" style={{ height, overflow: 'hidden', position: 'relative', zIndex: 0 }}>
      {geojson && (
        <div
          style={{
            position: 'absolute', bottom: 30, left: 12, zIndex: 1000,
            background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 6,
            padding: '8px 12px', fontSize: 11, color: 'var(--text-muted)', minWidth: 150,
          }}
        >
          <div style={{ marginBottom: 4 }}>
            Qualite du signal{quality?.operator && quality.operator !== 'ALL' ? ` (${quality.operator})` : ''}
          </div>
          <div style={{
            width: 140, height: 8, borderRadius: 4,
            background: 'linear-gradient(to right, rgb(255,0,40), rgb(255,255,40), rgb(0,255,40))',
          }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
            <span>0%</span>
            <span>100%</span>
          </div>
          <div style={{ marginTop: 6, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {quality?.quality_pct !== null && quality?.quality_pct !== undefined
              ? `${quality.quality_pct}% (${quality.sample_count} echantillons)`
              : 'Pas de donnees RSRP'}
          </div>
        </div>
      )}

      <MapContainer
        center={TUNISIA_CENTER}
        zoom={7}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
        preferCanvas={true}
      >
        <TileLayer key={layerKey === 'auto' ? `auto-${theme}` : layerKey} url={activeLayer.url} attribution={activeLayer.attribution} />

        {geojson && (
          <>
            <GeoJSON
              key={`${JSON.stringify(geojson.properties)}-${fillColor}`}
              data={geojson}
              style={{ color: fillColor, weight: 2, fillColor, fillOpacity: 0.35 }}
            />
            <FitToBounds geojson={geojson} />
          </>
        )}

        {showBadPoints && badPoints.map((p, i) => (
          <CircleMarker
            key={i}
            center={[p.lat, p.lon]}
            radius={4}
            pathOptions={{ color: 'var(--signal-poor)', fillColor: '#e5484d', fillOpacity: 0.85, weight: 1 }}
          />
        ))}
      </MapContainer>
    </div>
  )
}
