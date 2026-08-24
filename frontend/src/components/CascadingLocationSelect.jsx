import React, { useEffect, useState } from 'react'
import { getGouvernorats, getDelegations, getSecteurs } from '../api/client'

/**
 * Reusable cascading Gouvernorat -> Delegation -> Secteur selector.
 *
 * IMPORTANT: onSelectionChange is called directly from each dropdown's
 * onChange handler, NOT derived via a useEffect watching all 3 state
 * variables. The effect-based approach had a real bug: when the
 * Gouvernorat changes, the effect resetting Delegation/Secteur and the
 * effect reporting the selection upward both run in the same commit, but
 * the reporting effect could still see the pre-reset (stale) Delegation/
 * Secteur values, briefly reporting an inconsistent combination to the
 * parent (e.g. new gouvernorat + old delegation). Calling
 * onSelectionChange directly with the values we just computed sidesteps
 * this entirely - no derived state, no stale closures.
 */
export default function CascadingLocationSelect({
  onSelectionChange,
  fetchGouvernorats = getGouvernorats,
  fetchDelegations = getDelegations,
  fetchSecteurs = getSecteurs,
  emptyGouvernoratMessage = 'Aucune donnee disponible',
}) {
  const [gouvernorats, setGouvernorats] = useState([])
  const [delegations, setDelegations] = useState([])
  const [secteurs, setSecteurs] = useState([])

  const [gouvernoratId, setGouvernoratId] = useState('')
  const [delegationId, setDelegationId] = useState('')
  const [secteurId, setSecteurId] = useState('')

  useEffect(() => {
    fetchGouvernorats().then(setGouvernorats).catch(() => setGouvernorats([]))
  }, [])

  const emit = (g, d, s) => {
    onSelectionChange?.({
      gouvernoratId: g ? Number(g) : null,
      delegationId: d ? Number(d) : null,
      secteurId: s ? Number(s) : null,
    })
  }

  const handleGouvernoratChange = (val) => {
    setGouvernoratId(val)
    setDelegationId('')
    setSecteurId('')
    setDelegations([])
    setSecteurs([])
    emit(val, '', '')
    if (val) {
      fetchDelegations(val).then(setDelegations).catch(() => setDelegations([]))
    }
  }

  const handleDelegationChange = (val) => {
    setDelegationId(val)
    setSecteurId('')
    setSecteurs([])
    emit(gouvernoratId, val, '')
    if (val) {
      fetchSecteurs(val).then(setSecteurs).catch(() => setSecteurs([]))
    }
  }

  const handleSecteurChange = (val) => {
    setSecteurId(val)
    emit(gouvernoratId, delegationId, val)
  }

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <Selector label="Gouvernorat" value={gouvernoratId} onChange={handleGouvernoratChange}
                 options={gouvernorats}
                 placeholder={gouvernorats.length === 0 ? emptyGouvernoratMessage : 'Choisir un gouvernorat'} />
      <Selector label="Delegation" value={delegationId} onChange={handleDelegationChange}
                 options={delegations} placeholder="Choisir une delegation" disabled={!gouvernoratId} />
      <Selector label="Secteur" value={secteurId} onChange={handleSecteurChange}
                 options={secteurs} placeholder="Choisir un secteur" disabled={!delegationId} />
    </div>
  )
}

function Selector({ label, value, onChange, options, placeholder, disabled }) {
  return (
    <label style={{ flex: 1 }}>
      <div className="eyebrow" style={{ marginBottom: 6 }}>{label}</div>
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}
              style={{ width: '100%' }}>
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.name}</option>
        ))}
      </select>
    </label>
  )
}
