"""
Dividend Reconciliation Orchestrator - Coordinates the three specialized agents.
Replaces the monolithic llm_agent.py with a clean orchestration pattern.
"""
import pandas as pd
from typing import List, Dict, Any
import logging
from break_detection_agent import BreakDetectionAgent
from root_cause_analysis_agent import RootCauseAnalysisAgent
from priority_classification_agent import PriorityClassificationAgent


class DividendReconciliationOrchestrator:
    """Orchestrates the three specialized agents following SRP principles."""
    
    def __init__(self):
        self.break_detector = BreakDetectionAgent()
        self.root_cause_analyzer = RootCauseAnalysisAgent()
        self.priority_classifier = PriorityClassificationAgent()
        self.logger = logging.getLogger(__name__)
    
    def analyze_dividend_breaks(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> Dict[str, Any]:
        """Main orchestration method that coordinates all three agents."""
        self.logger.info("Starting dividend reconciliation analysis...")
        
        # Step 1: Break Detection
        self.logger.info("Step 1: Detecting breaks...")
        detected_breaks = self.break_detector.detect_breaks(nbim_df, custody_df)
        self.logger.info(f"Detected {len(detected_breaks)} breaks")
        
        if not detected_breaks:
            return {
                'detected_breaks': [],
                'root_cause_analyses': [],
                'priority_classifications': [],
                'summary': {
                    'total_breaks': 0,
                    'message': 'No breaks detected - all records reconciled successfully!'
                }
            }
        
        # Step 2: Root Cause Analysis
        self.logger.info("Step 2: Analyzing root causes...")
        root_cause_results = self.root_cause_analyzer.analyze_multiple_breaks(detected_breaks)
        
        # Step 3: Priority Classification
        self.logger.info("Step 3: Classifying priorities...")
        breaks_with_root_causes = []
        for i, detected_break in enumerate(detected_breaks):
            root_cause_analysis = root_cause_results['individual_analyses'][i] if i < len(root_cause_results['individual_analyses']) else {}
            breaks_with_root_causes.append({
                'detected_break': detected_break,
                'root_cause_analysis': root_cause_analysis
            })
        
        priority_classifications = self.priority_classifier.classify_multiple_breaks(breaks_with_root_causes)
        priority_summary = self.priority_classifier.generate_priority_summary(priority_classifications)
        
        self.logger.info("Analysis complete!")
        
        return {
            'detected_breaks': detected_breaks,
            'root_cause_analyses': root_cause_results,
            'priority_classifications': priority_classifications,
            'summary': {
                'total_breaks': len(detected_breaks),
                'priority_summary': priority_summary,
                'pattern_analysis': root_cause_results.get('pattern_analysis', {}),
                'message': f'Analysis complete: {len(detected_breaks)} breaks detected and analyzed'
            }
        }
    
    def get_legacy_format_results(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Get results in the legacy format for backward compatibility with existing reporting.
        This method maintains the same interface as the old llm_agent.py
        """
        analysis_results = self.analyze_dividend_breaks(nbim_df, custody_df)
        
        # Convert to legacy format
        legacy_breaks = []
        priority_classifications = analysis_results.get('priority_classifications', [])
        
        for item in priority_classifications:
            detected_break = item.get('detected_break', {})
            root_cause_analysis = item.get('root_cause_analysis', {})
            priority_classification = item.get('priority_classification', {})
            
            # Map to legacy format
            legacy_break = {
                'break_type': detected_break.get('break_type', 'unknown'),
                'severity': priority_classification.get('priority_level', detected_break.get('severity', 'medium')),
                'root_causes': root_cause_analysis.get('root_causes', ['Analysis not available']),
                'actions': priority_classification.get('recommended_actions', ['Review required']),
                'priority_score': priority_classification.get('priority_score', 5),
                'explanation': root_cause_analysis.get('detailed_explanation', 'No detailed explanation available'),
                'match_data': detected_break.get('match_data', {}),
                'calculated_differences': detected_break.get('calculated_differences', {}),
                
                # Additional fields from new architecture
                'amount_impact': detected_break.get('amount_impact', 0),
                'currency': detected_break.get('currency', 'USD'),
                'isin': detected_break.get('isin', 'N/A'),
                'company_name': detected_break.get('company_name', 'N/A'),
                'financial_impact': priority_classification.get('financial_impact', 'medium'),
                'operational_urgency': priority_classification.get('operational_urgency', 'routine'),
                'escalation_required': priority_classification.get('escalation_required', False),
                'target_resolution_days': priority_classification.get('target_resolution_days', 7)
            }
            
            legacy_breaks.append(legacy_break)
        
        # Sort by priority score (descending) to maintain legacy behavior
        legacy_breaks.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        
        return legacy_breaks
