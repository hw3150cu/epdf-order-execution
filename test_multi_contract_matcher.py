"""
Test multi-contract matching functionality across different asset classes.
"""

from data_matcher import DataMatcher
import pandas as pd

def test_asset_class(asset_name, agent_file, data_dir):
    """Test multi-contract matching for a single asset class."""
    print("\n" + "="*80)
    print(f"TESTING: {asset_name}")
    print("="*80)
    
    matcher = DataMatcher(agent_file, data_dir)
    
    # Run multi-contract matching
    matched_df = matcher.match_data_multi_contract()
    
    if matched_df is None:
        print(f"FAILED: Could not match data for {asset_name}")
        return None
    
    # Get statistics
    total = len(matched_df)
    valid = (matched_df['status'] == 'valid').sum()
    price_invalid = (matched_df['status'] == 'price_invalid').sum()
    unmatched = (matched_df['status'] == 'unmatched').sum()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY: {asset_name}")
    print(f"{'='*80}")
    print(f"Total bars:     {total}")
    print(f"Valid matches:  {valid} ({valid/total*100:.1f}%)")
    print(f"Price invalid:  {price_invalid} ({price_invalid/total*100:.1f}%)")
    print(f"Unmatched:      {unmatched} ({unmatched/total*100:.1f}%)")
    
    # Show contracts breakdown
    if 'matched_contract' in matched_df.columns:
        print(f"\nMatches by contract:")
        contract_counts = matched_df[matched_df['status'] == 'valid'].groupby('matched_contract').size()
        for contract, count in contract_counts.items():
            print(f"  {contract}: {count} bars")
    
    return {
        'total': total,
        'valid': valid,
        'price_invalid': price_invalid,
        'unmatched': unmatched,
        'match_rate': valid / total if total > 0 else 0,
        'matched_df': matched_df
    }


def main():
    """Run tests across multiple asset classes."""
    
    # Define test cases
    test_cases = [
        {
            'name': 'Gold',
            'agent_file': 'data_export/Gold/AIAgent_Gold.csv',
            'data_dir': 'data_export/Gold'
        },
        {
            'name': 'Nasdaq',
            'agent_file': 'data_export/Nasdaq/AIAgent_Nasdaq.csv',
            'data_dir': 'data_export/Nasdaq'
        }
    ]
    
    results = {}
    
    for test_case in test_cases:
        result = test_asset_class(
            test_case['name'],
            test_case['agent_file'],
            test_case['data_dir']
        )
        results[test_case['name']] = result
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL RESULTS SUMMARY")
    print("="*80)
    
    for asset_name, result in results.items():
        if result:
            print(f"\n{asset_name}:")
            print(f"  Match rate: {result['match_rate']*100:.1f}%")
            print(f"  Valid: {result['valid']}/{result['total']}")
        else:
            print(f"\n{asset_name}: FAILED")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()