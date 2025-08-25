export interface RowAnalysis {
  row_id: string
  company_name: string
  event_key: string
  reconciliation_score: number
  overall_status: string
  ex_date?: string
  payment_date?: string
  raw_fields?: Record<string, any>
  financial_impact: {
    total_impact_usd: number
    impact_breakdown: {
      net_amount_variance: number
      tax_calculation_variance: number
      position_related_variance: number
    }
    materiality_assessment: string
  }
  identified_issues: Array<{
    issue_type: string
    severity: string
    description: string
    financial_impact: number
    root_cause_hypothesis: string
  }>
  data_quality_assessment: {
    completeness_score: number
    accuracy_score: number
    consistency_score: number
    key_data_issues: string[]
  }
  recommended_actions: Array<{
    action: string
    priority: string
    rationale: string
    estimated_effort: string
    responsible_party: string
    id?: string
    completed?: boolean
  }>
  investigation_findings: {
    primary_discrepancy: string
    contributing_factors: string[]
    system_implications: string
    pattern_indicators: string
    reasoning?: string
  }
  regulatory_compliance: {
    compliance_risk: string
    regulatory_implications: string[]
    reporting_requirements: string[]
  }
  detailed_explanation: string
}

export interface PortfolioSummary {
  total_rows: number
  total_financial_impact_usd: number
  average_reconciliation_score: number
  status_distribution: Record<string, number>
  severity_distribution: Record<string, number>
  high_impact_rows_count: number
  portfolio_health: string
  key_portfolio_recommendations: string[]
  top_issues_by_impact: Array<{
    row_id: string
    company: string
    impact_usd: number
    score: number
  }>
}

export interface ConsolidatedAnalysisResult {
  analysis_type: string
  total_rows_analyzed: number
  analysis_timestamp: string
  row_analyses: RowAnalysis[]
  portfolio_summary: PortfolioSummary
}

export type LoadingState = 'idle' | 'loading' | 'success' | 'error'
