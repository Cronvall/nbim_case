"""
Main application entry point for NBIM dividend reconciliation system.
"""
import os
import sys
from data_ingestion import DataIngestion
from dividend_reconciliation_orchestrator import DividendReconciliationOrchestrator
from reporting import ReportGenerator


def main():
    """Main application function."""
    print("🔍 NBIM Dividend Reconciliation System")
    print("=" * 50)
    
    # Check for Anthropic API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set your Anthropic API key in the .env file")
        return 1
    
    try:
        # Step 1: Load and normalize data
        print("\n📊 Loading dividend data...")
        data_loader = DataIngestion()
        nbim_data, custody_data = data_loader.load_all_data()
        
        print(f"✅ Loaded {len(nbim_data)} NBIM records")
        print(f"✅ Loaded {len(custody_data)} custody records")
        
        # Step 2: Analyze breaks using three-agent architecture
        print("\n🤖 Analyzing potential breaks with AI agents...")
        orchestrator = DividendReconciliationOrchestrator()
        breaks = orchestrator.get_legacy_format_results(nbim_data, custody_data)
        
        print(f"✅ Analysis complete - found {len(breaks)} potential breaks")
        
        # Step 3: Generate reports
        print("\n📋 Generating reports...")
        reporter = ReportGenerator()
        
        # Generate markdown report
        markdown_report = reporter.generate_summary_report(breaks)
        
        # Save reports
        os.makedirs('reports', exist_ok=True)
        
        with open('reports/dividend_reconciliation_report.md', 'w') as f:
            f.write(markdown_report)
        
        with open('reports/dividend_reconciliation_report.json', 'w') as f:
            f.write(reporter.generate_json_report(breaks))
        
        print("✅ Reports saved:")
        print("   - reports/dividend_reconciliation_report.md")
        print("   - reports/dividend_reconciliation_report.json")
        
        # Display summary
        print("\n" + "=" * 50)
        print("📈 RECONCILIATION SUMMARY")
        print("=" * 50)
        
        if breaks:
            severity_counts = {'high': 0, 'medium': 0, 'low': 0}
            for break_item in breaks:
                severity = break_item.get('severity', 'medium')
                severity_counts[severity] += 1
            
            print(f"🔴 High severity breaks: {severity_counts['high']}")
            print(f"🟡 Medium severity breaks: {severity_counts['medium']}")
            print(f"🟢 Low severity breaks: {severity_counts['low']}")
            
            # Show top 3 priority breaks
            top_breaks = sorted(breaks, key=lambda x: x.get('priority_score', 0), reverse=True)[:3]
            print(f"\n🎯 TOP PRIORITY BREAKS:")
            for i, break_item in enumerate(top_breaks, 1):
                match_data = break_item.get('match_data', {})
                nbim_record = match_data.get('nbim_record')
                custody_record = match_data.get('custody_record')
                
                isin = 'N/A'
                if nbim_record:
                    isin = nbim_record.get('isin', 'N/A')
                elif custody_record:
                    isin = custody_record.get('isin', 'N/A')
                
                print(f"   {i}. {break_item.get('break_type', 'Unknown').replace('_', ' ').title()}")
                print(f"      ISIN: {isin}")
                print(f"      Priority: {break_item.get('priority_score', 'N/A')}/10")
        else:
            print("🎉 No breaks detected - all records reconciled successfully!")
        
        print(f"\n📖 View full report: reports/dividend_reconciliation_report.md")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"❌ Error: Could not find data files - {e}")
        print("Please ensure CSV files are in the ../data directory")
        return 1
    except Exception as e:
        print(f"❌ Error during reconciliation: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
