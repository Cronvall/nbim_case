import './App.css'
import { useData } from './context/DataProvider'
import Header from './components/Header'
import AnalyzeControls from './components/AnalyzeControls'
import LoadingComponent from './components/LoadingComponent'
import RowAnalysis from './components/RowAnalysis'

function App() {
  const { loadingState, analysisResult, error } = useData()

  // Show loading component when API is processing
  if (loadingState === 'loading') {
    return <LoadingComponent />
  }


  return (
    <div className="app">
      <Header />
      
      <main className="app-main">
        <AnalyzeControls />

        {error && (
          <div className="error-message">
            <h3>Error</h3>
            <p>{error}</p>
          </div>
        )}

        {analysisResult && (
          <div className="results-section">
            <div className="rows-section">
              <h2>Event Analysis Results</h2>
              {analysisResult.row_analyses?.map((rowAnalysis) => (
                <RowAnalysis key={rowAnalysis.row_id} rowAnalysis={rowAnalysis} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
