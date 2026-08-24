import React, { useEffect, useRef, useState } from 'react'
import CascadingLocationSelect from './CascadingLocationSelect.jsx'

const OPERATOR_OPTIONS = [
  { value: 'ALL', label: 'Tous les operateurs' },
  { value: 'TT', label: 'Tunisie Telecom' },
  { value: 'OO', label: 'Ooredoo' },
  { value: 'OR', label: 'Orange' },
]

function findScrollParent(el) {
  let node = el?.parentElement
  while (node) {
    const style = window.getComputedStyle(node)
    if (/(auto|scroll)/.test(style.overflowY)) return node
    node = node.parentElement
  }
  return document.scrollingElement || document.documentElement
}

/**
 * Sticks to the top of the page's scroll container and auto-hides
 * (slides up) when scrolling down, reappearing when scrolling up or near
 * the top - same pattern as most mobile app headers.
 */
export default function StickyFilterBar({ onSelectionChange, operatorFilter, onOperatorChange }) {
  const wrapperRef = useRef(null)
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    const scrollParent = findScrollParent(wrapperRef.current)
    let lastY = scrollParent.scrollTop

    const onScroll = () => {
      const y = scrollParent.scrollTop
      const diff = y - lastY
      if (y < 40) {
        setHidden(false)
      } else if (diff > 6) {
        setHidden(true)
      } else if (diff < -6) {
        setHidden(false)
      }
      lastY = y
    }

    scrollParent.addEventListener('scroll', onScroll, { passive: true })
    return () => scrollParent.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div
      ref={wrapperRef}
      style={{
        position: 'sticky', top: 0, zIndex: 1500,
        background: 'var(--bg)', paddingBottom: 8, marginBottom: -8,
        transform: hidden ? 'translateY(-130%)' : 'translateY(0)',
        transition: 'transform 0.25s ease',
      }}
    >
      <div className="panel" style={{ padding: 20, display: 'flex', gap: 16, alignItems: 'flex-end' }}>
        <div style={{ flex: 1 }}>
          <CascadingLocationSelect onSelectionChange={onSelectionChange} />
        </div>
        <label style={{ minWidth: 180 }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Operateur</div>
          <select value={operatorFilter} onChange={(e) => onOperatorChange(e.target.value)} style={{ width: '100%' }}>
            {OPERATOR_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </div>
    </div>
  )
}
