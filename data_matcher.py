"""
Data Matcher Module

Reusable utilities for:
1. Identifying which futures contract agent is trading
2. Matching agent timestamps with our data
3. Calculating match statistics

Usage:
    matcher = DataMatcher(agent_file, data_dir)
    contract_info = matcher.identify_contract()
    matched_df = matcher.match_data(contract_info['best_contract'])
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


class DataMatcher:
    """
    Match agent trading data with our bar data.

    Handles:
    - Loading and preprocessing agent data
    - Identifying which futures contract is being traded
    - Resampling our data to 5-minute bars
    - Matching timestamps between datasets
    - Providing match statistics
    """

    def __init__(self, agent_file, data_dir='data_export'):
        """
        Initialize DataMatcher.

        Args:
            agent_file: Path to agent data CSV
            data_dir: Directory containing our futures data
        """
        self.agent_file = agent_file
        self.data_dir = data_dir
        self.agent_df = None
        self.our_dfs = {}
        self.matched_df = None

    def load_agent_data(self):
        """
        Load and preprocess agent trading data.

        Returns:
            DataFrame with datetime index, price, vol
        """
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

    def load_future_contracts(self, future_name):
        """
        Load all contract files for a given future.

        Args:
            future_name: Name of future (e.g., 'Nasdaq', 'GBP')

        Returns:
            Dict mapping contract names to DataFrames
        """
        print(f"\nLoading contracts for {future_name}...")

        data_path = os.path.join(self.data_dir, future_name)

        if not os.path.exists(data_path):
            print(f"  ERROR: Directory not found: {data_path}")
            return {}

        # Find contract files (exclude AIAgent files)
        contract_files = [f for f in os.listdir(data_path)
                         if f.endswith('.csv') and 'AIAgent' not in f]

        if not contract_files:
            print(f"  ERROR: No contract files found in {data_path}")
            return {}

        contracts = {}
        for file in sorted(contract_files):
            file_path = os.path.join(data_path, file)
            contract_name = file.replace('.csv', '')

            print(f"  Loading {file}...")

            df = pd.read_csv(file_path, header=None,
                           names=['ts', 'open', 'high', 'low', 'close', 'vol'])
            df['datetime'] = pd.to_datetime(df['ts'], format='%Y.%m.%d.%H:%M:%S')
            df = df.set_index('datetime').sort_index()

            contracts[contract_name] = df

            print(f"    {len(df)} bars: {df.index.min()} to {df.index.max()}")
            print(f"    Price range: {df['low'].min():.2f} to {df['high'].max():.2f}")

        self.our_dfs = contracts
        return contracts

    def resample_to_5min(self, df):
        """
        Resample data to 5-minute intervals using OHLC aggregation.

        Args:
            df: DataFrame with datetime index and OHLCV columns

        Returns:
            Resampled DataFrame with 5-minute bars
        """
        df_resampled = df.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum'
        }).dropna()

        return df_resampled

    def calculate_overlap(self, agent_df, our_df, validate_price=True):
        """
        Calculate overlap statistics between agent and our data.

        Args:
            agent_df: Agent data with datetime index and 'price' column
            our_df: Our data with datetime index and OHLC columns
            validate_price: Whether to validate agent price falls within OHLC range

        Returns:
            Dict with overlap statistics
        """
        # Find common date range
        start_common = max(agent_df.index.min(), our_df.index.min())
        end_common = min(agent_df.index.max(), our_df.index.max())

        # Filter to common range
        agent_common = agent_df[(agent_df.index >= start_common) &
                               (agent_df.index <= end_common)]
        our_common = our_df[(our_df.index >= start_common) &
                           (our_df.index <= end_common)]

        # Match timestamps
        matched = agent_common.join(our_common, how='left', rsuffix='_ours')
        matched_count = matched['open'].notna().sum()
        total_count = len(agent_common)

        # Validate prices if requested
        price_valid_count = 0
        price_invalid_count = 0
        if validate_price and matched_count > 0:
            matched_with_data = matched[matched['open'].notna()].copy()
            
            # Check if agent price falls within OHLC range
            price_in_range = (
                (matched_with_data['price'] >= matched_with_data['low']) &
                (matched_with_data['price'] <= matched_with_data['high'])
            )
            price_valid_count = price_in_range.sum()
            price_invalid_count = (~price_in_range).sum()

        return {
            'start_common': start_common,
            'end_common': end_common,
            'agent_bars_common': len(agent_common),
            'our_bars_common': len(our_common),
            'matched_bars': matched_count,
            'unmatched_bars': total_count - matched_count,
            'match_rate': matched_count / total_count if total_count > 0 else 0,
            'price_valid_bars': price_valid_count,
            'price_invalid_bars': price_invalid_count,
            'price_validation_rate': price_valid_count / matched_count if matched_count > 0 else 0,
            'price_overlap_range': (
                max(agent_df['price'].min(), our_df['low'].min()),
                min(agent_df['price'].max(), our_df['high'].max())
            )
        }

    def identify_contract(self, future_name):
        """
        Identify which futures contract the agent is trading.

        Uses:
        1. Date range overlap
        2. Price range overlap
        3. Match rate (timestamp matching)

        Args:
            future_name: Name of future (e.g., 'Nasdaq', 'GBP')

        Returns:
            Dict with best contract and statistics
        """
        print("\n" + "="*70)
        print("IDENTIFYING CONTRACT")
        print("="*70)

        # Load agent data
        self.load_agent_data()

        # Load all contracts
        contracts = self.load_future_contracts(future_name)

        if not contracts:
            return {'error': 'No contracts found'}

        # Resample all contracts to 5-minute bars
        print("\nResampling contracts to 5-minute bars...")
        contracts_5min = {}
        for contract_name, df in contracts.items():
            contracts_5min[contract_name] = self.resample_to_5min(df)
            print(f"  {contract_name}: {len(contracts_5min[contract_name])} bars (5-minute)")

        # Calculate overlap for each contract
        print("\nCalculating overlap statistics...")
        results = []

        for contract_name, df in contracts_5min.items():
            overlap = self.calculate_overlap(self.agent_df, df, validate_price=True)
            overlap['contract'] = contract_name

            # Calculate score (weighted combination of metrics)
            # Now includes price validation rate
            score = (
                overlap['match_rate'] * 0.4 +  # 40% weight on match rate
                overlap['price_validation_rate'] * 0.3 +  # 30% weight on price validation
                (1 if overlap['unmatched_bars'] < len(self.agent_df) * 0.1 else 0) * 0.2 +  # 20% if <10% unmatched
                (overlap['price_overlap_range'][1] - overlap['price_overlap_range'][0]) * 0.1  # 10% price range
            )
            overlap['score'] = score

            results.append(overlap)

            print(f"\n{contract_name}:")
            print(f"  Date overlap: {overlap['start_common']} to {overlap['end_common']}")
            print(f"  Match rate: {overlap['match_rate']*100:.1f}%")
            print(f"  Matched bars: {overlap['matched_bars']}")
            print(f"  Unmatched bars: {overlap['unmatched_bars']}")
            print(f"  Price validation: {overlap['price_validation_rate']*100:.1f}%")
            print(f"    Valid prices: {overlap['price_valid_bars']}")
            print(f"    Invalid prices: {overlap['price_invalid_bars']}")
            print(f"  Price overlap: {overlap['price_overlap_range'][0]:.2f} to {overlap['price_overlap_range'][1]:.2f}")
            print(f"  Score: {score:.3f}")

        # Find best contract
        results.sort(key=lambda x: x['score'], reverse=True)
        best = results[0]

        print("\n" + "="*70)
        print(f"BEST CONTRACT: {best['contract']}")
        print("="*70)
        print(f"  Match rate: {best['match_rate']*100:.1f}%")
        print(f"  Matched: {best['matched_bars']}")
        print(f"  Unmatched: {best['unmatched_bars']}")
        print(f"  Date range: {best['start_common']} to {best['end_common']}")
        print("="*70)

        return {
            'best_contract': best['contract'],
            'best_match_rate': best['match_rate'],
            'all_results': results
        }

    def match_data(self, contract_name):
        """
        Match agent data with a specific contract.

        Args:
            contract_name: Name of contract (e.g., 'NQH20')

        Returns:
            DataFrame with matched data
        """
        print(f"\nMatching agent data with {contract_name}...")

        # Load agent data if not already loaded
        if self.agent_df is None:
            self.load_agent_data()

        # Load contract data
        # If contract name has underscore, extract the prefix as subdirectory name
        # Otherwise, look directly in data_dir (no subdirectory)
        if '_' in contract_name:
            subdir = contract_name[:contract_name.find('_')]
            contract_path = os.path.join(self.data_dir, subdir, f"{contract_name}.csv")
        else:
            contract_path = os.path.join(self.data_dir, f"{contract_name}.csv")

        if not os.path.exists(contract_path):
            print(f"  ERROR: Contract file not found: {contract_path}")
            return None

        df = pd.read_csv(contract_path, header=None,
                        names=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['datetime'] = pd.to_datetime(df['ts'], format='%Y.%m.%d.%H:%M:%S')
        df = df.set_index('datetime').sort_index()

        # Resample to 5-minute bars
        df_5min = self.resample_to_5min(df)

        # Match timestamps with price validation
        overlap = self.calculate_overlap(self.agent_df, df_5min, validate_price=True)

        # Join on timestamp
        matched = self.agent_df.join(df_5min, how='left', rsuffix='_ours')

        print(f"  Matched bars: {overlap['matched_bars']}/{overlap['agent_bars_common']} ({overlap['match_rate']*100:.1f}%)")
        print(f"  Price validated: {overlap['price_valid_bars']}/{overlap['matched_bars']} ({overlap['price_validation_rate']*100:.1f}%)")
        print(f"  Price invalid: {overlap['price_invalid_bars']}")
        print(f"  Unmatched bars: {overlap['unmatched_bars']}")

        # Add detailed status and reason columns
        matched['has_data'] = matched['open'].notna()
        matched['price_valid'] = False
        matched.loc[
            matched['has_data'] & 
            (matched['price'] >= matched['low']) & 
            (matched['price'] <= matched['high']),
            'price_valid'
        ] = True
        
        # Determine match status and reason
        def get_match_status(row):
            if not row['has_data']:
                return 'no_data', f'No data in {contract_name} at this timestamp'
            elif not row['price_valid']:
                return 'price_invalid', f'Price {row["price"]:.2f} outside OHLC range [{row["low"]:.2f}, {row["high"]:.2f}]'
            else:
                return 'valid', 'Timestamp matched and price validated'
        
        matched[['status', 'status_reason']] = matched.apply(
            lambda row: pd.Series(get_match_status(row)),
            axis=1
        )
        
        # Add is_matched flag (only true if both timestamp and price valid)
        matched['is_matched'] = (matched['status'] == 'valid')

        self.matched_df = matched
        return matched

    def match_data_multi_contract(self, future_name=None):
        """
        Match agent data across ALL available contracts for an asset class.
        
        This handles the case where the AI agent trades multiple contracts over time
        (e.g., rolling from front month to next month contract).
        
        Args:
            future_name: Name of future (e.g., 'Gold', 'Nasdaq'). 
                        If None, extracted from agent_file path.
        
        Returns:
            DataFrame with matched data including 'matched_contract' column
        """
        print("\n" + "="*70)
        print("MULTI-CONTRACT MATCHING")
        print("="*70)
        
        # Load agent data if not already loaded
        if self.agent_df is None:
            self.load_agent_data()
        
        # Extract future name from agent_file path if not provided
        if future_name is None:
            # Try to extract from agent_file path
            if '/' in self.agent_file:
                future_name = self.agent_file.split('/')[-2]
            else:
                print("  ERROR: Could not determine future name. Please provide future_name parameter.")
                return None
        
        # Load all contracts for this asset class
        # Check if data_dir already points to the asset-specific directory
        # by checking if it contains CSV files directly
        direct_csv_files = [f for f in os.listdir(self.data_dir) 
                           if f.endswith('.csv') and 'AIAgent' not in f] if os.path.exists(self.data_dir) else []
        
        if direct_csv_files:
            # data_dir already points to the asset-specific directory
            contracts = {}
            data_path = self.data_dir
            print(f"\nLoading contracts from {data_path}...")
            
            for file in sorted(direct_csv_files):
                file_path = os.path.join(data_path, file)
                contract_name = file.replace('.csv', '')
                
                print(f"  Loading {file}...")
                
                df = pd.read_csv(file_path, header=None,
                               names=['ts', 'open', 'high', 'low', 'close', 'vol'])
                df['datetime'] = pd.to_datetime(df['ts'], format='%Y.%m.%d.%H:%M:%S')
                df = df.set_index('datetime').sort_index()
                
                contracts[contract_name] = df
                
                print(f"    {len(df)} bars: {df.index.min()} to {df.index.max()}")
                print(f"    Price range: {df['low'].min():.2f} to {df['high'].max():.2f}")
        else:
            # data_dir points to parent directory, need to use future_name as subdirectory
            contracts = self.load_future_contracts(future_name)
        
        if not contracts:
            print(f"  ERROR: No contracts found for {future_name}")
            return None
        
        # Resample all contracts to 5-minute bars
        print("\nResampling contracts to 5-minute bars...")
        contracts_5min = {}
        for contract_name, df in contracts.items():
            contracts_5min[contract_name] = self.resample_to_5min(df)
            print(f"  {contract_name}: {len(contracts_5min[contract_name])} bars (5-minute)")
        
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
        
        # For each agent timestamp, find the best matching contract
        print("\nMatching timestamps across all contracts...")
        for idx in result_df.index:
            agent_price = result_df.loc[idx, 'price']
            
            best_contract = None
            best_data = None
            
            # Check each contract
            for contract_name, contract_df in contracts_5min.items():
                # Check if timestamp exists in this contract
                if idx in contract_df.index:
                    bar_data = contract_df.loc[idx]
                    
                    # Check if price is within OHLC range
                    if bar_data['low'] <= agent_price <= bar_data['high']:
                        # This is a valid match
                        if best_contract is None:
                            best_contract = contract_name
                            best_data = bar_data
                        else:
                            # If multiple contracts match, prefer the one with tighter range
                            # (more specific match)
                            current_range = best_data['high'] - best_data['low']
                            new_range = bar_data['high'] - bar_data['low']
                            if new_range < current_range:
                                best_contract = contract_name
                                best_data = bar_data
            
            # Record the match result
            if best_contract is not None:
                result_df.loc[idx, 'matched_contract'] = best_contract
                result_df.loc[idx, 'open'] = best_data['open']
                result_df.loc[idx, 'high'] = best_data['high']
                result_df.loc[idx, 'low'] = best_data['low']
                result_df.loc[idx, 'close'] = best_data['close']
                result_df.loc[idx, 'vol_ours'] = best_data['vol']
                result_df.loc[idx, 'status'] = 'valid'
                result_df.loc[idx, 'status_reason'] = f'Matched with {best_contract}'
                contract_stats[best_contract]['matched'] += 1
                contract_stats[best_contract]['price_valid'] += 1
            else:
                # Check if timestamp exists in any contract but price doesn't match
                for contract_name, contract_df in contracts_5min.items():
                    if idx in contract_df.index:
                        bar_data = contract_df.loc[idx]
                        result_df.loc[idx, 'matched_contract'] = contract_name
                        result_df.loc[idx, 'open'] = bar_data['open']
                        result_df.loc[idx, 'high'] = bar_data['high']
                        result_df.loc[idx, 'low'] = bar_data['low']
                        result_df.loc[idx, 'close'] = bar_data['close']
                        result_df.loc[idx, 'vol_ours'] = bar_data['vol']
                        result_df.loc[idx, 'status'] = 'price_invalid'
                        result_df.loc[idx, 'status_reason'] = (
                            f'Price {agent_price:.2f} outside OHLC [{bar_data["low"]:.2f}, {bar_data["high"]:.2f}] in {contract_name}'
                        )
                        contract_stats[contract_name]['matched'] += 1
                        contract_stats[contract_name]['price_invalid'] += 1
                        break
        
        # Add is_matched flag
        result_df['is_matched'] = (result_df['status'] == 'valid')
        result_df['has_data'] = result_df['open'].notna()
        result_df['price_valid'] = (result_df['status'] == 'valid')
        
        # Print statistics
        total_bars = len(result_df)
        valid_bars = (result_df['status'] == 'valid').sum()
        price_invalid_bars = (result_df['status'] == 'price_invalid').sum()
        unmatched_bars = (result_df['status'] == 'unmatched').sum()
        
        print("\n" + "-"*70)
        print("MATCHING RESULTS")
        print("-"*70)
        print(f"\nOverall Statistics:")
        print(f"  Total agent bars: {total_bars}")
        print(f"  Valid matches: {valid_bars} ({valid_bars/total_bars*100:.1f}%)")
        print(f"  Price invalid: {price_invalid_bars} ({price_invalid_bars/total_bars*100:.1f}%)")
        print(f"  Unmatched: {unmatched_bars} ({unmatched_bars/total_bars*100:.1f}%)")
        
        print(f"\nPer-Contract Statistics:")
        for contract_name in sorted(contract_stats.keys()):
            stats = contract_stats[contract_name]
            if stats['matched'] > 0:
                print(f"  {contract_name}:")
                print(f"    Total matched: {stats['matched']}")
                print(f"    Price valid: {stats['price_valid']}")
                print(f"    Price invalid: {stats['price_invalid']}")
        
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
        
        self.matched_df = result_df
        return result_df

    def get_match_report(self):
        """
        Generate a detailed match report.

        Returns:
            String with match statistics
        """
        if self.matched_df is None:
            return "No matched data available. Call match_data() first."

        total_count = len(self.matched_df)
        valid_count = (self.matched_df['status'] == 'valid').sum()
        no_data_count = (self.matched_df['status'] == 'no_data').sum()
        price_invalid_count = (self.matched_df['status'] == 'price_invalid').sum()

        report = f"""
