"""
Break Detection Agent - Identifies breaks between NBIM and custody data.
Follows Single Responsibility Principle (SRP).
"""
import pandas as pd
from typing import List, Dict, Any
import json
import logging
from config import prompt_config
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()


class BreakDetectionAgent:
    """Agent responsible for detecting breaks in dividend data."""
    
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
    
    def find_potential_matches(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Find potential matches between NBIM and custody records."""
        matches = []
        
        for _, nbim_row in nbim_df.iterrows():
            # Look for matches based on ISIN and event key
            custody_matches = custody_df[
                (custody_df['isin'] == nbim_row['isin']) &
                (custody_df['event_key'] == nbim_row['event_key'])
            ]
            
            if len(custody_matches) == 0:
                # Missing in custody
                matches.append({
                    'type': 'missing_custody',
                    'nbim_record': nbim_row.to_dict(),
                    'custody_record': None
                })
            else:
                # Found matches, compare each one
                for _, custody_row in custody_matches.iterrows():
                    matches.append({
                        'type': 'potential_match',
                        'nbim_record': nbim_row.to_dict(),
                        'custody_record': custody_row.to_dict()
                    })
        
        # Check for custody records missing in NBIM
        for _, custody_row in custody_df.iterrows():
            nbim_matches = nbim_df[
                (nbim_df['isin'] == custody_row['isin']) &
                (nbim_df['event_key'] == custody_row['event_key'])
            ]
            
            if len(nbim_matches) == 0:
                matches.append({
                    'type': 'missing_nbim',
                    'nbim_record': None,
                    'custody_record': custody_row.to_dict()
                })
        
        return matches
    
    def detect_missing_record_break(self, match: Dict[str, Any], missing_source: str) -> Dict[str, Any]:
        """Detect and classify missing record breaks."""
        record = match['nbim_record'] if missing_source == 'custody' else match['custody_record']
        
        prompt_template = prompt_config.get_prompt("break_detection.missing_record")
        prompt = prompt_template.format(
            missing_source=missing_source.upper(),
            record_details=json.dumps(record, indent=2, default=str)
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            result = self._extract_json_from_response(response.content[0].text)
            result['match_data'] = match
            return result
        except json.JSONDecodeError:
            return {
                'break_type': 'missing_record',
                'severity': 'medium',
                'amount_impact': 0.0,
                'currency': 'USD',
                'isin': record.get('isin', 'N/A') if record else 'N/A',
                'company_name': record.get('company_name', 'N/A') if record else 'N/A',
                'missing_from': missing_source,
                'detection_summary': 'Failed to parse LLM response',
                'match_data': match
            }
    
    def detect_potential_break(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Detect and classify potential breaks between matching records."""
        nbim_record = match['nbim_record']
        custody_record = match['custody_record']
        
        # Calculate differences
        amount_diff = abs(float(nbim_record.get('net_amount', 0)) - float(custody_record.get('net_amount', 0)))
        tax_diff = abs(float(nbim_record.get('tax_amount', 0)) - float(custody_record.get('tax_amount', 0)))
        
        prompt_template = prompt_config.get_prompt("break_detection.potential_mismatch")
        prompt = prompt_template.format(
            nbim_record=json.dumps(nbim_record, indent=2, default=str),
            custody_record=json.dumps(custody_record, indent=2, default=str),
            amount_diff=amount_diff,
            tax_diff=tax_diff,
            ex_date_match=nbim_record.get('ex_date') == custody_record.get('ex_date'),
            payment_date_match=nbim_record.get('payment_date') == custody_record.get('payment_date')
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            result = self._extract_json_from_response(response.content[0].text)
            result['match_data'] = match
            result['calculated_differences'] = {
                'amount_diff': amount_diff,
                'tax_diff': tax_diff
            }
            return result
        except json.JSONDecodeError:
            return {
                'break_type': 'detection_error',
                'severity': 'medium',
                'amount_impact': amount_diff,
                'currency': nbim_record.get('currency', 'USD'),
                'isin': nbim_record.get('isin', 'N/A'),
                'company_name': nbim_record.get('company_name', 'N/A'),
                'detection_summary': 'Failed to parse LLM response',
                'match_data': match,
                'calculated_differences': {
                    'amount_diff': amount_diff,
                    'tax_diff': tax_diff
                }
            }
    
    def detect_breaks(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Main method to detect all breaks between datasets."""
        matches = self.find_potential_matches(nbim_df, custody_df)
        detected_breaks = []
        
        for match in matches:
            if match['type'] == 'missing_custody':
                break_result = self.detect_missing_record_break(match, 'custody')
            elif match['type'] == 'missing_nbim':
                break_result = self.detect_missing_record_break(match, 'nbim')
            else:
                break_result = self.detect_potential_break(match)
            
            # Only include actual breaks (not "no_break" results)
            if break_result.get('break_type') != 'no_break':
                detected_breaks.append(break_result)
        
        return detected_breaks
