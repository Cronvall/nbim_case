# NBIM Dividend Reconciliation Backend

A simple AI-powered backend system for detecting and analyzing dividend reconciliation breaks between NBIM and custody data using Anthropic's Claude API.

## Setup

1. **Install dependencies using uv**:
   ```bash
   cd backend
   uv sync
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your Anthropic API key
   ```

3. **Run the reconciliation**:
   ```bash
   uv run python main.py
   ```

## Architecture

The backend is organized around a modular, agent‑oriented pipeline with a thin orchestration layer and an optional API surface for the frontend.

• **Data layer (`data_ingestion.py`)**
  - Reads NBIM and Custody CSVs, returns normalized `pandas.DataFrame` objects with consistent schema (e.g., `isin`, `event_key`, `ex_date`, `payment_date`, `net_amount`, `tax_amount`).
  - Centralizes file I/O and basic validation so downstream components operate on clean inputs.

• **LLM configuration (`config.py`, `prompts.json`)**
  - `prompt_config` loads and serves prompt templates used by all agents.
  - Environment is read via `python-dotenv` with `ANTHROPIC_API_KEY`, `API_MODEL` (defaults to `claude-3-sonnet-20240229`), and `MAX_TOKENS`.

• **Agent layer (single-responsibility components)**
  - `break_detection_agent.py`:
    - Computes candidate matches (`isin`, `event_key`) and detects discrepancies (missing records, amount/tax/date mismatches).
    - Calls Anthropic Messages API per match/batch; robust JSON extraction with fallbacks when parsing fails.
  - `root_cause_analysis_agent.py`:
    - Explains detected breaks, producing structured causes, data-quality issues, and recommended investigations.
    - Supports batch prompts and portfolio-level pattern extraction (e.g., most frequent causes, systemic risk indicator).
  - `priority_classification_agent.py`:
    - Scores each break (1–10), assigns `priority_level` and operational urgency, and proposes actions/escalations.
    - Provides portfolio recommendations and batching to reduce API calls.

• **Orchestration (`dividend_reconciliation_orchestrator.py`)**
  - Coordinates the three agents in sequence: detect → root-cause → prioritize.
  - Returns a rich result object and a legacy view via `get_legacy_format_results()` for compatibility with prior reporting.
  - Adds deterministic fallbacks, sorting, and summary rollups to stabilize outputs when LLM parsing is imperfect.

• **Reporting (`reporting.py`)**
  - Transforms results into Markdown and JSON artifacts for both human and machine consumption.
  - Used by CLI entrypoint to persist `reports/dividend_reconciliation_report.{md,json}`.

• **Entrypoints**
  - CLI: `main.py` wires the pipeline end‑to‑end: ingestion → orchestration → reporting.
  - API: `api_server.py` (FastAPI) exposes `/api/analyze` for the frontend. It initializes `DataIngestion` and a consolidated analysis surface.

• **Row-centric consolidated analysis (`consolidated_row_analysis_agent.py`)**
  - Produces a per-row analysis (status, issues, recommended actions, financial impact) plus a `portfolio_summary` for UI consumption.
  - Used by the FastAPI route to return a strongly typed payload (Pydantic models) aligned with the frontend’s expectations.

• **Legacy compatibility**
  - `dividend_reconciliation_orchestrator.get_legacy_format_results()` maps new agent outputs to the older structure previously emitted by a monolithic `llm_agent.py`.

• **Operational concerns**
  - CORS is configured in `api_server.py` for the Vite dev server (`localhost:5173`).
  - Batching across agents reduces token usage/latency. Each agent implements defensive JSON extraction and fallback objects to keep the pipeline resilient.
  - Configuration and secrets live in `.env`; dependencies are managed via `uv`/`pyproject.toml`.

## Features

- ✅ Automated data loading and normalization
- ✅ AI-powered break detection with classification:
  - Amount mismatches
  - Date mismatches  
  - Missing/extra records
  - Tax discrepancies
- ✅ Priority scoring and materiality assessment
- ✅ Actionable reporting with root cause analysis
- ✅ Both Markdown and JSON output formats

## Output

The system generates reports in the `reports/` directory:
- `dividend_reconciliation_report.md` - Human-readable summary
- `dividend_reconciliation_report.json` - Machine-readable data

## Requirements

- Python 3.9+
- Anthropic API key
- CSV data files in `../data/` directory
