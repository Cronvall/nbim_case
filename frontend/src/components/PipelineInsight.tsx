import React, { useEffect, useRef } from 'react'
import type { RowAnalysis } from '../types'
import PipelineGraph from './PipelineGraph'

interface PipelineInsightProps {
  rowAnalysis: RowAnalysis
  onClose: () => void
  rawFields?: Record<string, any>
}

const PipelineInsight: React.FC<PipelineInsightProps> = ({ rowAnalysis, onClose, rawFields }) => {
  // Accessibility: focus trap and ESC to close
  const modalRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault()
            last.focus()
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault()
            first.focus()
          }
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    // autofocus container
    setTimeout(() => modalRef.current?.focus(), 0)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div className="insight-overlay" role="dialog" aria-modal="true">
      <div className="insight-modal" ref={modalRef} tabIndex={-1}>
        <div className="insight-header">
          <div>
            <h3>Event Pipeline</h3>
            <div className="insight-subtitle">
              {rowAnalysis.company_name} • {rowAnalysis.event_key}
            </div>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close insight">✕</button>
        </div>

        <PipelineGraph rawFields={rawFields} />

        <div className="insight-footer">
          <div className="legend">
            <span className="legend-item legend-source">Source</span>
            <span className="legend-item legend-calc">Calc</span>
            <span className="legend-item legend-amount">Amounts</span>
          </div>
          {!rawFields && (
            <div className="insight-note">
              No raw event field values provided by backend yet. Showing structure only.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PipelineInsight
