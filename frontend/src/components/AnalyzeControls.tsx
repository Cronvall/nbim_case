import React from 'react'
import { useData } from '../context/DataProvider'

const AnalyzeControls: React.FC = () => {
  const { loadingState, analysisResult, isUsingCache, handleAnalyze, handleAnalyzeRevised, handleResolve, downloadLinks, reviewStatus, reviewVotes, reviewFeedback, error } = useData()

  return (
    <div className="analyze-section">
      <div className="analyze-controls">
        <button 
          className="analyze-button"
          onClick={() => handleAnalyze()}
          disabled={loadingState === 'loading'}
        >
          {loadingState === 'loading' ? 'Analyzing...' : 'Analyze'}
        </button>
        <button
          className="analyze-button"
          onClick={() => handleAnalyzeRevised()}
          disabled={loadingState === 'loading'}
          title="Analyze latest revised datasets saved under Revisions"
        >
          {loadingState === 'loading' ? 'Analyzing...' : 'Analyze Latest Revision'}
        </button>
        {analysisResult && (
          <button 
            className="refresh-button"
            onClick={() => handleAnalyze(true)}
            disabled={loadingState === 'loading'}
            title="Force refresh - bypass cache"
          >
            🔄 Refresh
          </button>
        )}
        <button
          className="resolve-button"
          onClick={() => handleResolve()}
          disabled={loadingState === 'loading'}
          title="Resolve based on latest analysis report"
        >
          🛠 Resolve
        </button>
      </div>
      {downloadLinks && (
        <div className="download-controls" style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
          <a className="download-button" href={downloadLinks.nbim} target="_blank" rel="noreferrer" download>
            ⬇️ Download Fixed NBIM CSV
          </a>
          <a className="download-button" href={downloadLinks.custody} target="_blank" rel="noreferrer" download>
            ⬇️ Download Fixed Custody CSV
          </a>
        </div>
      )}
      {reviewStatus === 'needs_revision' && (
        <div className="review-feedback" style={{ marginTop: '12px' }}>
          <div style={{ color: '#b00020', fontWeight: 600 }}>Reviewers rejected the resolution.</div>
          {error && <div style={{ color: '#b00020' }}>{error}</div>}
          {reviewVotes.length > 0 && (
            <ul style={{ marginTop: 8 }}>
              {reviewVotes.map((v, i) => (
                <li key={i}>
                  <strong>{v.reviewer}</strong>: {v.approved ? 'Approved ✅' : 'Rejected ❌'} – {v.feedback}
                </li>
              ))}
            </ul>
          )}
          {reviewFeedback.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600 }}>Actionable feedback:</div>
              <ul>
                {reviewFeedback.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {isUsingCache && (
        <div className="cache-indicator">
          📋 Showing cached results (refreshes every 5 minutes)
        </div>
      )}
    </div>
  )
}

export default AnalyzeControls
