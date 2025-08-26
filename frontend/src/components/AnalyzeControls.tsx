import React from 'react'
import { useData } from '../context/DataProvider'

const AnalyzeControls: React.FC = () => {
  const { loadingState, analysisResult, isUsingCache, handleAnalyze, handleResolve, downloadLinks } = useData()

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
      {isUsingCache && (
        <div className="cache-indicator">
          📋 Showing cached results (refreshes every 5 minutes)
        </div>
      )}
    </div>
  )
}

export default AnalyzeControls