MATCH REPORT
{'='*50}
Total bars: {total_count}
  Valid (timestamp + price): {valid_count} ({valid_count/total_count*100:.1f}%)
  No data at timestamp: {no_data_count} ({no_data_count/total_count*100:.1f}%)
  Price outside OHLC range: {price_invalid_count} ({price_invalid_count/total_count*100:.1f}%)

Date range:
  Start: {self.matched_df.index.min()}
  End: {self.matched_df.index.max()}

Status breakdown:
"""
        for status, count in self.matched_df['status'].value_counts().items():
            report += f"  {status}: {count}\n"
        
        report += "\nFirst 10 status reasons:\n"
        for idx, row in self.matched_df.head(10).iterrows():
            report += f"  {idx} - {row['status']}: {row['status_reason']}\n"

        return report

    def export_validated_data(self, output_dir='execution_pnl_comparison'):
        """
        Export validated timestamps and agent trade data for comparison.

        Returns:
            Dict with paths to exported files
        """
        import os
        from datetime import datetime

        # Filter to only validated rows
        validated_df = self.matched_df[self.matched_df['status'] == 'valid'].copy()

        if len(validated_df) == 0:
            print("Warning: No validated data to export")
            return None

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Create timestamp subfolder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f'validated_data_{timestamp}')
        os.makedirs(output_path, exist_ok=True)

        # Export validated data with agent trades
        validated_file = os.path.join(output_path, 'validated_trades.csv')
        validated_df.to_csv(validated_file, index=True)

        # Export only the columns needed for backtesting
        backtest_columns = ['price', 'vol', 'cum_vol', 'direction', 'open', 'high', 'low', 'close', 'vwap']
        backtest_file = os.path.join(output_path, 'backtest_input.csv')
        validated_df[backtest_columns].to_csv(backtest_file, index=True)

        print(f"\nExported validated data to: {output_path}")
        print(f"  Validated trades: {len(validated_df)}")
        print(f"  File: {validated_file}")
        print(f"  Backtest input: {backtest_file}")

        return {
            'output_path': output_path,
            'validated_file': validated_file,
            'backtest_file': backtest_file,
            'validated_count': len(validated_df)
        }


def identify_contract_for_agent(agent_file, data_dir='data_export'):
    """
    Convenience function to identify contract for an agent file.

    Args:
        agent_file: Path to agent data CSV
        data_dir: Directory containing our futures data

    Returns:
        Dict with contract information
    """
    # Extract future name from agent_file path
    future_name = agent_file.split('/')[-2] if '/' in agent_file else 'Nasdaq'

    matcher = DataMatcher(agent_file, data_dir)
    return matcher.identify_contract(future_name)


if __name__ == '__main__':
    # Test the module
    import sys

    if len(sys.argv) > 1:
        agent_file = sys.argv[1]
    else:
        agent_file = 'data_export/Nasdaq/AIAgent_Nasdaq.csv'

    print("Testing DataMatcher module...")
    print(f"Agent file: {agent_file}")

    matcher = DataMatcher(agent_file)
    result = matcher.identify_contract('Nasdaq')

    if 'error' not in result:
        print(f"\nIdentified contract: {result['best_contract']}")
        matched = matcher.match_data(result['best_contract'])
        print(matcher.get_match_report())
    else:
        print(f"Error: {result['error']}")