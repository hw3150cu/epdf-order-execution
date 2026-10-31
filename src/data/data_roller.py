"""
Data Roller Module

Uses volume-based rolling to match agent data across multiple futures contracts.

Methodology:
1. Roll contracts based on volume dominance (new contract >= 1.2x old contract volume)
2. Validate agent's price falls within the active contract's OHLC range
3. Provide comprehensive statistics
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta


class DataRoller:
    """
    Match agent data using volume-based rolling across contracts.
    
    This approach:
    1. Determines which contract to use at each time based on volume dominance
    2. Validates that agent's price falls within the chosen contract's OHLC range
    """

    def __init__(self, agent_file, data_dir):
        """
        Initialize DataRoller.

        Args:
            agent_file: Path to agent data CSV
            data_dir: Directory containing futures data (e.g., 'data_export/Nasdaq')
        """
        self.agent_file = agent_file
        self.data_dir = data_dir
        self.agent_df = None
        self.contract_dfs = {}

    def load_agent_data(self):
        """Load and preprocess agent trading data."""
        print(f"Loading agent data from {self.agent_file}...")

        df = pd.read_csv(self.agent_file, header=None,
                        names=['date', 'hour', 'min', 'price', 'cum_vol'])

        # Convert Excel date numbers to timestamps
        start_date = datetime(1900, 1, 1)
        df['datetime'] = df.apply(
            lambda row: start_date + timedelta(days=int(row['date']) - 2,
                                              hours=int(row['hour']),
                                              minutes=int(row['min'])),
            axis=1
        )

        # Calculate bar volume (difference from next row)
        df['vol'] = df['cum_vol'].diff(-1).abs().fillna(0)

        # Set datetime as index and sort
        df = df.set_index('datetime').sort_index()

        self.agent_df = df

        print(f"  Loaded {len(df)} bars")
        print(f"  Date range: {df.index.min()} to {df.index.max()}")
        print(f"  Price range: {df['price'].min():.2f} to {df['price'].max():.2f}")

        return df

    def load_contracts(self):
        """Load all contract files from data_dir."""
        print(f"\nLoading contracts from {self.data_dir}...")

        contracts = {}

        # Find contract files (exclude AIAgent files)
        contract_files = [f for f in os.listdir(self.data_dir)
                         if f.endswith('.csv') and 'AIAgent' not in f]

        for file in sorted(contract_files):
            file_path = os.path.join(self.data_dir, file)
            contract_name = file.replace('.csv', '')

            print(f"  Loading {file}...")

            df = pd.read_csv(file_path, header=None,
                           names=['ts', 'open', 'high', 'low', 'close', 'vol'])
            df['datetime'] = pd.to_datetime(df['ts'], format='%Y.%m.%d.%H:%M:%S')
            df = df.set_index('datetime').sort_index()

            contracts[contract_name] = df

            print(f"    {len(df)} bars: {df.index.min()} to {df.index.max()}")
            print(f"    Price range: {df['low'].min():.2f} to {df['high'].max():.2f}")

        self.contract_dfs = contracts
        return contracts

    def resample_to_5min(self, df):
        """Resample data to 5-minute intervals."""
        return df.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum'
        }).dropna()

    def find_roll_time_by_volume(self, dfA, dfB, vol_col="vol",
                                 W=60, r=1.2, K=60):
        """
        Find roll time between two contracts based on volume dominance.

        Args:
            dfA: Old contract DataFrame
            dfB: New contract DataFrame
            vol_col: Volume column name
            W: Rolling window size in minutes
            r: Lead multiplier (e.g., 1.2 means 20% advantage)
            K: Consecutive confirmation minutes

        Returns:
            Roll timestamp or None if not found
        """
        A = dfA.sort_index()
        B = dfB.sort_index()

        idx = A.index.intersection(B.index)
        if len(idx) == 0:
            return None

        vA = A.loc[idx, vol_col].rolling(W, min_periods=W).mean()
        vB = B.loc[idx, vol_col].rolling(W, min_periods=W).mean()

        lead = (vB >= r * vA).astype(int)
        confirm = lead.rolling(K, min_periods=K).sum() == K

        if not confirm.any():
            return None

        return confirm[confirm].index[0]

    def sort_dfs_by_start(self, dfs):
        """Sort contracts by start time."""
        meta = []
        for name, df in dfs:
            if df is None or df.empty:
                continue
            meta.append((df.index.min(), df.index.max(), name, df))
        meta.sort(key=lambda x: x[0])
        return meta

    def compute_roll_schedule(self, sorted_meta, vol_col="vol",
                              W=60, r=1.2, K=60,
                              fallback="next_start"):
        """
        Compute roll schedule between consecutive contracts.

        Returns:
            List of (nameA, nameB, roll_time) tuples
        """
        roll_times = []
        for i in range(len(sorted_meta) - 1):
            _, _, nameA, dfA = sorted_meta[i]
            _, _, nameB, dfB = sorted_meta[i+1]

            t = self.find_roll_time_by_volume(dfA, dfB, vol_col=vol_col,
                                              W=W, r=r, K=K)

            if t is None and fallback == "next_start":
                t = dfB.index.min()

            roll_times.append((nameA, nameB, t))
        return roll_times

    def match_agent_data(self, W=60, r=1.2, K=60, fallback="next_start"):
        """
        Match agent data using volume-based rolling across contracts.

        Returns:
            DataFrame with matched data including 'matched_contract' column
        """
        print("\n" + "="*70)
        print("VOLUME-BASED ROLLING MATCHING")
        print("="*70)
        print(f"Roll parameters: W={W}, r={r}, K={K}")

        # Load agent data
        self.load_agent_data()

        # Load contracts
        self.load_contracts()

        if not self.contract_dfs:
            print("  ERROR: No contracts found")
            return None

        # Resample all contracts to 5-minute bars
        print("\nResampling contracts to 5-minute bars...")
        contracts_5min = {}
        for contract_name, df in self.contract_dfs.items():
            contracts_5min[contract_name] = self.resample_to_5min(df)
            print(f"  {contract_name}: {len(contracts_5min[contract_name])} bars")

        # Sort contracts by start time
        print("\nSorting contracts by start time...")
        dfs = [(name, df) for name, df in contracts_5min.items()]
        sorted_meta = self.sort_dfs_by_start(dfs)

        print("Sorted contracts:")
        for s, e, nm, _ in sorted_meta:
            print(f"  {nm}: {s} -> {e}")

        # Compute roll schedule using volume dominance
        print("\nComputing roll schedule based on volume dominance...")
        roll_times = self.compute_roll_schedule(sorted_meta, vol_col="vol",
                                                W=W, r=r, K=K,
                                                fallback=fallback)

        print("\nRoll schedule:")
        for a, b, t in roll_times:
            print(f"  {a} -> {b} at {t}")

        # Create a mapping of datetime -> active contract
        print("\nCreating contract mapping...")
        active_contract_map = {}

        for i, (start, end, name, df) in enumerate(sorted_meta):
            if i == 0:
                # First contract: from start to first roll time
                if len(roll_times) > 0:
                    t_end = roll_times[0][2]
                    segment_times = df.index[df.index < t_end]
                else:
                    segment_times = df.index
            elif i == len(sorted_meta) - 1:
                # Last contract: from last roll time to end
                if len(roll_times) > 0:
                    t_start = roll_times[-1][2]
                    segment_times = df.index[df.index >= t_start]
                else:
                    segment_times = df.index
            else:
                # Middle contracts: between adjacent roll times
                t_start = roll_times[i-1][2]
                t_end = roll_times[i][2]
                segment_times = df.index[(df.index >= t_start) & (df.index < t_end)]

            for ts in segment_times:
                active_contract_map[ts] = name

        print(f"  Created mapping for {len(active_contract_map)} timestamps")

        # Initialize result DataFrame with agent data
        result_df = self.agent_df.copy()
        result_df['matched_contract'] = None
        result_df['open'] = np.nan
        result_df['high'] = np.nan
        result_df['low'] = np.nan
        result_df['close'] = np.nan
        result_df['vol_ours'] = np.nan
        result_df['status'] = 'unmatched'
        result_df['status_reason'] = 'No matching contract found'

        # Track matching statistics per contract
        contract_stats = {name: {'matched': 0, 'price_valid': 0, 'price_invalid': 0}
                         for name in contracts_5min.keys()}

        # Match each agent timestamp to the active contract
        print("\nMatching agent timestamps to active contracts...")
        matched_count = 0
        valid_count = 0

        for idx in result_df.index:
            agent_price = result_df.loc[idx, 'price']

            # Determine which contract should be active at this time
            active_contract = active_contract_map.get(idx, None)

            if active_contract is None:
                result_df.loc[idx, 'status_reason'] = f'No active contract at {idx}'
                continue

            # Check if the active contract has data at this timestamp
            if active_contract not in contracts_5min:
                result_df.loc[idx, 'status_reason'] = f'Contract {active_contract} not loaded'
                continue

            contract_df = contracts_5min[active_contract]

            if idx not in contract_df.index:
                result_df.loc[idx, 'status_reason'] = f'No data in {active_contract} at {idx}'
                continue

            matched_count += 1
            bar_data = contract_df.loc[idx]

            # Validate price falls within OHLC range
            if bar_data['low'] <= agent_price <= bar_data['high']:
                # Valid match: correct contract + price validation
                result_df.loc[idx, 'matched_contract'] = active_contract
                result_df.loc[idx, 'open'] = bar_data['open']
                result_df.loc[idx, 'high'] = bar_data['high']
                result_df.loc[idx, 'low'] = bar_data['low']
                result_df.loc[idx, 'close'] = bar_data['close']
                result_df.loc[idx, 'vol_ours'] = bar_data['vol']
                result_df.loc[idx, 'status'] = 'valid'
                result_df.loc[idx, 'status_reason'] = f'Valid: matched with {active_contract}'
                contract_stats[active_contract]['matched'] += 1
                contract_stats[active_contract]['price_valid'] += 1
                valid_count += 1
            else:
                # Price invalid: correct contract but price outside OHLC
                result_df.loc[idx, 'matched_contract'] = active_contract
                result_df.loc[idx, 'open'] = bar_data['open']
                result_df.loc[idx, 'high'] = bar_data['high']
                result_df.loc[idx, 'low'] = bar_data['low']
                result_df.loc[idx, 'close'] = bar_data['close']
                result_df.loc[idx, 'vol_ours'] = bar_data['vol']
                result_df.loc[idx, 'status'] = 'price_invalid'
                result_df.loc[idx, 'status_reason'] = (
                    f'Price invalid in {active_contract}: '
                    f'agent_price={agent_price:.2f} outside '
                    f'OHLC [{bar_data["low"]:.2f}, {bar_data["high"]:.2f}]'
                )
                contract_stats[active_contract]['matched'] += 1
                contract_stats[active_contract]['price_invalid'] += 1

        # Add flags
        result_df['is_matched'] = (result_df['status'] == 'valid')
        result_df['has_data'] = result_df['open'].notna()
        result_df['price_valid'] = (result_df['status'] == 'valid')

        # Print statistics
        total_bars = len(result_df)
        valid_bars = (result_df['status'] == 'valid').sum()
        price_invalid_bars = (result_df['status'] == 'price_invalid').sum()
        unmatched_bars = (result_df['status'] == 'unmatched').sum()

        print("\n" + "-"*70)
        print("MATCHING RESULTS (VOLUME-BASED ROLLING)")
        print("-"*70)
        print(f"\nOverall Statistics:")
        print(f"  Total agent bars: {total_bars}")
        print(f"  Matched to active contract: {matched_count} ({matched_count/total_bars*100:.1f}%)")
        print(f"  Valid (price within OHLC): {valid_bars} ({valid_bars/total_bars*100:.1f}%)")
        print(f"  Price invalid: {price_invalid_bars} ({price_invalid_bars/total_bars*100:.1f}%)")
        print(f"  Unmatched (no active contract): {unmatched_bars} ({unmatched_bars/total_bars*100:.1f}%)")

        print(f"\nPer-Contract Statistics:")
        for contract_name in sorted(contract_stats.keys()):
            stats = contract_stats[contract_name]
            if stats['matched'] > 0:
                print(f"  {contract_name}:")
                print(f"    Total matched: {stats['matched']}")
                print(f"    Price valid: {stats['price_valid']}")
                print(f"    Price invalid: {stats['price_invalid']}")
                if stats['matched'] > 0:
                    print(f"    Price validation rate: {stats['price_valid']/stats['matched']*100:.1f}%")

        # Show date ranges per contract for valid matches
        print(f"\nValid Matches by Contract (Date Ranges):")
        for contract_name in sorted(contract_stats.keys()):
            valid_mask = (result_df['matched_contract'] == contract_name) & (result_df['status'] == 'valid')
            if valid_mask.sum() > 0:
                contract_data = result_df[valid_mask]
                print(f"  {contract_name}:")
                print(f"    Bars: {len(contract_data)}")
                print(f"    Date range: {contract_data.index.min()} to {contract_data.index.max()}")

        print("="*70)

        return result_df


if __name__ == '__main__':
    # Test with Nasdaq
    roller = DataRoller(
        agent_file='data_export/Nasdaq/AIAgent_Nasdaq.csv',
        data_dir='data_export/Nasdaq'
    )
    result = roller.match_agent_data(W=60, r=1.2, K=60)

    if result is not None:
        print(f"\nValid matches: {(result['status'] == 'valid').sum()}")
        print(f"Total matched to contract: {result['matched_contract'].notna().sum()}")