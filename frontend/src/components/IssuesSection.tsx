import React from 'react'
import type { RowAnalysis } from '../types'

interface IssuesSectionProps {
  rowAnalysis: RowAnalysis
}

const IssuesSection: React.FC<IssuesSectionProps> = ({ rowAnalysis }) => {
  return (
    <div className="issues-section">
      <h4>Identified Issues ({rowAnalysis.identified_issues.length})</h4>
      {rowAnalysis.identified_issues.map((issue, index) => (
        <div key={index} className={`issue-item ${issue.severity}`}>
          <div className="issue-header">
            <span className="issue-type">{issue.issue_type.replace('_', ' ')}</span>
            <span className={`severity-badge ${issue.severity}`}>{issue.severity}</span>
          </div>
          <p className="issue-description">{issue.description}</p>
          <div className="issue-details">
            <span className="financial-impact">Impact: ${issue.financial_impact.toLocaleString()}</span>
            <span className="root-cause">Cause: {issue.root_cause_hypothesis}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default IssuesSection
