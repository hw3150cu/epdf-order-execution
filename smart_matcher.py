"""
Smart matcher that finds which contract the agent is trading at each timestamp.
Checks ALL contracts to achieve 100% match rate.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tqdm import tqdm


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
    Checks ALL contracts to achieve maximum match rate.
    """

    def __init__(self, agent_file, contract_dir, tick_tolerance=0):
        """
        Initialize SmartMatcher.

        agent_file: Path to agent data CSV
        contract_dir: Directory containing contract files
        tick_tolerance: Number of ticks to allow outside OHLC range (0 = strict, 1 = allow ±1 tick)
        """
        self.agent_file = agent_file
        self.contract_dir = contract_dir
        self.tick_tolerance = tick_tolerance

        self.agent_df = None
        self.contracts = {}  # {name: df}
        self.matched_df = None

    def load_agent_data(self):
        """Load agent data."""
        print(f"\nLoading agent data from {self.agent_file}...")
        self.agent_df = load_agent_data(self.agent_file)

        print(f"  Loaded {len(self.agent_df)} agent bars")
        print(f"  Date range: {self.agent_df.index.min()} -> {self.agent_df.index.max()}")

    def load_contracts(self):
        """Load all contract files."""
        import os
        import glob

        print(f"\nLoading contracts from {self.contract_dir}...")
        print(f"  Tick tolerance: ±{self.tick_tolerance} ticks")

        contract_files = sorted(
            f for f in glob.glob(os.path.join(self.contract_dir, "*.csv"))
            if not os.path.basename(f).lower().startswith('aiagent')
        )

        for file_path in tqdm(contract_files, desc="Loading contracts"):
            import os
            name = os.path.splitext(os.path.basename(file_path))[0]
            df = load_and_clean_one_csv(file_path)
            self.contracts[name] = df

        print(f"  Loaded {len(self.contracts)} contracts")
        for name in sorted(self.contracts.keys()):
            df = self.contracts[name]
            print(f"    {name}: {df.index.min()} -> {df.index.max()}\n")

    def find_matching_contract(self, timestamp, agent_price, tick_size=0.25):
        """
        Find which contract(s) contain the agent price at this timestamp.

        Returns:
            list of (contract_name, open, high, low, close) tuples
        """
        matches = []

        for name, df in self.contracts.items():
            # Check if this contract has data at this timestamp
            if timestamp not in df.index:
                continue

            row = df.loc[timestamp]

            # Check if agent price is within OHLC range (with tolerance)
            tolerance = self.tick_tolerance * tick_size
            if (row['low'] - tolerance) <= agent_price <= (row['high'] + tolerance):
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
        """
        Match all agent timestamps with available contracts.

        Returns:
            DataFrame with match information for each timestamp
        """
        print("\nMatching agent timestamps with contracts...")

        results = []

        for timestamp, agent_row in tqdm(self.agent_df.iterrows(), total=len(self.agent_df), desc="Matching"):
            agent_price = agent_row['price']
            agent_vol = agent_row['vol']

            # Find matching contracts
            matches = self.find_matching_contract(timestamp, agent_price)

            if len(matches) == 0:
                # No match
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
                # Unique match
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
                # Multiple matches - pick the one with highest volume
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
        unique_matches = (self.matched_df['status'] == 'unique_match').sum()
        multiple_matches = (self.matched_df['status'] == 'multiple_matches').sum()
        no_match = (self.matched_df['status'] == 'no_match').sum()

        total_matches = unique_matches + multiple_matches
        match_rate = (total_matches / total * 100) if total > 0 else 0

        stats = {
            'total_timestamps': total,
            'unique_matches': unique_matches,
            'multiple_matches': multiple_matches,
            'total_matches': total_matches,
            'no_match': no_match,
            'match_rate': match_rate
        }

        return stats

    def get_contract_distribution(self):
        """Get distribution of which contracts were matched."""
        if self.matched_df is None:
            raise ValueError("No matched data. Call match_all_timestamps() first.")

        # Only count matches (not no_match)
        matched_only = self.matched_df[self.matched_df['matched_contract'].notna()]

        distribution = matched_only['matched_contract'].value_counts()

        return distribution

    def analyze_no_matches(self):
        """Analyze timestamps with no matches."""
        if self.matched_df is None:
            raise ValueError("No matched data. Call match_all_timestamps() first.")

        no_matches = self.matched_df[self.matched_df['status'] == 'no_match']

        if len(no_matches) == 0:
            print("No unmatched timestamps!")
            return

        print(f"\nAnalyzing {len(no_matches)} unmatched timestamps...")

        # Check if there's any contract data at these timestamps
        print("\nChecking contract coverage at unmatched timestamps...")

        for timestamp, row in no_matches.head(10).iterrows():
            print(f"\n  Timestamp: {timestamp}")
            print(f"    Agent price: {row['agent_price']:.2f}")

            contracts_at_time = []
            for name, df in self.contracts.items():
                if timestamp in df.index:
                    contracts_at_time.append((name, df.loc[timestamp]['low'], df.loc[timestamp]['high']))

            if len(contracts_at_time) == 0:
                print(f"    No contracts have data at this timestamp")
            else:
                print(f"    Contracts with data: {len(contracts_at_time)}")
                for c_name, c_low, c_high in contracts_at_time:
                    print(f"      {c_name}: [{c_low:.2f}, {c_high:.2f}]")

    def run(self):
        """Run the complete matching pipeline."""
        print("="*70)
        print("SMART CONTRACT MATCHER")
        print("Finds which contract the agent is trading at each timestamp")
        print("="*70)

        # Step 1: Load agent data
        self.load_agent_data()

        # Step 2: Load contracts
        self.load_contracts()

        # Step 3: Match all timestamps
        self.match_all_timestamps()

        # Step 4: Calculate statistics
        stats = self.calculate_statistics()

        print("\n" + "="*70)
        print("MATCH STATISTICS")
        print("="*70)
        print(f"Total timestamps:          {stats['total_timestamps']}")
        print(f"Unique matches:            {stats['unique_matches']} ({stats['unique_matches']/stats['total_timestamps']*100:.1f}%)")
        print(f"Multiple matches:          {stats['multiple_matches']} ({stats['multiple_matches']/stats['total_timestamps']*100:.1f}%)")
        print(f"Total matches:             {stats['total_matches']} ({stats['match_rate']:.1f}%)")
        print(f"No match:                  {stats['no_match']} ({stats['no_match']/stats['total_timestamps']*100:.1f}%)")
        print("="*70)

        # Step 5: Show contract distribution
        print("\nContract Distribution:")
        dist = self.get_contract_distribution()
        for contract, count in dist.items():
            pct = (count / stats['total_matches'] * 100) if stats['total_matches'] > 0 else 0
            print(f"  {contract}: {count} matches ({pct:.1f}%)")

        # Step 6: Analyze no matches if any
        if stats['no_match'] > 0:
            self.analyze_no_matches()

        print("\n" + "="*70)
        print("COMPLETE")
        print("="*70)

        return self.matched_df


if __name__ == '__main__':
    # Example usage - with 1 tick tolerance to handle execution timing
    matcher = SmartMatcher(
        agent_file='data_export/Nasdaq/AIAgent_Nasdaq.csv',
        contract_dir='data_export/Nasdaq',
        tick_tolerance=1  # Allow ±1 tick outside OHLC range
    )

    matched_df = matcher.run()

    # Save results
    output_dir = 'agent_comparison_results'
    import os
    os.makedirs(output_dir, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'{output_dir}/smart_matched_{timestamp}.csv'
    matched_df.to_csv(output_file)

    print(f"\nSaved matched data to: {output_file}")