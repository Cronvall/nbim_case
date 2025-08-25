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
from dividend_reconciliation_orchestrator import DividendReconciliationOrchestrator

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

# Pydantic models matching frontend interfaces
class RecordData(BaseModel):
    isin: Optional[str] = None
    ticker: Optional[str] = None
    currency: Optional[str] = None
    custodian: Optional[str] = None
    company_name: Optional[str] = None
    ex_date: Optional[str] = None
    payment_date: Optional[str] = None

class MatchData(BaseModel):
    type: str
    nbim_record: Optional[RecordData] = None
    custody_record: Optional[RecordData] = None

class Break(BaseModel):
    id: str
    type: str
    description: str
    priority: str  # 'high' | 'medium' | 'low'
    match_data: Optional[MatchData] = None
    suggested_actions: List[str]

class Summary(BaseModel):
    total_breaks: int
    high_priority: int
    medium_priority: int
    low_priority: int

class AnalysisResult(BaseModel):
    breaks: List[Break]
    summary: Summary

# Global data loader and orchestrator instances
data_loader = None
orchestrator = None

def initialize_components():
    """Initialize data loader and orchestrator."""
    global data_loader, orchestrator
    
    # Check for Anthropic API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    
    data_loader = DataIngestion()
    orchestrator = DividendReconciliationOrchestrator()
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
        "components_initialized": data_loader is not None and orchestrator is not None
    }

@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_dividends():
    """
    Analyze dividend bookings for discrepancies and breaks.
    Returns analysis results in the format expected by the frontend.
    """
    try:
        if not data_loader or not orchestrator:
            raise HTTPException(status_code=500, detail="Components not initialized")
        
        logger.info("Starting dividend analysis...")
        
        # Load data
        logger.info("Loading dividend data...")
        nbim_data, custody_data = data_loader.load_all_data()
        logger.info(f"Loaded {len(nbim_data)} NBIM records and {len(custody_data)} custody records")
        
        # Analyze breaks using orchestrator
        logger.info("Analyzing breaks with AI agents...")
        breaks = orchestrator.get_legacy_format_results(nbim_data, custody_data)
        logger.info(f"Analysis complete - found {len(breaks)} potential breaks")
        
        # Convert to frontend format
        formatted_breaks = []
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        
        for i, break_item in enumerate(breaks):
            # Map break type to user-friendly description
            break_type = break_item.get('break_type', 'unknown').replace('_', ' ').title()
            
            # Create description from explanation or root causes
            description = break_item.get('explanation', '')
            if not description and break_item.get('root_causes'):
                description = '. '.join(break_item['root_causes'])
            if not description:
                description = f"Discrepancy detected in {break_type.lower()}"
            
            # Map severity to priority
            severity = break_item.get('severity', 'medium').lower()
            if severity not in ['high', 'medium', 'low']:
                severity = 'medium'
            
            severity_counts[severity] += 1
            
            # Get suggested actions
            actions = break_item.get('actions', [])
            if not actions:
                actions = ['Review and investigate discrepancy', 'Verify source data accuracy']
            
            # Get match data
            match_data = None
            if break_item.get('match_data'):
                match_type = break_item['match_data'].get('type')
                nbim_record = None
                if break_item['match_data'].get('nbim_record'):
                    nbim_data = break_item['match_data']['nbim_record']
                    nbim_record = RecordData(
                        isin=nbim_data.get('isin'),
                        ticker=nbim_data.get('ticker'),
                        currency=nbim_data.get('currency'),
                        custodian=nbim_data.get('custodian'),
                        company_name=nbim_data.get('company_name'),
                        ex_date=str(nbim_data.get('ex_date')) if nbim_data.get('ex_date') is not None else None,
                        payment_date=str(nbim_data.get('payment_date')) if nbim_data.get('payment_date') is not None else None
                    )
                custody_record = None
                if break_item['match_data'].get('custody_record'):
                    custody_data = break_item['match_data']['custody_record']
                    custody_record = RecordData(
                        isin=custody_data.get('isin'),
                        ticker=custody_data.get('ticker'),
                        currency=custody_data.get('currency'),
                        custodian=custody_data.get('custodian'),
                        company_name=custody_data.get('company_name'),
                        ex_date=str(custody_data.get('ex_date')) if custody_data.get('ex_date') is not None else None,
                        payment_date=str(custody_data.get('payment_date')) if custody_data.get('payment_date') is not None else None
                    )
                match_data = MatchData(type=match_type, nbim_record=nbim_record, custody_record=custody_record)
            
            formatted_break = Break(
                id=f"break_{i+1}",
                type=break_type,
                description=description,
                priority=severity,
                match_data=match_data,
                suggested_actions=actions
            )
            formatted_breaks.append(formatted_break)
        
        # Create summary
        summary = Summary(
            total_breaks=len(formatted_breaks),
            high_priority=severity_counts['high'],
            medium_priority=severity_counts['medium'],
            low_priority=severity_counts['low']
        )
        
        result = AnalysisResult(breaks=formatted_breaks, summary=summary)
        logger.info("Analysis results formatted successfully")
        
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
