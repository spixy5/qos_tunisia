import React from 'react'

/**
 * The platform's signature visual: a signal-bar readout, styled after the
 * bars on a phone's status icon - directly grounded in the subject
 * (Quality of Service / signal accessibility) rather than a generic
 * gauge or donut chart. Used both as the small brand mark (bars=4, no
 * value) and as the Overall Rating Card's main visualization (value 0-100).
 */
export default function SignalMark({ value = null, bars = 5, size = 28, color = null }) {
  const activeBars = value === null ? bars : Math.max(1, Math.round((value / 100) * bars))
  const barColor = color || colorForValue(value)

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {Array.from({ length: bars }).map((_, i) => {
        const barHeight = 6 + i * ((18 - 6) / (bars - 1))
        const barWidth = 24 / bars - 2
        const x = i * (24 / bars) + 1
        const y = 22 - barHeight
        const isActive = value === null ? true : i < activeBars
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barWidth}
            height={barHeight}
            rx={1}
            fill={isActive ? barColor : 'var(--signal-none)'}
          />
        )
      })}
    </svg>
  )
}

export function colorForValue(value) {
  if (value === null || value === undefined) return 'var(--signal-none)'
  if (value >= 90) return 'var(--signal-good)'
  if (value >= 70) return 'var(--signal-mid)'
  return 'var(--signal-poor)'
}
