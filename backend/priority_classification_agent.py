"""
Priority Classification Agent - Ranks breaks by business/materiality impact.
Follows Single Responsibility Principle (SRP).
"""
from typing import Dict, Any, List
import json
import logging
from config import prompt_config
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()


class PriorityClassificationAgent:
    """Agent responsible for classifying business priority and impact of breaks."""
    
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
    
    def classify_priority(self, detected_break: Dict[str, Any], root_cause_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Classify the business priority and impact of a break."""
        break_details = {
            'break_type': detected_break.get('break_type'),
            'severity': detected_break.get('severity'),
            'detection_summary': detected_break.get('detection_summary'),
            'isin': detected_break.get('isin'),
            'company_name': detected_break.get('company_name')
        }
        
        amount_impact = detected_break.get('amount_impact', 0)
        currency = detected_break.get('currency', 'USD')
        
        prompt_template = prompt_config.get_prompt("priority_classification")
        prompt = prompt_template.format(
            break_details=json.dumps(break_details, indent=2, default=str),
            root_cause_analysis=json.dumps(root_cause_analysis, indent=2, default=str),
            amount_impact=amount_impact,
            currency=currency
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            result = self._extract_json_from_response(response.content[0].text)
            result['break_id'] = detected_break.get('isin', 'unknown')
            result['amount_impact'] = amount_impact
            result['currency'] = currency
            return result
        except json.JSONDecodeError:
            return {
                'priority_score': self._calculate_fallback_priority(amount_impact, detected_break.get('severity', 'medium')),
                'priority_level': self._map_severity_to_priority(detected_break.get('severity', 'medium')),
                'financial_impact': self._assess_financial_impact(amount_impact),
                'regulatory_risk': 'medium',
                'operational_urgency': 'routine',
                'systemic_risk': 'low',
                'recommended_actions': ['Manual review required', 'LLM analysis failed'],
                'escalation_required': amount_impact > 10000,
                'target_resolution_days': self._calculate_target_days(amount_impact),
                'business_justification': 'Failed to parse LLM response - using fallback classification',
                'break_id': detected_break.get('isin', 'unknown'),
                'amount_impact': amount_impact,
                'currency': currency
            }
    
    def classify_multiple_breaks(self, breaks_with_root_causes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify priority for multiple breaks using batched API calls."""
        if not breaks_with_root_causes:
            return []
        
        # Use batched classification for better performance
        classified_breaks = self._classify_breaks_batched(breaks_with_root_causes)
        
        # Sort by priority score (descending)
        classified_breaks.sort(
            key=lambda x: x['priority_classification'].get('priority_score', 0), 
            reverse=True
        )
        
        return classified_breaks
    
    def generate_priority_summary(self, classified_breaks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of priority classifications."""
        if not classified_breaks:
            return {'total_breaks': 0, 'summary': 'No breaks to classify'}
        
        # Count by priority levels
        priority_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        financial_impact_total = 0
        escalation_required_count = 0
        immediate_action_count = 0
        
        for item in classified_breaks:
            priority_class = item['priority_classification']
            
            priority_level = priority_class.get('priority_level', 'medium')
            priority_counts[priority_level] = priority_counts.get(priority_level, 0) + 1
            
            financial_impact_total += priority_class.get('amount_impact', 0)
            
            if priority_class.get('escalation_required', False):
                escalation_required_count += 1
            
            if priority_class.get('operational_urgency') == 'immediate':
                immediate_action_count += 1
        
        # Identify highest priority breaks
        top_priority_breaks = classified_breaks[:5]  # Top 5 by priority score
        
        return {
            'total_breaks': len(classified_breaks),
            'priority_distribution': priority_counts,
            'total_financial_impact': financial_impact_total,
            'escalation_required_count': escalation_required_count,
            'immediate_action_required_count': immediate_action_count,
            'top_priority_breaks': [
                {
                    'isin': item['detected_break'].get('isin'),
                    'company_name': item['detected_break'].get('company_name'),
                    'priority_score': item['priority_classification'].get('priority_score'),
                    'priority_level': item['priority_classification'].get('priority_level'),
                    'amount_impact': item['priority_classification'].get('amount_impact')
                }
                for item in top_priority_breaks
            ],
            'recommendations': self._generate_portfolio_recommendations(classified_breaks)
        }
    
    def _calculate_fallback_priority(self, amount_impact: float, severity: str) -> int:
        """Calculate fallback priority score based on amount and severity."""
        base_score = {'high': 8, 'medium': 5, 'low': 2}.get(severity, 5)
        
        # Adjust based on amount impact
        if amount_impact > 100000:
            base_score += 2
        elif amount_impact > 10000:
            base_score += 1
        elif amount_impact < 100:
            base_score -= 1
        
        return max(1, min(10, base_score))
    
    def _map_severity_to_priority(self, severity: str) -> str:
        """Map severity to priority level."""
        mapping = {
            'high': 'high',
            'medium': 'medium',
            'low': 'low'
        }
        return mapping.get(severity, 'medium')
    
    def _assess_financial_impact(self, amount_impact: float) -> str:
        """Assess financial impact level."""
        if amount_impact > 50000:
            return 'high'
        elif amount_impact > 5000:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_target_days(self, amount_impact: float) -> int:
        """Calculate target resolution days based on amount impact."""
        if amount_impact > 100000:
            return 1  # Critical - same day
        elif amount_impact > 10000:
            return 3  # High priority
        elif amount_impact > 1000:
            return 7  # Medium priority
        else:
            return 14  # Low priority
    
    def _generate_portfolio_recommendations(self, classified_breaks: List[Dict[str, Any]]) -> List[str]:
        """Generate portfolio-level recommendations based on break patterns."""
        recommendations = []
        
        if not classified_breaks:
            return ['No breaks detected - continue monitoring']
        
        critical_count = sum(1 for item in classified_breaks 
                           if item['priority_classification'].get('priority_level') == 'critical')
        high_count = sum(1 for item in classified_breaks 
                        if item['priority_classification'].get('priority_level') == 'high')
        
        total_impact = sum(item['priority_classification'].get('amount_impact', 0) 
                          for item in classified_breaks)
        
        if critical_count > 0:
            recommendations.append(f"URGENT: {critical_count} critical breaks require immediate attention")
        
        if high_count > 3:
            recommendations.append(f"High volume of priority breaks ({high_count}) - consider dedicated task force")
        
        if total_impact > 500000:
            recommendations.append(f"Significant financial exposure (${total_impact:,.2f}) - escalate to senior management")
        
        # Pattern-based recommendations
        isins = [item['detected_break'].get('isin') for item in classified_breaks]
        unique_isins = set(isins)
        
        if len(isins) - len(unique_isins) > 2:
            recommendations.append("Multiple breaks per security detected - investigate systematic issues")
        
        if not recommendations:
            recommendations.append("Continue standard break resolution process")
            recommendations.append("Monitor for emerging patterns")
        
        return recommendations
    
    def _classify_breaks_batched(self, breaks_with_root_causes: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        """Classify multiple breaks in batches to reduce API calls."""
        all_classified = []
        
        # Process breaks in batches
        for i in range(0, len(breaks_with_root_causes), batch_size):
            batch = breaks_with_root_causes[i:i + batch_size]
            
            if len(batch) == 1:
                # Single break - use individual classification
                item = batch[0]
                detected_break = item.get('detected_break', {})
                root_cause_analysis = item.get('root_cause_analysis', {})
                priority_classification = self.classify_priority(detected_break, root_cause_analysis)
                
                all_classified.append({
                    'detected_break': detected_break,
                    'root_cause_analysis': root_cause_analysis,
                    'priority_classification': priority_classification
                })
            else:
                # Multiple breaks - use batch classification
                batch_classified = self._classify_batch_priorities(batch)
                all_classified.extend(batch_classified)
        
        return all_classified
    
    def _classify_batch_priorities(self, break_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify priorities for a batch of breaks in a single API call."""
        # Prepare batch data
        batch_data = []
        for i, item in enumerate(break_batch):
            detected_break = item.get('detected_break', {})
            root_cause_analysis = item.get('root_cause_analysis', {})
            
            batch_item = {
                'break_id': i,
                'break_type': detected_break.get('break_type'),
                'severity': detected_break.get('severity'),
                'detection_summary': detected_break.get('detection_summary'),
                'isin': detected_break.get('isin'),
                'company_name': detected_break.get('company_name'),
                'amount_impact': detected_break.get('amount_impact', 0),
                'currency': detected_break.get('currency', 'USD'),
                'root_cause_analysis': root_cause_analysis
            }
            
            batch_data.append(batch_item)
        
        # Create batch prompt
        batch_prompt = self._create_batch_priority_prompt(batch_data)
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens * 2,  # Increase tokens for batch processing
                messages=[{"role": "user", "content": batch_prompt}]
            )
            
            batch_result = self._extract_json_from_response(response.content[0].text)
            
            # Extract individual classifications from batch result
            classified_breaks = []
            for i, item in enumerate(break_batch):
                detected_break = item.get('detected_break', {})
                root_cause_analysis = item.get('root_cause_analysis', {})
                
                if 'classifications' in batch_result and i < len(batch_result['classifications']):
                    priority_classification = batch_result['classifications'][i]
                    priority_classification['break_id'] = detected_break.get('isin', 'unknown')
                    priority_classification['amount_impact'] = detected_break.get('amount_impact', 0)
                    priority_classification['currency'] = detected_break.get('currency', 'USD')
                else:
                    # Fallback for missing classification
                    priority_classification = self._create_fallback_classification(detected_break)
                
                classified_breaks.append({
                    'detected_break': detected_break,
                    'root_cause_analysis': root_cause_analysis,
                    'priority_classification': priority_classification
                })
            
            return classified_breaks
            
        except Exception as e:
            self.logger.error(f"Batch priority classification failed: {e}")
            # Fallback to individual classifications
            fallback_classified = []
            for item in break_batch:
                detected_break = item.get('detected_break', {})
                root_cause_analysis = item.get('root_cause_analysis', {})
                priority_classification = self._create_fallback_classification(detected_break)
                
                fallback_classified.append({
                    'detected_break': detected_break,
                    'root_cause_analysis': root_cause_analysis,
                    'priority_classification': priority_classification
                })
            
            return fallback_classified
    
    def _create_batch_priority_prompt(self, batch_data: List[Dict[str, Any]]) -> str:
        """Create a prompt for batch priority classification."""
        prompt = """Classify business priority and impact for multiple dividend reconciliation breaks. For each break, provide a detailed priority classification.

Breaks to classify:
"""
        
        for i, break_details in enumerate(batch_data):
            prompt += f"\n--- Break {i + 1} ---\n"
            prompt += f"Break Type: {break_details.get('break_type')}\n"
            prompt += f"Severity: {break_details.get('severity')}\n"
            prompt += f"Amount Impact: {break_details.get('amount_impact')} {break_details.get('currency')}\n"
            prompt += f"ISIN: {break_details.get('isin')}\n"
            prompt += f"Company: {break_details.get('company_name')}\n"
            prompt += f"Detection Summary: {break_details.get('detection_summary')}\n"
            
            root_cause = break_details.get('root_cause_analysis', {})
            if root_cause:
                prompt += f"Root Cause Analysis: {json.dumps(root_cause, indent=2, default=str)}\n"
        
        prompt += """\n\nProvide your classification in the following JSON format:
{
  "classifications": [
    {
      "priority_score": "integer (1-10, where 10 is highest priority)",
      "priority_level": "string (critical|high|medium|low)",
      "financial_impact": "string (high|medium|low)",
      "regulatory_risk": "string (high|medium|low)",
      "operational_urgency": "string (immediate|urgent|routine|low)",
      "systemic_risk": "string (high|medium|low)",
      "recommended_actions": ["list of recommended actions"],
      "escalation_required": "boolean",
      "target_resolution_days": "integer",
      "business_justification": "string explaining the priority classification"
    }
  ]
}

Ensure the classifications array has exactly the same number of elements as the input breaks."""
        
        return prompt
    
    def _create_fallback_classification(self, detected_break: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fallback classification when batch processing fails."""
        amount_impact = detected_break.get('amount_impact', 0)
        severity = detected_break.get('severity', 'medium')
        
        return {
            'priority_score': self._calculate_fallback_priority(amount_impact, severity),
            'priority_level': self._map_severity_to_priority(severity),
            'financial_impact': self._assess_financial_impact(amount_impact),
            'regulatory_risk': 'medium',
            'operational_urgency': 'routine',
            'systemic_risk': 'low',
            'recommended_actions': ['Manual review required', 'Batch classification failed'],
            'escalation_required': amount_impact > 10000,
            'target_resolution_days': self._calculate_target_days(amount_impact),
            'business_justification': 'Batch classification failed - using fallback priority assessment',
            'break_id': detected_break.get('isin', 'unknown'),
            'amount_impact': amount_impact,
            'currency': detected_break.get('currency', 'USD')
        }
