import React, { useState } from 'react'
import type { RowAnalysis as RowAnalysisType } from '../types'
import IssuesSection from './IssuesSection'
import ActionsSection from './ActionsSection'
import PipelineInsight from './PipelineInsight'

interface RowAnalysisProps {
  rowAnalysis: RowAnalysisType
}

const RowAnalysis: React.FC<RowAnalysisProps> = ({ rowAnalysis }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [showInsight, setShowInsight] = useState(false)

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    } catch {
      return dateString
    }
  }

  const hasIssues = rowAnalysis.identified_issues && rowAnalysis.identified_issues.length > 0
  const hasActions = rowAnalysis.recommended_actions && rowAnalysis.recommended_actions.length > 0

  return (
    <div key={rowAnalysis.row_id} className="row-card">
      <div className="row-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="row-title-section">
          <div className="row-title-with-toggle">
            <h3>{rowAnalysis.company_name} | {rowAnalysis.event_key}</h3>
            <button className={`expand-toggle ${isExpanded ? 'expanded' : ''}`}>
              {isExpanded ? '▼' : '▶'}
            </button>
          </div>
          <div className="row-metadata">
            <span className="dividend-date">
              Ex-Date: {formatDate(rowAnalysis.ex_date)}
            </span>
            {rowAnalysis.payment_date && (
              <span className="payment-date">
                Pay-Date: {formatDate(rowAnalysis.payment_date)}
              </span>
            )}
          </div>
          <div className="row-metrics">
            <span className="score-badge">
              Score: {rowAnalysis.reconciliation_score}/10
            </span>
            <span className={`status-badge ${rowAnalysis.overall_status}`}>
              {rowAnalysis.overall_status.replace('_', ' ').toUpperCase()}
            </span>
            <button
              className="insight-button"
              onClick={(e) => { e.stopPropagation(); setShowInsight(true) }}
              title="View field-level pipeline"
            >
              Insight
            </button>
          </div>
        </div>
        <div className="financial-impact-summary">
          <span className="impact-amount">
            ${rowAnalysis.financial_impact.total_impact_usd.toLocaleString()}
          </span>
          <span className="materiality">
            {rowAnalysis.financial_impact.materiality_assessment}
          </span>
        </div>
      </div>
      
      {isExpanded && (
        <div className="row-details">
          {hasIssues && <IssuesSection rowAnalysis={rowAnalysis} />}
          {hasActions && <ActionsSection rowAnalysis={rowAnalysis} />}
          
          <div className="detailed-explanation">
            <h4>Investigation Summary</h4>
            <p>{rowAnalysis.detailed_explanation}</p>
          </div>
        </div>
      )}

      {showInsight && (
        <PipelineInsight
          rowAnalysis={rowAnalysis}
          onClose={() => setShowInsight(false)}
          rawFields={rowAnalysis.raw_fields}
        />
      )}
    </div>
  )
}

export default RowAnalysis
