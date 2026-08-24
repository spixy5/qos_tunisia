import React from 'react'
import RsrpHistogramChart from './RsrpHistogramChart.jsx'
import HttpFailureDonutChart from './HttpFailureDonutChart.jsx'

/**
 * 2-column grid on desktop, stacked on mobile (CSS grid with auto-fit
 * minmax handles this without a JS breakpoint check).
 */
export default function DiagnosticsSection({ logs, crossFilter, onBinClick, onCauseClick }) {
  return (
    <div>
      <div className="eyebrow" style={{ marginBottom: 10 }}>Diagnostic et cause racine</div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
          gap: 16,
        }}
      >
        <RsrpHistogramChart logs={logs} activeFilter={crossFilter} onBinClick={onBinClick} />
        <HttpFailureDonutChart logs={logs} activeFilter={crossFilter} onCauseClick={onCauseClick} />
      </div>
    </div>
  )
}
