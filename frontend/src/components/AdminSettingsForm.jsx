import React, { useEffect, useState } from 'react'
import {
  getBandThresholds, upsertBandThreshold,
  getTechnologyThresholds, upsertTechnologyThreshold,
  getDurationThreshold, upsertDurationThreshold,
} from '../api/client'

const BANDS = ['L800', 'L1800', 'L2100', 'U900', 'U2100', 'G900', 'G1800']
const TECHNOLOGIES = ['4G', '4G_3G', '5G']

export default function AdminSettingsForm() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DurationThresholdPanel />
      <BandThresholdsPanel />
      <TechnologyThresholdsPanel />
    </div>
  )
}

function DurationThresholdPanel() {
  const [value, setValue] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(10)
  const [saving, setSaving] = useState(false)

  const load = () => getDurationThreshold().then((r) => { setValue(r); setDraft(r.cutoff_seconds) }).catch(() => setValue(null))
  useEffect(() => { load() }, [])

  const save = async () => {
    setSaving(true)
    try {
      await upsertDurationThreshold({ cutoff_seconds: draft })
      await load()
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel" style={{ padding: 24 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Seuil de telechargement lent (TAO / TAI)</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Un attempt HTTP dont la duree de telechargement depasse ce seuil est compte comme un echec TAO,
        et exclu du numerateur TAI.
      </div>

      {!editing ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 28, fontWeight: 600 }}>
            {value ? `${value.cutoff_seconds}s` : '—'}
          </div>
          <button className="btn-ghost" onClick={() => setEditing(true)}>Modifier</button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <NumField label="Seuil (secondes)" value={draft} onChange={setDraft} />
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Enregistrement...' : 'Enregistrer'}
          </button>
          <button className="btn-ghost" onClick={() => { setEditing(false); setDraft(value?.cutoff_seconds ?? 10) }}>
            Annuler
          </button>
        </div>
      )}
    </div>
  )
}

function BandThresholdsPanel() {
  const [rows, setRows] = useState([])
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = () => getBandThresholds().then(setRows).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const findRow = (band) => rows.find((r) => r.band === band)

  const openEditor = (band) => {
    const existing = findRow(band)
    setEditing(existing || { band, taux_aff: 0, tai_threshold: -100 })
  }

  const save = async () => {
    setSaving(true)
    try {
      await upsertBandThreshold(editing)
      await load()
      setEditing(null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel" style={{ padding: 24 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Parametres TAI — par bande de frequence</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Affaiblissement de penetration et seuil indoor. Meme valeur pour les 3 operateurs (pas de variation par operateur).
      </div>

      <table>
        <thead>
          <tr>
            <th style={{ fontFamily: 'var(--font-body)' }}>Bande (MHz)</th>
            <th>Affaiblissement (Taux_aff, dB)</th>
            <th>Seuil Indoor (dBm)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {BANDS.map((band) => {
            const row = findRow(band)
            return (
              <tr key={band}>
                <td style={{ fontFamily: 'var(--font-body)', fontWeight: 500 }}>{band}</td>
                <td>{row ? row.taux_aff : '—'}</td>
                <td>{row ? row.tai_threshold : '—'}</td>
                <td style={{ fontFamily: 'var(--font-body)' }}>
                  <button className="btn-ghost" onClick={() => openEditor(band)}>Modifier</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {editing && (
        <div style={{ marginTop: 20, padding: 18, background: 'var(--bg-panel-raised)', borderRadius: 8 }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Modifier {editing.band}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
            <NumField label="Affaiblissement (dB)" value={editing.taux_aff}
                      onChange={(v) => setEditing({ ...editing, taux_aff: v })} />
            <NumField label="Seuil Indoor (dBm)" value={editing.tai_threshold}
                      onChange={(v) => setEditing({ ...editing, tai_threshold: v })} />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Enregistrement...' : 'Enregistrer'}
            </button>
            <button className="btn-ghost" onClick={() => setEditing(null)}>Annuler</button>
          </div>
        </div>
      )}
    </div>
  )
}

function TechnologyThresholdsPanel() {
  const [rows, setRows] = useState([])
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = () => getTechnologyThresholds().then(setRows).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const findRow = (tech) => rows.find((r) => r.technology === tech)

  const openEditor = (tech) => {
    const existing = findRow(tech)
    setEditing(existing || { technology: tech, debit_exige_mbps: null })
  }

  const save = async () => {
    setSaving(true)
    try {
      await upsertTechnologyThreshold(editing)
      await load()
      setEditing(null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel" style={{ padding: 24 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Parametres TD — par technologie</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Debit exige (Mbps). Pas de variation par operateur.
      </div>

      <table>
        <thead>
          <tr>
            <th style={{ fontFamily: 'var(--font-body)' }}>Technologie</th>
            <th>Debit exige (Mbps)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {TECHNOLOGIES.map((tech) => {
            const row = findRow(tech)
            return (
              <tr key={tech}>
                <td style={{ fontFamily: 'var(--font-body)', fontWeight: 500 }}>{tech}</td>
                <td>{row?.debit_exige_mbps ?? <span style={{ color: 'var(--text-faint)' }}>non defini</span>}</td>
                <td style={{ fontFamily: 'var(--font-body)' }}>
                  <button className="btn-ghost" onClick={() => openEditor(tech)}>Modifier</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {editing && (
        <div style={{ marginTop: 20, padding: 18, background: 'var(--bg-panel-raised)', borderRadius: 8 }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Modifier {editing.technology}</div>
          <div style={{ marginBottom: 14, maxWidth: 220 }}>
            <NumField label="Debit exige (Mbps)" value={editing.debit_exige_mbps ?? ''}
                      onChange={(v) => setEditing({ ...editing, debit_exige_mbps: v })} />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Enregistrement...' : 'Enregistrer'}
            </button>
            <button className="btn-ghost" onClick={() => setEditing(null)}>Annuler</button>
          </div>
        </div>
      )}
    </div>
  )
}

function NumField({ label, value, onChange }) {
  return (
    <label>
      <div className="eyebrow" style={{ marginBottom: 6 }}>{label}</div>
      <input type="number" step="0.1" value={value}
             onChange={(e) => onChange(e.target.value === '' ? null : parseFloat(e.target.value))}
             style={{ width: '100%' }} />
    </label>
  )
}
