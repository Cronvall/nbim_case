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
import json
from datetime import datetime
from fastapi.responses import StreamingResponse, JSONResponse
import io
import pandas as pd

from data_ingestion import DataIngestion
from consolidated_row_analysis_agent import ConsolidatedRowAnalysisAgent
from team_resolution_agent import TeamResolutionOrchestrator

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

        # Persist JSON report for downstream resolve endpoint
        try:
            reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            report_path = os.path.join(reports_dir, 'dividend_reconciliation_report.json')
            with open(report_path, 'w') as f:
                json.dump(result.model_dump(), f, indent=2, default=str)
            # Also write a timestamped copy
            ts_name = datetime.now().strftime('%Y%m%d_%H%M%S') + '.json'
            with open(os.path.join(reports_dir, ts_name), 'w') as f:
                json.dump(result.model_dump(), f, indent=2, default=str)
            logger.info(f"Saved analysis report to {report_path}")
        except Exception as e:
            logger.warning(f"Failed to save analysis report: {e}")

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

def _load_latest_report() -> Dict[str, Any]:
    reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
    report_path = os.path.join(reports_dir, 'dividend_reconciliation_report.json')
    if not os.path.exists(report_path):
        raise FileNotFoundError("No analysis report found. Run /api/analyze first.")
    with open(report_path, 'r') as f:
        return json.load(f)

def _build_fixed_dataframes(report_data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """
    Quick-fix resolver:
    - Load normalized NBIM and Custody data using DataIngestion
    - For matched pairs: align custody fields to NBIM where amounts/dates differ
    - For missing_in_nbim: add custody row to NBIM
    - For missing_in_custody: add nbim row to Custody
    - Output normalized schema CSVs
    """
    loader = DataIngestion()
    nbim_df, custody_df = loader.load_all_data()

    # First try team-based resolution
    try:
        team = TeamResolutionOrchestrator()
        result = team.resolve(nbim_df, custody_df, report_data)
        return {'nbim': result['nbim'], 'custody': result['custody']}
    except Exception as e:
        logger.warning(f"Team resolution failed, falling back to simple alignment: {e}")
        # Fallback: simple NBIM-authoritative alignment
        def make_index(df: pd.DataFrame):
            return {(str(r.get('isin')), str(r.get('event_key'))): i for i, r in enumerate(df.to_dict('records'))}
        nbim_index = make_index(nbim_df)
        custody_index = make_index(custody_df)
        for row in report_data.get('row_analyses', []):
            isin = str((row.get('raw_fields') or {}).get('ISIN') or (row.get('row_id') or '').split('-')[0] or '')
            event_key = str((row.get('raw_fields') or {}).get('COAC_EVENT_KEY') or row.get('event_key') or '')
            key = (isin, event_key)
            status = row.get('overall_status')
            nbim_i = nbim_index.get(key)
            custody_i = custody_index.get(key)
            if status == 'missing_record':
                if nbim_i is None and custody_i is not None:
                    nbim_df = pd.concat([nbim_df, custody_df.iloc[[custody_i]].assign(source='NBIM')], ignore_index=True)
                    nbim_index[key] = len(nbim_df) - 1
                elif custody_i is None and nbim_i is not None:
                    custody_df = pd.concat([custody_df, nbim_df.iloc[[nbim_i]].assign(source='CUSTODY')], ignore_index=True)
                    custody_index[key] = len(custody_df) - 1
                continue
            if nbim_i is not None and custody_i is not None:
                for col in ['net_amount', 'gross_amount', 'tax_amount', 'tax_rate', 'currency', 'ex_date', 'payment_date', 'nominal_basis']:
                    try:
                        custody_df.at[custody_i, col] = nbim_df.at[nbim_i, col]
                    except Exception:
                        pass
        return {'nbim': nbim_df, 'custody': custody_df}

@app.post("/api/resolve")
async def resolve_breaks():
    """Trigger quick-fix resolution based on the latest JSON report. Returns download links."""
    try:
        _ = _load_latest_report()  # Validate report exists
        return JSONResponse({
            "status": "ok",
            "message": "Resolution computed. Use the provided download endpoints.",
            "downloads": {
                "nbim": "/api/download-fixed/nbim",
                "custody": "/api/download-fixed/custody"
            }
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Resolution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Resolution failed: {str(e)}")

@app.get("/api/download-fixed/{which}")
async def download_fixed(which: str):
    """Download fixed CSV for 'nbim' or 'custody' computed from the latest report."""
    if which not in {"nbim", "custody"}:
        raise HTTPException(status_code=400, detail="Invalid file selection")
    try:
        report = _load_latest_report()
        dfs = _build_fixed_dataframes(report)
        df = dfs[which]
        buf = io.StringIO()
        df.to_csv(buf, index=False, sep=';')  # match input separator
        buf.seek(0)
        filename = f"fixed_{which}_dividend_bookings.csv"
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename={filename}"
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
