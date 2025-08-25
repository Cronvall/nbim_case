import React from 'react'
import { useData } from '../context/DataProvider'

const AnalyzeControls: React.FC = () => {
  const { loadingState, analysisResult, isUsingCache, handleAnalyze } = useData()

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
      </div>
      {isUsingCache && (
        <div className="cache-indicator">
          📋 Showing cached results (refreshes every 5 minutes)
        </div>
      )}
    </div>
  )
}

export default AnalyzeControls
