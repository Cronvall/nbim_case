"""
FastAPI server for NBIM dividend reconciliation system.
Exposes the backend agents through REST API endpoints.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from data_ingestion import DataIngestion
from consolidated_row_analysis_agent import ConsolidatedRowAnalysisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NBIM Dividend Reconciliation API",
    description="API for analyzing dividend booking discrepancies using AI agents",
    version="1.0.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for consolidated row analysis
class RowAnalysis(BaseModel):
    row_id: str
    company_name: str
    event_key: str
    reconciliation_score: int
    overall_status: str
    ex_date: Optional[str] = None
    payment_date: Optional[str] = None
    financial_impact: Dict[str, Any]
    identified_issues: List[Dict[str, Any]]
    data_quality_assessment: Dict[str, Any]
    recommended_actions: List[Dict[str, Any]]
    investigation_findings: Dict[str, Any]
    regulatory_compliance: Dict[str, Any]
    detailed_explanation: str
    raw_fields: Optional[Dict[str, Any]] = None

class PortfolioSummary(BaseModel):
    total_rows: int
    total_financial_impact_usd: float
    average_reconciliation_score: float
    status_distribution: Dict[str, int]
    severity_distribution: Dict[str, int]
    high_impact_rows_count: int
    portfolio_health: str
    key_portfolio_recommendations: List[str]
    top_issues_by_impact: List[Dict[str, Any]]

class ConsolidatedAnalysisResult(BaseModel):
    analysis_type: str
    total_rows_analyzed: int
    analysis_timestamp: str
    row_analyses: List[RowAnalysis]
    portfolio_summary: PortfolioSummary

# Global data loader and analysis agent instances
data_loader = None
analysis_agent = None

def initialize_components():
    """Initialize data loader and analysis agent."""
    global data_loader, analysis_agent
    
    # Check for Anthropic API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    
    data_loader = DataIngestion()
    analysis_agent = ConsolidatedRowAnalysisAgent()
    logger.info("Components initialized successfully")

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    try:
        initialize_components()
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "NBIM Dividend Reconciliation API is running"}

@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "api_key_configured": bool(os.getenv('ANTHROPIC_API_KEY')),
        "components_initialized": data_loader is not None and analysis_agent is not None
    }

@app.post("/api/analyze", response_model=ConsolidatedAnalysisResult)
async def analyze_dividends():
    """
    Analyze dividend bookings using consolidated row-based analysis.
    Returns comprehensive analysis with one result per data row.
    """
    try:
        if not data_loader or not analysis_agent:
            raise HTTPException(status_code=500, detail="Components not initialized")
        
        logger.info("Starting consolidated dividend analysis...")
        
        # Load data
        logger.info("Loading dividend data...")
        nbim_data, custody_data = data_loader.load_all_data()
        logger.info(f"Loaded {len(nbim_data)} NBIM records and {len(custody_data)} custody records")
        
        # Perform consolidated row analysis
        logger.info("Performing consolidated row analysis...")
        analysis_result = analysis_agent.analyze_all_rows(nbim_data, custody_data)
        logger.info(f"Analysis complete - analyzed {analysis_result['total_rows_analyzed']} rows")
        
        # Convert to Pydantic models for validation
        row_analyses = [RowAnalysis(**row) for row in analysis_result['row_analyses']]
        portfolio_summary = PortfolioSummary(**analysis_result['portfolio_summary'])
        
        result = ConsolidatedAnalysisResult(
            analysis_type=analysis_result['analysis_type'],
            total_rows_analyzed=analysis_result['total_rows_analyzed'],
            analysis_timestamp=analysis_result['analysis_timestamp'],
            row_analyses=row_analyses,
            portfolio_summary=portfolio_summary
        )
        
        logger.info("Consolidated analysis results formatted successfully")
        return result
        
    except FileNotFoundError as e:
        logger.error(f"Data files not found: {e}")
        raise HTTPException(
            status_code=404, 
            detail="Required data files not found. Please ensure CSV files are available."
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Analysis failed: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
