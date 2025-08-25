"""
Reporting layer for generating actionable dividend reconciliation summaries.
"""
from typing import List, Dict, Any
import json
from datetime import datetime


class ReportGenerator:
    """Generates human-readable reports from break analysis results."""
    
    def generate_summary_report(self, breaks: List[Dict[str, Any]]) -> str:
        """Generate a comprehensive summary report."""
        if not breaks:
            return "# Dividend Reconciliation Report\n\n✅ **No breaks detected** - All records reconciled successfully!"
        
        # Calculate statistics
        total_breaks = len(breaks)
        high_severity = len([b for b in breaks if b.get('severity') == 'high'])
        medium_severity = len([b for b in breaks if b.get('severity') == 'medium'])
        low_severity = len([b for b in breaks if b.get('severity') == 'low'])
        
        break_types = {}
        total_amount_impact = 0
        
        for break_item in breaks:
            break_type = break_item.get('break_type', 'unknown')
            break_types[break_type] = break_types.get(break_type, 0) + 1
            
            # Calculate financial impact
            if 'calculated_differences' in break_item:
                total_amount_impact += break_item['calculated_differences'].get('amount_diff', 0)
        
        # Generate report
        report = f"""# Dividend Reconciliation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Total Breaks Found**: {total_breaks}
- **High Severity**: {high_severity}
- **Medium Severity**: {medium_severity}
- **Low Severity**: {low_severity}
- **Estimated Financial Impact**: ${total_amount_impact:,.2f}

## Break Categories
"""
        
        for break_type, count in break_types.items():
            report += f"- **{break_type.replace('_', ' ').title()}**: {count} breaks\n"
        
        report += "\n## Priority Actions Required\n"
        
        # Show top 5 highest priority breaks
        top_breaks = sorted(breaks, key=lambda x: x.get('priority_score', 0), reverse=True)[:5]
        
        for i, break_item in enumerate(top_breaks, 1):
            report += self._format_break_summary(break_item, i)
        
        if len(breaks) > 5:
            report += f"\n*... and {len(breaks) - 5} additional breaks (see detailed report below)*\n"
        
        report += "\n## Detailed Break Analysis\n"
        
        for i, break_item in enumerate(breaks, 1):
            report += self._format_detailed_break(break_item, i)
        
        return report
    
    def _format_break_summary(self, break_item: Dict[str, Any], index: int) -> str:
        """Format a brief break summary."""
        severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(break_item.get('severity', 'medium'), '⚪')
        
        summary = f"\n### {index}. {severity_emoji} {break_item.get('break_type', 'Unknown').replace('_', ' ').title()}\n"
        summary += f"**Priority Score**: {break_item.get('priority_score', 'N/A')}/10\n"
        summary += f"**Severity**: {break_item.get('severity', 'Unknown').title()}\n"
        
        if 'calculated_differences' in break_item:
            amount_diff = break_item['calculated_differences'].get('amount_diff', 0)
            if amount_diff > 0:
                summary += f"**Amount Difference**: ${amount_diff:,.2f}\n"
        
        # Show key identifiers
        match_data = break_item.get('match_data', {})
        nbim_record = match_data.get('nbim_record')
        custody_record = match_data.get('custody_record')
        
        if nbim_record:
            summary += f"**ISIN**: {nbim_record.get('isin', 'N/A')}\n"
            summary += f"**Company**: {nbim_record.get('company_name', 'N/A')}\n"
        elif custody_record:
            summary += f"**ISIN**: {custody_record.get('isin', 'N/A')}\n"
        
        summary += f"**Action Required**: {', '.join(break_item.get('actions', ['Review required']))}\n"
        
        return summary
    
    def _format_detailed_break(self, break_item: Dict[str, Any], index: int) -> str:
        """Format a detailed break analysis."""
        severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(break_item.get('severity', 'medium'), '⚪')
        
        detail = f"\n### Break #{index}: {severity_emoji} {break_item.get('break_type', 'Unknown').replace('_', ' ').title()}\n"
        
        # Basic info
        detail += f"- **Severity**: {break_item.get('severity', 'Unknown').title()}\n"
        detail += f"- **Priority Score**: {break_item.get('priority_score', 'N/A')}/10\n"
        
        # Financial impact
        if 'calculated_differences' in break_item:
            diffs = break_item['calculated_differences']
            if diffs.get('amount_diff', 0) > 0:
                detail += f"- **Amount Difference**: ${diffs['amount_diff']:,.2f}\n"
            if diffs.get('tax_diff', 0) > 0:
                detail += f"- **Tax Difference**: ${diffs['tax_diff']:,.2f}\n"
        
        # Record details
        match_data = break_item.get('match_data', {})
        nbim_record = match_data.get('nbim_record')
        custody_record = match_data.get('custody_record')
        
        if nbim_record and custody_record:
            detail += "\n**NBIM vs Custody Comparison**:\n"
            detail += f"- ISIN: {nbim_record.get('isin', 'N/A')}\n"
            detail += f"- Company: {nbim_record.get('company_name', 'N/A')}\n"
            detail += f"- Net Amount: ${nbim_record.get('net_amount', 0):,.2f} vs ${custody_record.get('net_amount', 0):,.2f}\n"
            detail += f"- Tax Amount: ${nbim_record.get('tax_amount', 0):,.2f} vs ${custody_record.get('tax_amount', 0):,.2f}\n"
            detail += f"- Ex Date: {nbim_record.get('ex_date', 'N/A')} vs {custody_record.get('ex_date', 'N/A')}\n"
        elif nbim_record:
            detail += f"\n**Missing from Custody** - NBIM Record:\n"
            detail += f"- ISIN: {nbim_record.get('isin', 'N/A')}\n"
            detail += f"- Company: {nbim_record.get('company_name', 'N/A')}\n"
            detail += f"- Net Amount: ${nbim_record.get('net_amount', 0):,.2f}\n"
        elif custody_record:
            detail += f"\n**Missing from NBIM** - Custody Record:\n"
            detail += f"- ISIN: {custody_record.get('isin', 'N/A')}\n"
            detail += f"- Net Amount: ${custody_record.get('net_amount', 0):,.2f}\n"
        
        # Root causes and actions
        detail += f"\n**Possible Root Causes**:\n"
        for cause in break_item.get('root_causes', ['Unknown']):
            detail += f"- {cause}\n"
        
        detail += f"\n**Recommended Actions**:\n"
        for action in break_item.get('actions', ['Manual review required']):
            detail += f"- {action}\n"
        
        if break_item.get('explanation'):
            detail += f"\n**Analysis**: {break_item['explanation']}\n"
        
        detail += "\n---\n"
        
        return detail
    
    def generate_json_report(self, breaks: List[Dict[str, Any]]) -> str:
        """Generate a JSON report for programmatic consumption."""
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_breaks': len(breaks),
                'severity_breakdown': {
                    'high': len([b for b in breaks if b.get('severity') == 'high']),
                    'medium': len([b for b in breaks if b.get('severity') == 'medium']),
                    'low': len([b for b in breaks if b.get('severity') == 'low'])
                },
                'break_types': {}
            },
            'breaks': breaks
        }
        
        # Calculate break type distribution
        for break_item in breaks:
            break_type = break_item.get('break_type', 'unknown')
            report_data['summary']['break_types'][break_type] = \
                report_data['summary']['break_types'].get(break_type, 0) + 1
        
        return json.dumps(report_data, indent=2, default=str)
