"""
Root Cause Analysis Agent - Analyzes and explains causes behind detected breaks.
Follows Single Responsibility Principle (SRP).
"""
from typing import Dict, Any
import json
import logging
from config import prompt_config
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()


class RootCauseAnalysisAgent:
    """Agent responsible for analyzing root causes of detected breaks."""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = os.getenv('API_MODEL', 'claude-3-sonnet-20240229')
        self.max_tokens = int(os.getenv('MAX_TOKENS', '1500'))
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
    
    def analyze_root_cause(self, detected_break: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze root causes for a detected break."""
        break_details = {
            'break_type': detected_break.get('break_type'),
            'severity': detected_break.get('severity'),
            'amount_impact': detected_break.get('amount_impact'),
            'currency': detected_break.get('currency'),
            'detection_summary': detected_break.get('detection_summary')
        }
        
        match_data = detected_break.get('match_data', {})
        nbim_record = match_data.get('nbim_record')
        custody_record = match_data.get('custody_record')
        
        prompt_template = prompt_config.get_prompt("root_cause_analysis")
        prompt = prompt_template.format(
            break_details=json.dumps(break_details, indent=2, default=str),
            nbim_record=json.dumps(nbim_record, indent=2, default=str) if nbim_record else "None",
            custody_record=json.dumps(custody_record, indent=2, default=str) if custody_record else "None"
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            result = self._extract_json_from_response(response.content[0].text)
            result['break_id'] = detected_break.get('isin', 'unknown')
            return result
        except json.JSONDecodeError:
            return {
                'primary_root_cause': 'analysis_failed',
                'root_causes': ['LLM analysis failed'],
                'data_quality_issues': ['Unable to analyze'],
                'system_discrepancies': ['Analysis error'],
                'business_rule_conflicts': [],
                'recommended_investigation': ['Manual review required'],
                'analysis_confidence': 'low',
                'detailed_explanation': 'Failed to parse LLM response for root cause analysis',
                'break_id': detected_break.get('isin', 'unknown')
            }
    
    def analyze_multiple_breaks(self, detected_breaks: list) -> Dict[str, Any]:
        """Analyze root causes for multiple breaks using batched API calls."""
        if not detected_breaks:
            return {
                'individual_analyses': [],
                'pattern_analysis': {'patterns_found': False},
                'total_breaks_analyzed': 0
            }
        
        # Use batched analysis for better performance
        individual_analyses = self._analyze_breaks_batched(detected_breaks)
        
        # Pattern analysis
        patterns = self._identify_patterns(individual_analyses)
        
        return {
            'individual_analyses': individual_analyses,
            'pattern_analysis': patterns,
            'total_breaks_analyzed': len(detected_breaks)
        }
    
    def _identify_patterns(self, analyses: list) -> Dict[str, Any]:
        """Identify common patterns across multiple root cause analyses."""
        if not analyses:
            return {'patterns_found': False}
        
        # Count common root causes
        root_cause_counts = {}
        data_quality_counts = {}
        system_discrepancy_counts = {}
        
        for analysis in analyses:
            # Count primary root causes
            primary_cause = analysis.get('primary_root_cause', 'unknown')
            root_cause_counts[primary_cause] = root_cause_counts.get(primary_cause, 0) + 1
            
            # Count data quality issues
            for issue in analysis.get('data_quality_issues', []):
                data_quality_counts[issue] = data_quality_counts.get(issue, 0) + 1
            
            # Count system discrepancies
            for discrepancy in analysis.get('system_discrepancies', []):
                system_discrepancy_counts[discrepancy] = system_discrepancy_counts.get(discrepancy, 0) + 1
        
        # Identify most common patterns
        most_common_root_cause = max(root_cause_counts.items(), key=lambda x: x[1]) if root_cause_counts else ('none', 0)
        most_common_data_issue = max(data_quality_counts.items(), key=lambda x: x[1]) if data_quality_counts else ('none', 0)
        most_common_system_issue = max(system_discrepancy_counts.items(), key=lambda x: x[1]) if system_discrepancy_counts else ('none', 0)
        
        return {
            'patterns_found': True,
            'most_common_root_cause': {
                'cause': most_common_root_cause[0],
                'frequency': most_common_root_cause[1],
                'percentage': round((most_common_root_cause[1] / len(analyses)) * 100, 1)
            },
            'most_common_data_issue': {
                'issue': most_common_data_issue[0],
                'frequency': most_common_data_issue[1],
                'percentage': round((most_common_data_issue[1] / len(analyses)) * 100, 1) if most_common_data_issue[1] > 0 else 0
            },
            'most_common_system_issue': {
                'issue': most_common_system_issue[0],
                'frequency': most_common_system_issue[1],
                'percentage': round((most_common_system_issue[1] / len(analyses)) * 100, 1) if most_common_system_issue[1] > 0 else 0
            },
            'systemic_risk_indicator': most_common_root_cause[1] / len(analyses) > 0.5,
            'recommended_systemic_actions': self._get_systemic_recommendations(most_common_root_cause[0], most_common_root_cause[1] / len(analyses))
        }
    
    def _get_systemic_recommendations(self, primary_cause: str, frequency_ratio: float) -> list:
        """Get systemic recommendations based on pattern analysis."""
        if frequency_ratio > 0.7:
            return [
                f"High systemic risk detected: {primary_cause} affects {frequency_ratio*100:.1f}% of breaks",
                "Immediate system-wide investigation required",
                "Consider process automation to prevent recurrence",
                "Escalate to senior management for strategic review"
            ]
        elif frequency_ratio > 0.5:
            return [
                f"Moderate systemic pattern: {primary_cause} affects {frequency_ratio*100:.1f}% of breaks",
                "Review and strengthen related controls",
                "Consider process improvements",
                "Monitor for trend continuation"
            ]
        else:
            return [
                "No significant systemic patterns detected",
                "Continue individual break resolution",
                "Monitor for emerging patterns"
            ]
    
    def _analyze_breaks_batched(self, detected_breaks: list, batch_size: int = 5) -> list:
        """Analyze multiple breaks in batches to reduce API calls."""
        all_analyses = []
        
        # Process breaks in batches
        for i in range(0, len(detected_breaks), batch_size):
            batch = detected_breaks[i:i + batch_size]
            
            if len(batch) == 1:
                # Single break - use individual analysis
                analysis = self.analyze_root_cause(batch[0])
                all_analyses.append(analysis)
            else:
                # Multiple breaks - use batch analysis
                batch_analyses = self._analyze_batch_root_causes(batch)
                all_analyses.extend(batch_analyses)
        
        return all_analyses
    
    def _analyze_batch_root_causes(self, break_batch: list) -> list:
        """Analyze root causes for a batch of breaks in a single API call."""
        # Prepare batch data
        batch_data = []
        for i, detected_break in enumerate(break_batch):
            break_details = {
                'break_id': i,
                'break_type': detected_break.get('break_type'),
                'severity': detected_break.get('severity'),
                'amount_impact': detected_break.get('amount_impact'),
                'currency': detected_break.get('currency'),
                'detection_summary': detected_break.get('detection_summary'),
                'isin': detected_break.get('isin', 'unknown')
            }
            
            match_data = detected_break.get('match_data', {})
            break_details['nbim_record'] = match_data.get('nbim_record')
            break_details['custody_record'] = match_data.get('custody_record')
            
            batch_data.append(break_details)
        
        # Create batch prompt
        batch_prompt = self._create_batch_root_cause_prompt(batch_data)
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens * 2,  # Increase tokens for batch processing
                messages=[{"role": "user", "content": batch_prompt}]
            )
            
            batch_result = self._extract_json_from_response(response.content[0].text)
            
            # Extract individual analyses from batch result
            analyses = []
            for i, detected_break in enumerate(break_batch):
                if 'analyses' in batch_result and i < len(batch_result['analyses']):
                    analysis = batch_result['analyses'][i]
                    analysis['break_id'] = detected_break.get('isin', 'unknown')
                    analyses.append(analysis)
                else:
                    # Fallback for missing analysis
                    analyses.append(self._create_fallback_analysis(detected_break))
            
            return analyses
            
        except Exception as e:
            self.logger.error(f"Batch root cause analysis failed: {e}")
            # Fallback to individual analyses
            return [self._create_fallback_analysis(break_item) for break_item in break_batch]
    
    def _create_batch_root_cause_prompt(self, batch_data: list) -> str:
        """Create a prompt for batch root cause analysis."""
        prompt = """Analyze root causes for multiple dividend reconciliation breaks. For each break, provide a detailed root cause analysis.

Breaks to analyze:
"""
        
        for i, break_details in enumerate(batch_data):
            prompt += f"\n--- Break {i + 1} ---\n"
            prompt += f"Break Type: {break_details.get('break_type')}\n"
            prompt += f"Severity: {break_details.get('severity')}\n"
            prompt += f"Amount Impact: {break_details.get('amount_impact')} {break_details.get('currency')}\n"
            prompt += f"ISIN: {break_details.get('isin')}\n"
            prompt += f"Detection Summary: {break_details.get('detection_summary')}\n"
            
            if break_details.get('nbim_record'):
                prompt += f"NBIM Record: {json.dumps(break_details['nbim_record'], indent=2, default=str)}\n"
            if break_details.get('custody_record'):
                prompt += f"Custody Record: {json.dumps(break_details['custody_record'], indent=2, default=str)}\n"
        
        prompt += """\n\nProvide your analysis in the following JSON format:
{
  "analyses": [
    {
      "primary_root_cause": "string (data_quality|system_discrepancy|business_rule|timing|missing_record|other)",
      "root_causes": ["list of specific root causes"],
      "data_quality_issues": ["list of data quality problems identified"],
      "system_discrepancies": ["list of system-level discrepancies"],
      "business_rule_conflicts": ["list of business rule violations"],
      "recommended_investigation": ["list of investigation steps"],
      "analysis_confidence": "string (high|medium|low)",
      "detailed_explanation": "string explaining the root cause analysis"
    }
  ]
}

Ensure the analyses array has exactly the same number of elements as the input breaks."""
        
        return prompt
    
    def _create_fallback_analysis(self, detected_break: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fallback analysis when batch processing fails."""
        return {
            'primary_root_cause': 'analysis_failed',
            'root_causes': ['Batch analysis failed - manual review required'],
            'data_quality_issues': ['Unable to analyze in batch'],
            'system_discrepancies': ['Analysis error'],
            'business_rule_conflicts': [],
            'recommended_investigation': ['Manual review required'],
            'analysis_confidence': 'low',
            'detailed_explanation': 'Batch root cause analysis failed - requires manual investigation',
            'break_id': detected_break.get('isin', 'unknown')
        }
