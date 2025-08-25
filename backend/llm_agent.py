"""
Core LLM agent for dividend reconciliation break detection using Anthropic API.
"""
import pandas as pd
from anthropic import Anthropic
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import json
import re
import logging
from config import prompt_config

load_dotenv()


class DividendReconciliationAgent:
    """LLM-powered agent for detecting and classifying dividend breaks."""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = os.getenv('API_MODEL', 'claude-3-sonnet-20240229')
        self.max_tokens = int(os.getenv('MAX_TOKENS', '1500'))
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks and extra text."""
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
    
    def analyze_break(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a potential break using LLM."""
        if match['type'] == 'missing_custody':
            return self._analyze_missing_record(match, 'custody')
        elif match['type'] == 'missing_nbim':
            return self._analyze_missing_record(match, 'nbim')
        else:
            return self._analyze_potential_break(match)
    
    def _analyze_missing_record(self, match: Dict[str, Any], missing_source: str) -> Dict[str, Any]:
        """Analyze missing record breaks."""
        record = match['nbim_record'] if missing_source == 'custody' else match['custody_record']
        
        prompt_template = prompt_config.get_prompt("missing_record_analysis")
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
                'root_causes': ['Data synchronization issue'],
                'actions': ['Investigate missing record'],
                'priority_score': 5,
                'explanation': 'Failed to parse LLM response',
                'match_data': match
            }
    
    def _analyze_potential_break(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze potential breaks between matching records."""
        nbim_record = match['nbim_record']
        custody_record = match['custody_record']
        
        # Calculate differences
        amount_diff = abs(float(nbim_record.get('net_amount', 0)) - float(custody_record.get('net_amount', 0)))
        tax_diff = abs(float(nbim_record.get('tax_amount', 0)) - float(custody_record.get('tax_amount', 0)))
        
        prompt_template = prompt_config.get_prompt("potential_break_analysis")
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
                'break_type': 'analysis_error',
                'severity': 'medium',
                'root_causes': ['LLM analysis failed'],
                'actions': ['Manual review required'],
                'priority_score': 5,
                'explanation': 'Failed to parse LLM response',
                'match_data': match,
                'calculated_differences': {
                    'amount_diff': amount_diff,
                    'tax_diff': tax_diff
                }
            }
    
    def analyze_all_breaks(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Analyze all potential breaks between datasets."""
        matches = self.find_potential_matches(nbim_df, custody_df)
        breaks = []
        
        for match in matches:
            break_analysis = self.analyze_break(match)
            if break_analysis['break_type'] != 'no_break':
                breaks.append(break_analysis)
        
        # Sort by priority score (descending)
        breaks.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        
        return breaks
