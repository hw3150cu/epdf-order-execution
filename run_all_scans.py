"""
Comprehensive contract matching across all asset classes.
Scans data_export folder and runs smart matcher for each asset class.
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, timedelta
from tqdm import tqdm

from config import get_tick_size, get_config


def load_and_clean_one_csv(path: str) -> pd.DataFrame:
    """Load and clean a CSV file."""
    df = pd.read_csv(path, header=None)
    df.columns = ["datetime", "open", "high", "low", "close", "volume"]

    # datetime
    df["datetime"] = pd.to_datetime(
        df["datetime"],
        format="%Y.%m.%d.%H:%M:%S",
        errors="coerce"
    )
    df = df.dropna(subset=["datetime"])

    # numeric
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])

    # sort + index
    df = df.sort_values("datetime").set_index("datetime")
    df = df[~df.index.duplicated(keep="last")]

    # Day filtering: remove days with <90% data
    df["date"] = df.index.normalize()
    daily_counts = df.groupby("date").size()
    max_minutes = daily_counts.max()
    threshold = max_minutes * 0.9
    valid_dates = daily_counts[daily_counts >= threshold].index
    df = df[df["date"].isin(valid_dates)]
    df = df.drop(columns=["date"])

    return df


def load_agent_data(agent_file):
    """Load agent data with datetime."""
    df = pd.read_csv(agent_file, header=None,
                    names=['date', 'hour', 'min', 'price', 'cum_vol'])

    # Convert Excel date numbers to timestamps
    start_date = datetime(1900, 1, 1)
    df['datetime'] = df.apply(
        lambda row: start_date + timedelta(days=int(row['date']) - 2,
                                          hours=int(row['hour']),
                                          minutes=int(row['min'])),
        axis=1
    )

    # Set index and sort
    df = df.set_index('datetime').sort_index()
    df = df[~df.index.duplicated(keep='last')]

    # Calculate volume (change in cumulative volume)
    df['vol'] = df['cum_vol'].diff(-1).abs().fillna(0)

    return df


class SmartMatcher:
    """
    Smart matcher that finds which contract the agent is trading at each timestamp.
    """

    def __init__(self, agent_file, contract_files, tick_size=0.25, contract_rollover=None):
        """
        Initialize SmartMatcher.

        agent_file: Path to agent data CSV
        contract_files: List of paths to contract CSV files
        tick_size: Contract tick size
        contract_rollover: Dict {contract_name: rollover_date_str} for rollover filtering
        """
        self.agent_file = agent_file
        self.contract_files = contract_files
        self.tick_size = tick_size
        self.contract_rollover = contract_rollover or {}

        self.agent_df = None
        self.contracts = {}  # {name: df}
        self.matched_df = None

    def load_agent_data(self):
        """Load agent data."""
        self.agent_df = load_agent_data(self.agent_file)

    def load_contracts(self):
        """Load all contract files."""
        for file_path in self.contract_files:
            name = os.path.splitext(os.path.basename(file_path))[0]
            df = load_and_clean_one_csv(file_path)
            self.contracts[name] = df

    def find_matching_contract(self, timestamp, agent_price):
        """Find which contract(s) contain the agent price at this timestamp."""
        matches = []

        for name, df in self.contracts.items():
            # Skip contracts that haven't rolled over yet
            if name in self.contract_rollover:
                rollover_ts = pd.Timestamp(self.contract_rollover[name])
                if timestamp < rollover_ts:
                    continue

            if timestamp not in df.index:
                continue

            row = df.loc[timestamp]

            # Check if agent price is within OHLC range
            if row['low'] <= agent_price <= row['high']:
                matches.append({
                    'contract': name,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                })

        return matches

    def match_all_timestamps(self):
        """Match all agent timestamps with available contracts."""
        results = []

        for timestamp, agent_row in tqdm(self.agent_df.iterrows(), total=len(self.agent_df), desc="Matching"):
            agent_price = agent_row['price']
            agent_vol = agent_row['vol']

            matches = self.find_matching_contract(timestamp, agent_price)

            if len(matches) == 0:
                results.append({
                    'datetime': timestamp,
                    'agent_price': agent_price,
                    'agent_vol': agent_vol,
                    'matched_contract': None,
                    'open': None,
                    'high': None,
                    'low': None,
                    'close': None,
                    'volume': None,
                    'num_matches': 0,
                    'status': 'no_match'
                })
            elif len(matches) == 1:
                results.append({
                    'datetime': timestamp,
                    'agent_price': agent_price,
                    'agent_vol': agent_vol,
                    'matched_contract': matches[0]['contract'],
                    'open': matches[0]['open'],
                    'high': matches[0]['high'],
                    'low': matches[0]['low'],
                    'close': matches[0]['close'],
                    'volume': matches[0]['volume'],
                    'num_matches': 1,
                    'status': 'unique_match'
                })
            else:
                best_match = max(matches, key=lambda x: x['volume'])
                results.append({
                    'datetime': timestamp,
                    'agent_price': agent_price,
                    'agent_vol': agent_vol,
                    'matched_contract': best_match['contract'],
                    'open': best_match['open'],
                    'high': best_match['high'],
                    'low': best_match['low'],
                    'close': best_match['close'],
                    'volume': best_match['volume'],
                    'num_matches': len(matches),
                    'status': 'multiple_matches'
                })

        self.matched_df = pd.DataFrame(results).set_index('datetime')
        return self.matched_df

    def calculate_statistics(self):
        """Calculate match statistics."""
        if self.matched_df is None:
            raise ValueError("No matched data. Call match_all_timestamps() first.")

        total = len(self.matched_df)
        unique_matches = int((self.matched_df['status'] == 'unique_match').sum())
        multiple_matches = int((self.matched_df['status'] == 'multiple_matches').sum())
        no_match = int((self.matched_df['status'] == 'no_match').sum())

        total_matches = unique_matches + multiple_matches
        match_rate = float((total_matches / total * 100) if total > 0 else 0)

        # Filter to actual trades (vol > 0)
        actual_trades = int((self.matched_df['agent_vol'] > 0).sum())
        actual_matches = int(((self.matched_df['agent_vol'] > 0) & (
            self.matched_df['matched_contract'].notna()
        )).sum())
        actual_match_rate = float((actual_matches / actual_trades * 100) if actual_trades > 0 else 0)

        stats = {
            'total_timestamps': total,
            'actual_trades': actual_trades,
            'unique_matches': unique_matches,
            'multiple_matches': multiple_matches,
            'total_matches': total_matches,
            'actual_matches': actual_matches,
            'no_match': no_match,
            'match_rate': match_rate,
            'actual_trade_match_rate': actual_match_rate
        }

        return stats

    def get_contract_distribution(self):
        """Get distribution of which contracts were matched."""
        if self.matched_df is None:
            return pd.Series()

        matched_only = self.matched_df[self.matched_df['matched_contract'].notna()]
        return matched_only['matched_contract'].value_counts()

    def run(self):
        """Run the complete matching pipeline."""
        self.load_agent_data()
        self.load_contracts()
        self.match_all_timestamps()
        return self.calculate_statistics()


def discover_asset_classes(data_dir='data_export'):
    """
    Discover all asset classes (subdirectories) in data_export.

    Returns:
        dict: {asset_class: {'agent_file': path, 'contract_files': [paths]}}
    """
    asset_classes = {}

    for asset_name in os.listdir(data_dir):
        asset_path = os.path.join(data_dir, asset_name)

        if not os.path.isdir(asset_path):
            continue

        # Find agent file
        agent_files = glob.glob(os.path.join(asset_path, 'AIAgent_*.csv'))

        if not agent_files:
            continue

        agent_file = agent_files[0]

        # Find contract files (non-agent files)
        contract_files = sorted(
            f for f in glob.glob(os.path.join(asset_path, '*.csv'))
            if not os.path.basename(f).lower().startswith('aiagent')
        )

        if not contract_files:
            continue

        asset_classes[asset_name] = {
            'agent_file': agent_file,
            'contract_files': contract_files
        }

    return asset_classes


# get_tick_size is now imported from config.py — single source of truth


def run_all_asset_scans(data_dir='data_export', output_dir='agent_comparison_results'):
    """
    Scan all asset classes and generate comprehensive reports.

    Args:
        data_dir: Base directory containing asset class folders
        output_dir: Output directory for results
    """
    print("="*70)
    print("COMPREHENSIVE CONTRACT MATCHING ACROSS ALL ASSET CLASSES")
    print("="*70)

    # Discover asset classes
    print(f"\nScanning {data_dir} for asset classes...")
    asset_classes = discover_asset_classes(data_dir)

    print(f"Found {len(asset_classes)} asset classes:")
    for asset_name in sorted(asset_classes.keys()):
        info = asset_classes[asset_name]
        print(f"  {asset_name}:")
        print(f"    Agent file: {os.path.basename(info['agent_file'])}")
        print(f"    Contracts: {len(info['contract_files'])}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Store all results
    all_results = []

    # Process each asset class
    for asset_name in sorted(asset_classes.keys()):
        print("\n" + "="*70)
        print(f"Processing: {asset_name}")
        print("="*70)

        info = asset_classes[asset_name]
        tick_size = get_tick_size(asset_name)
        asset_config = get_config(asset_name)
        contract_rollover = asset_config.get('contract_rollover', {})

        # Run matcher
        matcher = SmartMatcher(
            agent_file=info['agent_file'],
            contract_files=info['contract_files'],
            tick_size=tick_size,
            contract_rollover=contract_rollover
        )

        try:
            stats = matcher.run()

            # Get contract distribution
            dist = matcher.get_contract_distribution()

            print(f"\nResults:")
            print(f"  Total timestamps:       {stats['total_timestamps']}")
            print(f"  Actual trades:          {stats['actual_trades']}")
            print(f"  Unique matches:         {stats['unique_matches']}")
            print(f"  Multiple matches:       {stats['multiple_matches']}")
            print(f"  Total matches:          {stats['total_matches']} ({stats['match_rate']:.1f}%)")
            print(f"  Actual trades matched:  {stats['actual_matches']} ({stats['actual_trade_match_rate']:.1f}%)")
            print(f"  No match:               {stats['no_match']}")

            print(f"\nContract Distribution:")
            for contract, count in dist.items():
                pct = (count / stats['total_matches'] * 100) if stats['total_matches'] > 0 else 0
                print(f"  {contract}: {count} ({pct:.1f}%)")

            # Save matched data
            timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
            safe_asset_name = asset_name.replace(' ', '_').replace('-', '_')
            output_file = f'{output_dir}/smart_matched_{safe_asset_name}_{timestamp}.csv'
            matcher.matched_df.to_csv(output_file)

            print(f"\nSaved matched data to: {output_file}")

            # Store results
            result = {
                'asset_class': asset_name,
                'tick_size': tick_size,
                'total_timestamps': stats['total_timestamps'],
                'actual_trades': stats['actual_trades'],
                'unique_matches': stats['unique_matches'],
                'multiple_matches': stats['multiple_matches'],
                'total_matches': stats['total_matches'],
                'actual_matches': stats['actual_matches'],
                'no_match': stats['no_match'],
                'match_rate': stats['match_rate'],
                'actual_trade_match_rate': stats['actual_trade_match_rate'],
                'num_contracts': len(info['contract_files']),
                'matched_file': output_file
            }

            # Add contract distribution
            for contract, count in dist.items():
                result[f'contract_{contract}'] = count

            all_results.append(result)

        except Exception as e:
            print(f"ERROR processing {asset_name}: {e}")
            import traceback
            traceback.print_exc()
            continue  # Skip to next asset class

    # Generate summary report
    print("\n" + "="*70)
    print("SUMMARY REPORT")
    print("="*70)

    if not all_results:
        print("No valid results generated!")
        return None

    summary_df = pd.DataFrame(all_results)

    # Reorder columns for readability
    cols = ['asset_class', 'total_timestamps', 'actual_trades', 'total_matches',
            'match_rate', 'actual_trade_match_rate', 'no_match', 'num_contracts', 'matched_file']

    # Add contract columns if they exist
    contract_cols = [c for c in summary_df.columns if c.startswith('contract_')]
    cols.extend(contract_cols)

    # Only keep columns that exist
    cols = [c for c in cols if c in summary_df.columns]
    summary_df = summary_df[cols]

    print("\nSummary Table:")
    print(summary_df.to_string(index=False))

    # Save summary
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    summary_file = f'{output_dir}/summary_report_{timestamp}.csv'
    summary_df.to_csv(summary_file, index=False)

    print(f"\nSaved summary report to: {summary_file}")

    # Also save as markdown
    md_file = f'{output_dir}/summary_report_{timestamp}.md'

    with open(md_file, 'w') as f:
        f.write("# Contract Matching Summary Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary Table\n\n")
        f.write(summary_df.to_string(index=False))
        f.write("\n\n## Detailed Results\n\n")

        for result in all_results:
            f.write(f"### {result['asset_class']}\n\n")
            f.write(f"- **Tick Size**: {result['tick_size']}\n")
            f.write(f"- **Total Timestamps**: {result['total_timestamps']}\n")
            f.write(f"- **Actual Trades**: {result['actual_trades']}\n")
            f.write(f"- **Total Matches**: {result['total_matches']} ({result['match_rate']:.1f}%)\n")
            f.write(f"- **Actual Trade Matches**: {result['actual_matches']} ({result['actual_trade_match_rate']:.1f}%)\n")
            f.write(f"- **No Match**: {result['no_match']}\n")
            f.write(f"- **Number of Contracts**: {result['num_contracts']}\n\n")
            f.write("**Contract Distribution**:\n\n")
            for key in result:
                if key.startswith('contract_'):
                    contract = key.replace('contract_', '')
                    count = result[key]
                    pct = (count / result['total_matches'] * 100) if result['total_matches'] > 0 else 0
                    f.write(f"- {contract}: {count} ({pct:.1f}%)\n")
            f.write("\n")

    print(f"Saved markdown report to: {md_file}")

    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)

    return summary_df


if __name__ == '__main__':
    summary = run_all_asset_scans(
        data_dir='data_export',
        output_dir='agent_comparison_results'
    )