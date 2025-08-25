import React from 'react'
import type { RowAnalysis } from '../types'
import { useData } from '../context/DataProvider'

interface ActionsSectionProps {
  rowAnalysis: RowAnalysis
}

const ActionsSection: React.FC<ActionsSectionProps> = ({ rowAnalysis }) => {
  const { toggleActionCompleted, removeAction } = useData()

  // Front-end safeguard filter to hide generic compliments/non-actionable items
  const filterActions = (actions: RowAnalysis['recommended_actions'] = []) => {
    const genericRe = /^(?:maintain|continue|monitor|document|create\s+benchmark|celebrate|keep\s+up|no\s+action|none)\b/i
    const actionableVerb = /(verify|reconcile|cross-?check|investigate|contact|request|correct|update|adjust|book|amend|align|compute|recompute|escalate|implement|fix|map|match|attach|obtain|validate)/i
    const seen = new Set<string>()
    return actions.filter((a) => {
      const text = (a?.action || '').trim()
      if (!text || text.length < 10) return false
      if (genericRe.test(text)) return false
      if (!actionableVerb.test(text)) return false
      const key = text.toLowerCase().replace(/\s+/g, ' ')
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }

  const filtered = filterActions(rowAnalysis.recommended_actions)

  return (
    <div className="actions-section">
      <h4>Recommended Actions ({filtered.length})</h4>
      <ul className="actions-list">
        {filtered?.map((action) => {
          const actionId = action.id || `${rowAnalysis.row_id}-${action.action.slice(0, 20)}`
          return (
            <li key={actionId} className={`action-item ${action.completed ? 'completed' : ''}`}>
              <div className="action-content">
                <div className="action-main">
                  <span className="action-text">{action.action}</span>
                  <span className={`priority-indicator ${action.priority}`}>{action.priority}</span>
                </div>
                <div className="action-details">
                  <span className="rationale">{action.rationale}</span>
                </div>
              </div>
              <div className="action-controls">
                <button
                  className={`complete-button ${action.completed ? 'completed' : ''}`}
                  onClick={() => toggleActionCompleted(rowAnalysis.row_id, actionId)}
                  title={action.completed ? 'Mark as incomplete' : 'Mark as complete'}
                >
                  ✓
                </button>
                <button
                  className="remove-button"
                  onClick={() => removeAction(rowAnalysis.row_id, actionId)}
                  title="Remove this action"
                >
                  ✕
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default ActionsSection
