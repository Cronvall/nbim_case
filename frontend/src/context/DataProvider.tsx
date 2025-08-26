import React, { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import type { ConsolidatedAnalysisResult, LoadingState } from '../types'

interface DataContextType {
  loadingState: LoadingState
  analysisResult: ConsolidatedAnalysisResult | null
  error: string
  isUsingCache: boolean
  handleAnalyze: (forceRefresh?: boolean) => Promise<void>
  handleResolve: () => Promise<void>
  downloadLinks: { nbim: string; custody: string } | null
  toggleActionCompleted: (rowId: string, actionId: string) => void
  removeAction: (rowId: string, actionId: string) => void
}

const DataContext = createContext<DataContextType | undefined>(undefined)

// Cache utilities
const CACHE_KEY = 'nbim_analysis_result'
const CACHE_TIMESTAMP_KEY = 'nbim_analysis_timestamp'
const CACHE_DURATION = 5 * 60 * 1000 // 5 minutes in milliseconds

const saveToCache = (data: ConsolidatedAnalysisResult) => {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data))
    localStorage.setItem(CACHE_TIMESTAMP_KEY, Date.now().toString())
  } catch (error) {
    console.warn('Failed to save to cache:', error)
  }
}

const loadFromCache = (): ConsolidatedAnalysisResult | null => {
  try {
    const cachedData = localStorage.getItem(CACHE_KEY)
    const cachedTimestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY)
    
    if (!cachedData || !cachedTimestamp) {
      return null
    }
    
    const timestamp = parseInt(cachedTimestamp, 10)
    const now = Date.now()
    
    // Check if cache is expired
    if (now - timestamp > CACHE_DURATION) {
      clearCache()
      return null
    }
    
    return JSON.parse(cachedData)
  } catch (error) {
    console.warn('Failed to load from cache:', error)
    clearCache()
    return null
  }
}

const clearCache = () => {
  try {
    localStorage.removeItem(CACHE_KEY)
    localStorage.removeItem(CACHE_TIMESTAMP_KEY)
  } catch (error) {
    console.warn('Failed to clear cache:', error)
  }
}

const isCacheValid = (): boolean => {
  try {
    const cachedTimestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY)
    if (!cachedTimestamp) return false
    
    const timestamp = parseInt(cachedTimestamp, 10)
    const now = Date.now()
    
    return (now - timestamp) <= CACHE_DURATION
  } catch (error) {
    return false
  }
}

interface DataProviderProps {
  children: ReactNode
}

export const DataProvider: React.FC<DataProviderProps> = ({ children }) => {
  const [loadingState, setLoadingState] = useState<LoadingState>('idle')
  const [analysisResult, setAnalysisResult] = useState<ConsolidatedAnalysisResult | null>(null)
  const [error, setError] = useState<string>('')
  const [isUsingCache, setIsUsingCache] = useState<boolean>(false)
  const [downloadLinks, setDownloadLinks] = useState<{ nbim: string; custody: string } | null>(null)

  // Load cached data on component mount
  useEffect(() => {
    const cachedResult = loadFromCache()
    if (cachedResult) {
      setAnalysisResult(cachedResult)
      setLoadingState('success')
      setIsUsingCache(true)
    }
  }, [])

  const toggleActionCompleted = (rowId: string, actionId: string) => {
    if (!analysisResult) return
    
    const updatedRowAnalyses = analysisResult.row_analyses.map(row =>
      row.row_id === rowId 
        ? {
            ...row,
            recommended_actions: row.recommended_actions.map(action => {
              const currentActionId = action.id || `${row.row_id}-${action.action.slice(0, 20)}`
              return currentActionId === actionId
                ? { ...action, completed: !action.completed }
                : action
            })
          }
        : row
    )
    
    const updatedResult = {
      ...analysisResult,
      row_analyses: updatedRowAnalyses
    }
    
    setAnalysisResult(updatedResult)
    saveToCache(updatedResult)
  }

  const removeAction = (rowId: string, actionId: string) => {
    if (!analysisResult) return
    
    // Find the action text for the confirmation dialog
    const rowItem = analysisResult.row_analyses.find(r => r.row_id === rowId)
    const action = rowItem?.recommended_actions.find(a => (a.id || `${rowId}-${a.action.slice(0, 20)}`) === actionId)
    
    if (!action) return
    
    const confirmed = window.confirm(
      `Are you sure you want to remove this action?\n\n"${action.action}"`
    )
    
    if (!confirmed) return
    
    const updatedRowAnalyses = analysisResult.row_analyses.map(row =>
      row.row_id === rowId 
        ? {
            ...row,
            recommended_actions: row.recommended_actions.filter(action => {
              const currentActionId = action.id || `${rowId}-${action.action.slice(0, 20)}`
              return currentActionId !== actionId
            })
          }
        : row
    )
    
    const updatedResult = {
      ...analysisResult,
      row_analyses: updatedRowAnalyses
    }
    
    setAnalysisResult(updatedResult)
    saveToCache(updatedResult)
  }

  const handleAnalyze = async (forceRefresh: boolean = false) => {
    // Check cache first unless force refresh is requested
    if (!forceRefresh && isCacheValid()) {
      const cachedResult = loadFromCache()
      if (cachedResult) {
        setAnalysisResult(cachedResult)
        setLoadingState('success')
        setIsUsingCache(true)
        return
      }
    }
    
    setLoadingState('loading')
    setError('')
    setIsUsingCache(false)
    
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

      const result: ConsolidatedAnalysisResult = await response.json()
      
      // Add IDs to actions for frontend state management
      const transformedResult: ConsolidatedAnalysisResult = {
        ...result,
        row_analyses: result.row_analyses.map(row => ({
          ...row,
          recommended_actions: row.recommended_actions.map((action, actionIndex) => ({
            ...action,
            id: action.id || `${row.row_id}-action-${actionIndex}`,
            completed: action.completed || false
          }))
        }))
      }
      
      // Save to cache
      saveToCache(transformedResult)
      
      setAnalysisResult(transformedResult)
      setLoadingState('success')
    } catch (err) {
      console.error('Analysis failed:', err)
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
      setLoadingState('error')
    }
  }

  const handleResolve = async () => {
    setLoadingState('loading')
    setError('')
    try {
      const resp = await fetch('http://localhost:8000/api/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!resp.ok) {
        if (resp.status === 404) throw new Error('No report found. Run Analyze first.')
        throw new Error(`Resolve failed with status ${resp.status}`)
      }
      const data = await resp.json()
      const base = 'http://localhost:8000'
      const links = {
        nbim: base + (data?.downloads?.nbim || '/api/download-fixed/nbim'),
        custody: base + (data?.downloads?.custody || '/api/download-fixed/custody'),
      }
      setDownloadLinks(links)
      setLoadingState('success')
    } catch (err) {
      console.error('Resolve failed:', err)
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
      setLoadingState('error')
    }
  }

  const value: DataContextType = {
    loadingState,
    analysisResult,
    error,
    isUsingCache,
    handleAnalyze,
    handleResolve,
    downloadLinks,
    toggleActionCompleted,
    removeAction,
  }

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

export const useData = (): DataContextType => {
  const context = useContext(DataContext)
  if (context === undefined) {
    throw new Error('useData must be used within a DataProvider')
  }
  return context
}
