"""
Consolidated Row Analysis Agent - Provides comprehensive analysis per data row.
Replaces the multi-agent approach with unified row-based analysis.
"""
import pandas as pd
from typing import List, Dict, Any, Tuple
import json
import logging
from config import prompt_config
from anthropic import Anthropic
import os
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()


class ConsolidatedRowAnalysisAgent:
    """Agent that provides comprehensive analysis for each data row with consolidated scoring and actions."""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = os.getenv('API_MODEL', 'claude-3-sonnet-20240229')
        self.max_tokens = int(os.getenv('MAX_TOKENS', '2000'))
        self.logger = logging.getLogger(__name__)
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks and extra text."""
        import re
        try:
            # First try direct JSON parsing
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON-like content (starts with { and ends with })
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Log the problematic response for debugging
        self.logger.error(f"Failed to extract JSON from response: {response_text[:500]}...")
        raise json.JSONDecodeError("Could not extract valid JSON from response", response_text, 0)
    
    def _normalize_date(self, value: Any) -> Any:
        """Convert pandas.Timestamp/date/datetime to ISO date string (YYYY-MM-DD). Leave strings as-is."""
        try:
            import pandas as pd  # local import to avoid hard dependency at module load
        except Exception:
            pd = None
        if value is None:
            return None
        # pandas Timestamp
        if pd is not None and isinstance(value, getattr(pd, 'Timestamp', ())):
            try:
                return value.date().isoformat()
            except Exception:
                return str(value)
        # datetime/date
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        # already a string or other type
        return str(value)
    
    def analyze_row_pair(self, nbim_record: Dict[str, Any], custody_record: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze a single row pair (NBIM + Custody) and provide comprehensive analysis."""
        
        # Calculate key metrics
        analysis_metrics = self._calculate_row_metrics(nbim_record, custody_record)
        
        # Create comprehensive prompt
        prompt = self._create_row_analysis_prompt(nbim_record, custody_record, analysis_metrics)
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result = self._extract_json_from_response(response.content[0].text)
            
            # Add calculated metrics to result
            result['calculated_metrics'] = analysis_metrics
            result['analysis_timestamp'] = datetime.now().isoformat()
            # Attach raw field values for transparency visual
            try:
                result['raw_fields'] = self._build_raw_fields(nbim_record, custody_record)
            except Exception:
                # Fail-safe: don't block analysis if mapping fails
                result['raw_fields'] = {}
            # Populate key dates for frontend rendering
            # Prefer NBIM record dates; fall back to custody if missing
            if nbim_record or custody_record:
                raw_ex = ((nbim_record or {}).get('ex_date') or (custody_record or {}).get('ex_date'))
                raw_pay = ((nbim_record or {}).get('payment_date') or (custody_record or {}).get('payment_date'))
                result['ex_date'] = self._normalize_date(raw_ex)
                result['payment_date'] = self._normalize_date(raw_pay)
            
            # Post-process: filter out non-actionable, generic recommendations
            try:
                result['recommended_actions'] = self._filter_recommended_actions(result.get('recommended_actions', []))
            except Exception:
                # Be conservative: if filtering fails, keep original actions
                pass
            
            # Normalize financial impact total to equal the sum of identified issues
            try:
                self._recompute_total_impact(result)
            except Exception:
                pass
            
            return result
            
        except Exception as e:
            self.logger.error(f"Row analysis failed: {e}")
            return self._create_fallback_analysis(nbim_record, custody_record, analysis_metrics)

    def _build_raw_fields(self, nbim_record: Dict[str, Any], custody_record: Dict[str, Any]) -> Dict[str, Any]:
        """Best-effort mapping of requested headers to values from source records (prefer NBIM)."""
        headers = [
            'COAC_EVENT_KEY','INSTRUMENT_DESCRIPTION','ISIN','SEDOL','TICKER','ORGANISATION_NAME',
            'DIVIDENDS_PER_SHARE','EXDATE','PAYMENT_DATE','CUSTODIAN','BANK_ACCOUNT','QUOTATION_CURRENCY',
            'SETTLEMENT_CURRENCY','AVG_FX_RATE_QUOTATION_TO_PORTFOLIO','NOMINAL_BASIS','GROSS_AMOUNT_QUOTATION',
            'NET_AMOUNT_QUOTATION','NET_AMOUNT_SETTLEMENT','GROSS_AMOUNT_PORTFOLIO','NET_AMOUNT_PORTFOLIO',
            'WTHTAX_COST_QUOTATION','WTHTAX_COST_SETTLEMENT','WTHTAX_COST_PORTFOLIO','WTHTAX_RATE',
            'LOCALTAX_COST_QUOTATION','LOCALTAX_COST_SETTLEMENT','TOTAL_TAX_RATE','EXRESPRDIV_COST_QUOTATION',
            'EXRESPRDIV_COST_SETTLEMENT','RESTITUTION_RATE'
        ]

        def normalize_keys(d: Dict[str, Any]) -> Dict[str, Any]:
            out = {}
            for k, v in (d or {}).items():
                if k is None:
                    continue
                kl = str(k).strip()
                out[kl] = v
                out[kl.lower()] = v
                out[kl.replace(' ', '_').lower()] = v
            return out

        src = {}
        src.update(normalize_keys(nbim_record or {}))
        # Only fill keys not present in NBIM from custody
        custody_norm = normalize_keys(custody_record or {})
        for k, v in custody_norm.items():
            src.setdefault(k, v)

        # Known alias map (target -> list of candidate keys)
        aliases: Dict[str, list] = {
            'COAC_EVENT_KEY': ['event_key','coac_event_key'],
            'INSTRUMENT_DESCRIPTION': ['instrument_description','security_description','description'],
            'ISIN': ['isin'],
            'SEDOL': ['sedol'],
            'TICKER': ['ticker'],
            'ORGANISATION_NAME': ['organisation_name','organization_name','company_name','issuer'],
            'DIVIDENDS_PER_SHARE': ['dividends_per_share','dividend_per_share','dps'],
            'EXDATE': ['exdate','ex_date'],
            'PAYMENT_DATE': ['payment_date','pay_date','paymentdate'],
            'CUSTODIAN': ['custodian','custodian_name'],
            'BANK_ACCOUNT': ['bank_account','account_number'],
            'QUOTATION_CURRENCY': ['quotation_currency','quote_currency','currency'],
            'SETTLEMENT_CURRENCY': ['settlement_currency','settle_currency'],
            'AVG_FX_RATE_QUOTATION_TO_PORTFOLIO': ['avg_fx_rate_quotation_to_portfolio','avg_fx_rate_q2p','fx_rate_q2p'],
            'NOMINAL_BASIS': ['nominal_basis','nominal'],
            'GROSS_AMOUNT_QUOTATION': ['gross_amount_quotation','gross_quotation'],
            'NET_AMOUNT_QUOTATION': ['net_amount_quotation','net_quotation'],
            'NET_AMOUNT_SETTLEMENT': ['net_amount_settlement','net_settlement'],
            'GROSS_AMOUNT_PORTFOLIO': ['gross_amount_portfolio','gross_portfolio'],
            'NET_AMOUNT_PORTFOLIO': ['net_amount_portfolio','net_portfolio'],
            'WTHTAX_COST_QUOTATION': ['wthtax_cost_quotation','withholding_tax_cost_quotation','withholding_tax_quotation'],
            'WTHTAX_COST_SETTLEMENT': ['wthtax_cost_settlement','withholding_tax_cost_settlement','withholding_tax_settlement'],
            'WTHTAX_COST_PORTFOLIO': ['wthtax_cost_portfolio','withholding_tax_cost_portfolio','withholding_tax_portfolio'],
            'WTHTAX_RATE': ['wthtax_rate','withholding_tax_rate','tax_rate'],
            'LOCALTAX_COST_QUOTATION': ['localtax_cost_quotation','local_tax_cost_quotation'],
            'LOCALTAX_COST_SETTLEMENT': ['localtax_cost_settlement','local_tax_cost_settlement'],
            'TOTAL_TAX_RATE': ['total_tax_rate','effective_tax_rate'],
            'EXRESPRDIV_COST_QUOTATION': ['exresprdiv_cost_quotation','ex_res_pr_div_cost_quotation'],
            'EXRESPRDIV_COST_SETTLEMENT': ['exresprdiv_cost_settlement','ex_res_pr_div_cost_settlement'],
            'RESTITUTION_RATE': ['restitution_rate']
        }

        out: Dict[str, Any] = {}
        for header, cands in aliases.items():
            val = None
            for cand in cands:
                # check exact, lower, and snake variants
                for key_variant in [cand, cand.lower(), cand.replace(' ', '_').lower()]:
                    if key_variant in src:
                        val = src[key_variant]
                        break
                if val is not None:
                    break
            out[header] = self._normalize_date(val) if 'DATE' in header.upper() else val

        return out
    
    def analyze_all_rows(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze all data rows and provide consolidated analysis."""
        
        # Match records by ISIN and event_key
        matched_pairs = self._match_records(nbim_df, custody_df)
        
        # Analyze each row pair
        row_analyses = []
        for i, (nbim_record, custody_record) in enumerate(matched_pairs):
            analysis = self.analyze_row_pair(nbim_record, custody_record)
            analysis['row_number'] = i + 1
            row_analyses.append(analysis)
        
        # Generate portfolio-level summary
        portfolio_summary = self._generate_portfolio_summary(row_analyses)
        
        return {
            'analysis_type': 'consolidated_row_analysis',
            'total_rows_analyzed': len(row_analyses),
            'analysis_timestamp': datetime.now().isoformat(),
            'row_analyses': row_analyses,
            'portfolio_summary': portfolio_summary
        }
    
    def _match_records(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Match NBIM and Custody records by ISIN and event_key."""
        matched_pairs = []
        
        # Convert DataFrames to dictionaries for easier handling
        nbim_records = nbim_df.to_dict('records')
        custody_records = custody_df.to_dict('records')
        
        # Track processed custody records to identify unmatched ones
        processed_custody = set()
        
        # Match NBIM records with Custody records
        for nbim_record in nbim_records:
            nbim_isin = nbim_record.get('isin')
            nbim_event_key = nbim_record.get('event_key')
            
            # Find matching custody record
            custody_match = None
            for i, custody_record in enumerate(custody_records):
                if (custody_record.get('isin') == nbim_isin and 
                    custody_record.get('event_key') == nbim_event_key and 
                    i not in processed_custody):
                    custody_match = custody_record
                    processed_custody.add(i)
                    break
            
            matched_pairs.append((nbim_record, custody_match))
        
        # Add unmatched custody records
        for i, custody_record in enumerate(custody_records):
            if i not in processed_custody:
                matched_pairs.append((None, custody_record))
        
        return matched_pairs
    
    def _calculate_row_metrics(self, nbim_record: Dict[str, Any], custody_record: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate key metrics for a row pair."""
        metrics = {
            'record_status': 'unknown',
            'amount_differences': {},
            'date_mismatches': {},
            'position_discrepancies': {},
            'tax_discrepancies': {},
            'calculation_errors': {}
        }
        
        if nbim_record is None and custody_record is not None:
            metrics['record_status'] = 'missing_in_nbim'
            metrics['missing_record_impact'] = custody_record.get('net_amount', 0)
            return metrics
        elif custody_record is None and nbim_record is not None:
            metrics['record_status'] = 'missing_in_custody'
            metrics['missing_record_impact'] = nbim_record.get('net_amount', 0)
            return metrics
        elif nbim_record is None and custody_record is None:
            metrics['record_status'] = 'both_missing'
            return metrics
        
        metrics['record_status'] = 'matched'
        
        # Calculate amount differences
        nbim_net = float(nbim_record.get('net_amount', 0))
        custody_net = float(custody_record.get('net_amount', 0))
        nbim_gross = float(nbim_record.get('gross_amount', 0))
        custody_gross = float(custody_record.get('gross_amount', 0))
        nbim_tax = float(nbim_record.get('tax_amount', 0))
        custody_tax = float(custody_record.get('tax_amount', 0))
        
        metrics['amount_differences'] = {
            'net_amount_diff': abs(nbim_net - custody_net),
            'gross_amount_diff': abs(nbim_gross - custody_gross),
            'tax_amount_diff': abs(nbim_tax - custody_tax),
            'net_amount_pct_diff': abs((nbim_net - custody_net) / max(nbim_net, custody_net, 1)) * 100,
            'currency': nbim_record.get('currency', 'USD')
        }
        
        # Check date mismatches
        metrics['date_mismatches'] = {
            'ex_date_match': nbim_record.get('ex_date') == custody_record.get('ex_date'),
            'payment_date_match': nbim_record.get('payment_date') == custody_record.get('payment_date'),
            'record_date_match': nbim_record.get('record_date') == custody_record.get('record_date')
        }
        
        # Check position discrepancies
        nbim_shares = float(nbim_record.get('shares', 0))
        custody_shares = float(custody_record.get('shares', 0))
        metrics['position_discrepancies'] = {
            'shares_diff': abs(nbim_shares - custody_shares),
            'shares_pct_diff': abs((nbim_shares - custody_shares) / max(nbim_shares, custody_shares, 1)) * 100,
            'position_match': nbim_shares == custody_shares
        }
        
        # Calculate tax rate discrepancies
        if nbim_gross > 0 and custody_gross > 0:
            nbim_tax_rate = (nbim_tax / nbim_gross) * 100
            custody_tax_rate = (custody_tax / custody_gross) * 100
            metrics['tax_discrepancies'] = {
                'nbim_tax_rate': nbim_tax_rate,
                'custody_tax_rate': custody_tax_rate,
                'tax_rate_diff': abs(nbim_tax_rate - custody_tax_rate)
            }
        
        return metrics
    
    def _create_row_analysis_prompt(self, nbim_record: Dict[str, Any], custody_record: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        """Create comprehensive analysis prompt for a row pair."""
        
        prompt = f"""You are analyzing dividend reconciliation data for a single row pair. Provide a comprehensive JSON analysis following the detailed investigative format.

            IMPORTANT action guidance:
            - Do not propose overlapping or redundant actions. If two actions solve the same underlying problem (e.g., a quick fix and a long-term fix), include only the long-term fix.
            - Prefer durable, long-term remediation over short-term workarounds.
            - Exclude generic compliments or hygiene tasks (e.g., "Maintain current high-quality standards", "Document successful reconciliation", "Create benchmark"). Only include concrete, row-specific actions that change data, perform a check, contact a counterparty, correct a calculation, or implement a specific control.

            NBIM Record: {json.dumps(nbim_record, indent=2, default=str) if nbim_record else "None"}

            Custody Record: {json.dumps(custody_record, indent=2, default=str) if custody_record else "None"}

            Calculated Metrics: {json.dumps(metrics, indent=2, default=str)}

            Provide your analysis in the following JSON structure:

            {{
            "row_id": "string (ISIN-EventKey or unique identifier)",
            "company_name": "string",
            "event_key": "string",
            "reconciliation_score": "integer (1-10, where 10 is perfect match, 1 is critical issues)",
            "overall_status": "string (perfect_match|minor_discrepancies|significant_issues|critical_problems|missing_record)",
            "financial_impact": {{
                "total_impact_usd": "float (total financial impact in USD)",
                "impact_breakdown": {{
                "net_amount_variance": "float",
                "tax_calculation_variance": "float", 
                "position_related_variance": "float"
                }},
                "materiality_assessment": "string (immaterial|material|highly_material)"
            }},
            "identified_issues": [
                {{
                "issue_type": "string (amount_discrepancy|date_mismatch|position_error|tax_calculation|missing_record|calculation_error)",
                "severity": "string (low|medium|high|critical)",
                "description": "string (detailed description of the issue)",
                "financial_impact": "float (USD impact of this specific issue)",
                "root_cause_hypothesis": "string (likely cause of this issue)"
                }}
            ],
            "data_quality_assessment": {{
                "completeness_score": "integer (1-10)",
                "accuracy_score": "integer (1-10)", 
                "consistency_score": "integer (1-10)",
                "key_data_issues": ["list of specific data quality problems"]
            }},
            "recommended_actions": [
                {{
                "action": "string (specific action to take)",
                "priority": "string (immediate|high|medium|low)",
                "rationale": "string (why this action is needed)",
                "estimated_effort": "string (hours/days estimate)",
                "responsible_party": "string (who should handle this)"
                }}
            ],
            "investigation_findings": {{
                "primary_discrepancy": "string (main issue identified)",
                "contributing_factors": ["list of factors contributing to discrepancies"],
                "system_implications": "string (what this suggests about system health)",
                "pattern_indicators": "string (whether this suggests broader issues)",
                "reasoning": "string (a concise paragraph explaining the reasoning behind the conclusions above)"
            }},
            "regulatory_compliance": {{
                "compliance_risk": "string (low|medium|high)",
                "regulatory_implications": ["list of potential regulatory concerns"],
                "reporting_requirements": ["list of reporting obligations affected"]
            }},
            "detailed_explanation": "string (comprehensive explanation of findings, similar to the investigative report style)"
            }}

            Focus on providing actionable insights with specific financial impacts and clear reasoning for each recommendation. Ensure action items are deduplicated and favor long-term solutions over short-term workarounds."""

        return prompt

    def _filter_recommended_actions(self, actions: List[Any]) -> List[Dict[str, Any]]:
        """Filter out non-actionable or generic recommendations.

        Rules:
        - Keep items that are concrete actions (imperative verb, row-specific).
        - Drop generic compliments or hygiene tasks (maintain/continue/monitor/document/create benchmark/celebrate/keep up/no action).
        - Normalize string actions into dict form.
        """
        import re

        if not actions:
            return []

        # Normalize to list of dicts with required keys
        normalized: List[Dict[str, Any]] = []
        for item in actions:
            if isinstance(item, dict):
                # Ensure required keys exist
                action_text = str(item.get('action', '')).strip()
                if not action_text and 'recommendation' in item:
                    action_text = str(item.get('recommendation', '')).strip()
                normalized.append({
                    'action': action_text,
                    'priority': item.get('priority', 'medium'),
                    'rationale': item.get('rationale', ''),
                    'estimated_effort': item.get('estimated_effort', ''),
                    'responsible_party': item.get('responsible_party', '')
                })
            elif isinstance(item, str):
                normalized.append({
                    'action': item.strip(),
                    'priority': 'medium',
                    'rationale': '',
                    'estimated_effort': '',
                    'responsible_party': ''
                })

        if not normalized:
            return []

        # Patterns indicating non-actionable/generic items
        generic_re = re.compile(r"^(?:maintain|continue|monitor|document|create\s+benchmark|celebrate|keep\s+up|no\s+action|none)\b",
                                re.IGNORECASE)
        # Require actionable verb
        actionable_verbs = re.compile(r"\b(verify|reconcile|cross-?check|investigate|contact|request|correct|update|adjust|book|amend|align|compute|recompute|escalate|implement|fix|map|match|attach|obtain|validate)\b",
                                      re.IGNORECASE)

        filtered: List[Dict[str, Any]] = []
        seen_texts = set()
        for obj in normalized:
            text = (obj.get('action') or '').strip()
            if not text:
                continue
            # Drop very short or generic statements
            if len(text) < 10:
                continue
            if generic_re.search(text):
                continue
            if not actionable_verbs.search(text):
                # Lacks a clear verb -> likely non-actionable
                continue
            # Deduplicate by normalized text
            key = re.sub(r"\s+", " ", text.lower())
            if key in seen_texts:
                continue
            seen_texts.add(key)
            filtered.append(obj)

        return filtered

    def _recompute_total_impact(self, result: Dict[str, Any]) -> None:
        """Ensure financial_impact.total_impact_usd equals sum of identified_issues[].financial_impact."""
        issues = result.get('identified_issues') or []
        try:
            total = 0.0
            for it in issues:
                val = it.get('financial_impact', 0) if isinstance(it, dict) else 0
                try:
                    num = float(val)
                except Exception:
                    num = 0.0
                if num < 0:
                    num = 0.0
                total += num
            result.setdefault('financial_impact', {})
            result['financial_impact']['total_impact_usd'] = round(total, 2)
        except Exception:
            # If anything goes wrong, leave the original value
            return

    def _create_fallback_analysis(self, nbim_record: Dict[str, Any], custody_record: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback analysis when LLM analysis fails."""
        # Determine basic status
        if metrics['record_status'] == 'missing_in_nbim':
            status = 'missing_record'
            score = 1
        elif metrics['record_status'] == 'missing_in_custody':
            status = 'missing_record'
            score = 1
        else:
            # Calculate basic score from metrics
            score = 10
            status = 'perfect_match'
            
            if metrics.get('amount_differences', {}).get('net_amount_diff', 0) > 0:
                score -= 3
                status = 'significant_issues'
            
            if not all(metrics.get('date_mismatches', {}).values()):
                score -= 2
                status = 'minor_discrepancies'
            
            if metrics.get('position_discrepancies', {}).get('shares_diff', 0) > 0:
                score -= 2
                status = 'significant_issues'
        
        record = nbim_record or custody_record or {}
        
        return {
            'row_id': f"{record.get('isin', 'unknown')}-{record.get('event_key', 'unknown')}",
            'company_name': record.get('company_name', 'Unknown'),
            'event_key': record.get('event_key', 'unknown'),
            'ex_date': self._normalize_date(record.get('ex_date')),
            'payment_date': self._normalize_date(record.get('payment_date')),
            'reconciliation_score': max(1, score),
            'overall_status': status,
            'financial_impact': {
                'total_impact_usd': metrics.get('missing_record_impact', metrics.get('amount_differences', {}).get('net_amount_diff', 0)),
                'impact_breakdown': {
                    'net_amount_variance': metrics.get('amount_differences', {}).get('net_amount_diff', 0),
                    'tax_calculation_variance': metrics.get('amount_differences', {}).get('tax_amount_diff', 0),
                    'position_related_variance': 0
                },
                'materiality_assessment': 'material' if metrics.get('missing_record_impact', 0) > 1000 else 'immaterial'
            },
            'identified_issues': [
                {
                    'issue_type': 'analysis_failed',
                    'severity': 'medium',
                    'description': 'LLM analysis failed - manual review required',
                    'financial_impact': 0,
                    'root_cause_hypothesis': 'System analysis error'
                }
            ],
            'data_quality_assessment': {
                'completeness_score': 5,
                'accuracy_score': 5,
                'consistency_score': 5,
                'key_data_issues': ['Analysis system failure']
            },
            'recommended_actions': [
                {
                    'action': 'Manual review required due to analysis failure',
                    'priority': 'high',
                    'rationale': 'Automated analysis could not complete successfully',
                    'estimated_effort': '2-4 hours',
                    'responsible_party': 'Senior Analyst'
                }
            ],
            'investigation_findings': {
                'primary_discrepancy': 'Analysis system failure',
                'contributing_factors': ['LLM response parsing error'],
                'system_implications': 'Analysis system requires attention',
                'pattern_indicators': 'Isolated system issue',
                'reasoning': 'Based on the inability to parse the LLM response, the most plausible conclusion is a tooling/parsing failure rather than a data discrepancy. Therefore, a manual review of this record and the analysis pipeline is warranted.'
            },
            'regulatory_compliance': {
                'compliance_risk': 'medium',
                'regulatory_implications': ['Manual verification required'],
                'reporting_requirements': ['Document analysis failure']
            },
            'detailed_explanation': 'Automated analysis failed to complete. Manual review is required to assess this dividend reconciliation row for potential discrepancies and compliance issues.'
        }
    
    def _generate_portfolio_summary(self, row_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate portfolio-level summary from individual row analyses."""
        
        if not row_analyses:
            return {'summary': 'No rows analyzed'}
        
        # Calculate aggregate metrics
        total_financial_impact = sum(analysis['financial_impact']['total_impact_usd'] for analysis in row_analyses)
        avg_reconciliation_score = sum(analysis['reconciliation_score'] for analysis in row_analyses) / len(row_analyses)
        
        # Count by status
        status_counts = {}
        severity_counts = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        
        for analysis in row_analyses:
            status = analysis['overall_status']
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count issue severities
            for issue in analysis.get('identified_issues', []):
                severity = issue.get('severity', 'medium')
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Identify top issues
        high_impact_rows = [
            analysis for analysis in row_analyses 
            if analysis['financial_impact']['total_impact_usd'] > 1000
        ]
        
        # Generate recommendations
        portfolio_recommendations = []
        
        if len(high_impact_rows) > 0:
            portfolio_recommendations.append(f"URGENT: {len(high_impact_rows)} rows have financial impact >$1,000 requiring immediate attention")
        
        if avg_reconciliation_score < 7:
            portfolio_recommendations.append(f"Portfolio reconciliation quality is below acceptable threshold (avg score: {avg_reconciliation_score:.1f}/10)")
        
        if severity_counts['critical'] > 0:
            portfolio_recommendations.append(f"CRITICAL: {severity_counts['critical']} critical issues identified requiring immediate escalation")
        
        return {
            'total_rows': len(row_analyses),
            'total_financial_impact_usd': total_financial_impact,
            'average_reconciliation_score': round(avg_reconciliation_score, 1),
            'status_distribution': status_counts,
            'severity_distribution': severity_counts,
            'high_impact_rows_count': len(high_impact_rows),
            'portfolio_health': 'excellent' if avg_reconciliation_score >= 9 else 'good' if avg_reconciliation_score >= 7 else 'concerning' if avg_reconciliation_score >= 5 else 'critical',
            'key_portfolio_recommendations': portfolio_recommendations,
            'top_issues_by_impact': sorted(
                [
                    {
                        'row_id': analysis['row_id'],
                        'company': analysis['company_name'],
                        'impact_usd': analysis['financial_impact']['total_impact_usd'],
                        'score': analysis['reconciliation_score']
                    }
                    for analysis in row_analyses
                ],
                key=lambda x: x['impact_usd'],
                reverse=True
            )[:5]
        }
