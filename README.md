# NBIM Dividend Case

Below follows my desing of the system and notes for my work process of the case.

## 1. Feature Priority (Moscow Method)
### Must-Have Features
Automated data ingestion and normalization: The system must pull and standardize dividend records from both NBIM and custodian CSVs. This reduces manual prep work and allows the agent to compare like-for-like data instantly.

Break detection and basic classification: The LLM must rapidly surface mismatches between datasets and classify common error types (amount, date, missing/extra, tax discrepancies) for each event.

Actionable, explainable reporting: The tool must produce a human-readable summary of found breaks, including root cause hints and prioritization, so teams know what to tackle first.

### Should-Have Features
Prioritization by financial/materiality impact: The agent should flag the largest/core breaks by dollar value, aging, and regulatory urgency, not just all possible mismatches.

User-feedback loop: Include an interface to mark breaks as resolved/accepted or needing escalation, feeding this data back to refine the logic for future runs.

Audit trail with change logging: Minimal logs of what the LLM agent did, showing every automated match/break/override for later review.

### Could-Have Features
Proactive remediation suggestions: Have the agent recommend likely fixes, such as potential booking adjustments or reconciliation with tax tables, for common error classes.

Basic workflow automation: Trigger sample notifications or assign breaks for follow-up to demo downstream integration potential.

Simple dashboard: MVP visualization of the break landscape (counts, categories, progress over time).

### Won’t-Have (for Demo Timeline)
Full AI-based settlement or adaptive learning models

Comprehensive integrations with legacy NBIM platforms

Multi-entity or global tax optimization

## 2. High-Level Architecture Sketch
### Key Modules:
Data Ingestion: Loader for NBIM_CSV, CUSTODY_CSV → common pandas DataFrames.

Normalization & Cleaning: Map columns, check types, fill NA, standardize IDs, amounts, dates.

Core LLM Agent: Prompt-driven logic to classify breaks:

Amount mismatch

Date mismatch

Missing/extra

Tax discrepancy

Reporting Layer: Generate Markdown, HTML, or terminal output with priorities and action points.

### Sequence Diagram (Simplified)

Load CSVs → Normalize

Row-by-row/pairwise compare → Detect potential breaks

For each break, construct LLM prompt/context → LLM classifies+suggests

Aggregate, prioritize, rank → Output summary for user