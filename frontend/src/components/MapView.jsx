import React, { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, useMap } from 'react-leaflet'
import { getBoundary, getAreaQuality, getBadRsrpPoints } from '../api/client'
import { useTheme } from '../context/ThemeContext.jsx'

const TUNISIA_CENTER = [34.0, 9.5]

const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY

if (!CARTO_API_KEY) {
  console.error(
    'VITE_CARTO_API_KEY is not set - CARTO basemap tiles will show the ' +
    '"API key required" watermark. Check your .env file and restart the dev server.'
  )
}

// CHANGED: the backend now returns EVERY point (good and bad), not just
// failures - so color needs to reflect `status`, not `logType`. Coloring
// by logType meant a 100%-quality secteur rendered as a solid red line
// (all points were "rsrp", none were actually bad). `logType` is still
// used for the type filter buttons, just not for point color anymore.
export const STATUS_COLORS = {
  good: '#3dd68c',  // green
  bad: '#e5484d',   // red - unchanged from before
}

function qualityColor(pct) {
  if (pct === null || pct === undefined) return '#5b6673'
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
      url: `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY}`,
      attribution: '&copy; OpenStreetMap &copy; CARTO',
    },
    light: {
      label: 'Clair',
      url: `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY}`,
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
 * Layer choice, the points toggle, and the points-type filter are all
 * CONTROLLED props (owned by the parent, rendered in a separate
 * MapControlsPanel) rather than internal state.
 */
export default function MapView({
  secteurId, delegationId, gouvernoratId, operator = 'ALL', technology, height = 320,
  layerKey = 'auto', showBadPoints = true, onBadPointsChange,
  pointsFilter = 'all',
}) {
  const { theme } = useTheme()
  const [geojson, setGeojson] = useState(null)
  const [quality, setQuality] = useState(null)
  const [points, setPoints] = useState([])

  const level = secteurId ? 'secteur' : delegationId ? 'delegation' : gouvernoratId ? 'gouvernorat' : null
  const id = secteurId || delegationId || gouvernoratId || null

  useEffect(() => {
    if (!level) { setGeojson(null); return }
    getBoundary(level, id).then(setGeojson).catch(() => setGeojson(null))
  }, [level, id])

  useEffect(() => {
    if (!level) { setQuality(null); return }
    getAreaQuality({ level, id, operator, technology }).then(setQuality).catch(() => setQuality(null))
  }, [level, id, operator, technology])

  useEffect(() => {
    if (!level) {
      setPoints([])
      onBadPointsChange?.(0)
      return
    }
    getBadRsrpPoints({ level, id, operator, technology })
      .then((pts) => {
        setPoints(pts)
        // CHANGED: report the count of actually-BAD points, not the raw
        // array length - the array now includes good points too, so the
        // raw length no longer means "bad points" (this drives the
        // "Points de mesure" badge count in MapControlsPanel).
        const badCount = pts.filter((p) => p.status === 'bad').length
        onBadPointsChange?.(badCount)
      })
      .catch(() => { setPoints([]); onBadPointsChange?.(0) })
  }, [level, id, operator, technology])

  const activeLayer = layerKey === 'auto' ? LAYERS.auto[theme] : LAYERS[layerKey]
  const fillColor = qualityColor(quality?.quality_pct)

  // logType filter still works exactly as before - just no longer tied
  // to marker color.
  const visiblePoints = pointsFilter === 'all'
    ? points
    : points.filter((p) => p.logType === pointsFilter)

  const hasGoodAndBad = points.some((p) => p.status === 'good') &&
    points.some((p) => p.status === 'bad')

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

          {/* CHANGED: legend now explains point COLOR (good/bad), which
              is what actually varies on the map now. Only shown when
              both statuses are actually present. */}
          {showBadPoints && hasGoodAndBad && (
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLORS.good }} />
                <span>Bon</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLORS.bad }} />
                <span>Mauvais</span>
              </div>
            </div>
          )}
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

        {showBadPoints && visiblePoints.map((p, i) => {
          const color = STATUS_COLORS[p.status] || STATUS_COLORS.bad
          return (
            <CircleMarker
              key={`${p.logType}-${p.status}-${i}`}
              center={[p.lat, p.lon]}
              radius={4}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 1 }}
            />
          )
        })}
      </MapContainer>
    </div>
  )
}