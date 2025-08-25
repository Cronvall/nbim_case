import { useState } from 'react'
import './App.css'

interface Break {
  id: string
  type: string
  description: string
  priority: 'high' | 'medium' | 'low'
  metadata?: {
    isin?: string
    ticker?: string
    currency?: string
    custodian?: string
  }
  suggested_actions: Array<{
    id: string
    text: string
    completed?: boolean
  }>
}

interface ApiBreak {
  id: string
  type: string
  description: string
  priority: 'high' | 'medium' | 'low'
  metadata?: {
    isin?: string
    ticker?: string
    currency?: string
    custodian?: string
  }
  suggested_actions: string[]
}

interface ApiAnalysisResult {
  breaks: ApiBreak[]
  summary: {
    total_breaks: number
    high_priority: number
    medium_priority: number
    low_priority: number
  }
}

interface AnalysisResult {
  breaks: Break[]
  summary: {
    total_breaks: number
    high_priority: number
    medium_priority: number
    low_priority: number
  }
}

type LoadingState = 'idle' | 'loading' | 'success' | 'error'

function App() {
  const [loadingState, setLoadingState] = useState<LoadingState>('idle')
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string>('')

  const toggleActionCompleted = (breakId: string, actionId: string) => {
    if (!analysisResult) return
    
    console.log('Toggling action:', { breakId, actionId })
    
    const updatedBreaks = analysisResult.breaks.map(breakItem =>
      breakItem.id === breakId 
        ? {
            ...breakItem,
            suggested_actions: breakItem.suggested_actions.map(action => {
              console.log('Checking action:', action.id, 'against', actionId, 'match:', action.id === actionId)
              return action.id === actionId
                ? { ...action, completed: !action.completed }
                : action
            })
          }
        : breakItem
    )
    
    setAnalysisResult({
      ...analysisResult,
      breaks: updatedBreaks
    })
  }

  const removeAction = (breakId: string, actionId: string) => {
    if (!analysisResult) return
    
    // Find the action text for the confirmation dialog
    const breakItem = analysisResult.breaks.find(b => b.id === breakId)
    const action = breakItem?.suggested_actions.find(a => a.id === actionId)
    
    if (!action) return
    
    const confirmed = window.confirm(
      `Are you sure you want to remove this action?\n\n"${action.text}"`
    )
    
    if (!confirmed) return
    
    const updatedBreaks = analysisResult.breaks.map(breakItem =>
      breakItem.id === breakId 
        ? {
            ...breakItem,
            suggested_actions: breakItem.suggested_actions.filter(action => action.id !== actionId)
          }
        : breakItem
    )
    
    setAnalysisResult({
      ...analysisResult,
      breaks: updatedBreaks
    })
  }

  const handleAnalyze = async () => {
    setLoadingState('loading')
    setError('')
    
    try {
      const response = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Analysis endpoint not found. Please ensure the backend is running.')
        } else if (response.status >= 500) {
          throw new Error('Server error occurred. Please try again later.')
        } else {
          throw new Error(`Request failed with status ${response.status}`)
        }
      }

      const result: ApiAnalysisResult = await response.json()
      
      // Transform string actions to objects with IDs
      const transformedResult: AnalysisResult = {
        ...result,
        breaks: result.breaks.map(breakItem => ({
          ...breakItem,
          suggested_actions: breakItem.suggested_actions.map((action, index) => {
            const actionObj = {
              id: `${breakItem.id}-action-${index}`,
              text: action,
              completed: false
            }
            console.log('Created action object:', actionObj)
            return actionObj
          })
        }))
      }
      
      console.log('Transformed result:', transformedResult)
      
      setAnalysisResult(transformedResult)
      setLoadingState('success')
    } catch (err) {
      console.error('Analysis failed:', err)
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
      setLoadingState('error')
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return '#ef4444'
      case 'medium': return '#f59e0b'
      case 'low': return '#10b981'
      default: return '#6b7280'
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>NBIM Dividend Reconciliation</h1>
        <p>Analyze dividend bookings for discrepancies and breaks</p>
      </header>

      <main className="app-main">
        <div className="analyze-section">
          <button 
            className="analyze-button"
            onClick={handleAnalyze}
            disabled={loadingState === 'loading'}
          >
            {loadingState === 'loading' ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>

        {error && (
          <div className="error-message">
            <h3>Error</h3>
            <p>{error}</p>
          </div>
        )}

        {analysisResult && (
          <div className="results-section">
            <div className="summary">
              <h2>Analysis Summary</h2>
              <div className="summary-stats">
                <div className="stat">
                  <span className="stat-number">{analysisResult.summary.total_breaks}</span>
                  <span className="stat-label">Total Breaks</span>
                </div>
                <div className="stat high">
                  <span className="stat-number">{analysisResult.summary.high_priority}</span>
                  <span className="stat-label">High Priority</span>
                </div>
                <div className="stat medium">
                  <span className="stat-number">{analysisResult.summary.medium_priority}</span>
                  <span className="stat-label">Medium Priority</span>
                </div>
                <div className="stat low">
                  <span className="stat-number">{analysisResult.summary.low_priority}</span>
                  <span className="stat-label">Low Priority</span>
                </div>
              </div>
            </div>

            <div className="breaks-section">
              <h2>Issues & Recommended Actions</h2>
              {analysisResult.breaks.map((breakItem) => (
                <div key={breakItem.id} className="break-card">
                  <div className="break-header">
                    <h3>{breakItem.type}</h3>
                    <span 
                      className="priority-badge"
                      style={{ backgroundColor: getPriorityColor(breakItem.priority) }}
                    >
                      {breakItem.priority.toUpperCase()}
                    </span>
                  </div>
                  {breakItem.metadata && (
                    <div className="metadata-section">
                      <h4>Issue Details</h4>
                      <div className="metadata-grid">
                        {breakItem.metadata.isin && (
                          <div className="metadata-item">
                            <span className="metadata-label">ISIN:</span>
                            <span className="metadata-value">{breakItem.metadata.isin}</span>
                          </div>
                        )}
                        {breakItem.metadata.ticker && (
                          <div className="metadata-item">
                            <span className="metadata-label">Ticker:</span>
                            <span className="metadata-value">{breakItem.metadata.ticker}</span>
                          </div>
                        )}
                        {breakItem.metadata.currency && (
                          <div className="metadata-item">
                            <span className="metadata-label">Currency:</span>
                            <span className="metadata-value">{breakItem.metadata.currency}</span>
                          </div>
                        )}
                        {breakItem.metadata.custodian && (
                          <div className="metadata-item">
                            <span className="metadata-label">Custodian:</span>
                            <span className="metadata-value">{breakItem.metadata.custodian}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  <p className="break-description">{breakItem.description}</p>
                  <div className="actions-list">
                    <h4>Recommended Actions:</h4>
                    <ul>
                      {breakItem.suggested_actions.map((action) => {
                        console.log('Rendering action:', action)
                        return (
                        <li key={action.id} className={`action-item ${action.completed ? 'completed' : ''}`}>
                          <span className="action-text">{action.text}</span>
                          <div className="action-controls">
                            <button
                              className={`complete-button ${action.completed ? 'completed' : ''}`}
                              onClick={() => toggleActionCompleted(breakItem.id, action.id)}
                              title={action.completed ? 'Mark as incomplete' : 'Mark as complete'}
                            >
                              ✓
                            </button>
                            <button
                              className="remove-button"
                              onClick={() => removeAction(breakItem.id, action.id)}
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
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
