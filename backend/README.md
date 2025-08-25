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

- **`data_ingestion.py`**: Loads and normalizes CSV data from both sources
- **`llm_agent.py`**: Core AI agent using Anthropic API for break detection and classification
- **`reporting.py`**: Generates human-readable and JSON reports
- **`main.py`**: Application entry point that orchestrates the entire process

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
