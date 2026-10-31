#!/usr/bin/env python3
"""
Compare Agent Trading vs Our Logic Trading

This script:
1. Loads agent trading data (date, hour, min, price, cumulative volume)
2. Uses DataMatcher to identify which futures contract is being traded
3. Matches agent timestamps with our 5-minute bar data
4. Applies our trading logic ONLY at matched timestamps (apple-to-apple comparison)
5. Keeps ALL timestamps in trading records with explanations for non-trades
6. Generates PnL comparison curves

Usage:
    python compare_agent_vs_logic.py --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv --window 60 --min_penalty 5.0 --max_level 10.0
"""

import warnings
warnings.filterwarnings('ignore', message='.*delta_grad.*', category=UserWarning)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import argparse
from datetime import datetime, timedelta
from tqdm import tqdm
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer
from data_matcher import DataMatcher


def load_agent_data(agent_file):
    """
    Load agent trading data and convert to proper format.

    Agent data format: date (Excel number), hour, min, price, cumulative_volume

    Returns:
        DataFrame with timestamp, price, volume, agent_pnl
    """
    print(f"Loading agent data from: {agent_file}")

    df = pd.read_csv(agent_file, header=None, names=['date', 'hour', 'min', 'price', 'cum_vol'])

    print(f"  Loaded {len(df)} bars")

    # Convert Excel date numbers to actual timestamps
    start_date = datetime(1900, 1, 1)
    df['timestamp'] = df.apply(
        lambda row: start_date + timedelta(days=int(row['date']) - 2,
                                          hours=int(row['hour']),
                                          minutes=int(row['min'])),
        axis=1
    )

    # Calculate trading volume (difference from next row)
    # agent uses cumulative volume, so vol = next_cum_vol - current_cum_vol
    df['vol'] = df['cum_vol'].diff(-1).abs()
    df.loc[df.index == df.index[-1], 'vol'] = 0  # Last row has no volume

    # Calculate agent's PnL (assuming agent trades at price and holds to next bar)
    df['price_next'] = df['price'].shift(-1)
    df['agent_pnl'] = df['price_next'] - df['price']

    # Filter out bars with zero volume
    df = df[df['vol'] > 0].copy()

    print(f"  After filtering (vol > 0): {len(df)} bars")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Price range: {df['price'].min():.2f} to {df['price'].max():.2f}")

    return df


def find_matching_contract(agent_df, future_name):
    """
    Identify which futures contract matches agent's date range.

    For Nasdaq: NQH20 (March), NQM20 (June), NQU20 (September)
    For other futures: similar pattern

    Returns:
        str: Contract file path
    """
    print(f"\nIdentifying matching contract for {future_name}...")

    # Get agent date range
    agent_start = agent_df['timestamp'].min()
    agent_end = agent_df['timestamp'].max()

    print(f"  Agent trading period: {agent_start} to {agent_end}")

    # Map futures to their contracts
    contract_map = {
        'Nasdaq': [
            'data_export/Nasdaq/NQH20.csv',
            'data_export/Nasdaq/NQM20.csv',
            'data_export/Nasdaq/NQU20.csv',
        ],
        'GBP': [
            'data_export/GBP - British Pound/BPM20.csv',
            'data_export/GBP - British Pound/BPU20.csv',
        ],
        'Gold': [
            'data_export/Gold/GCG24.csv',
            'data_export/Gold/GCJ24.csv',
            'data_export/Gold/GCM24.csv',
            'data_export/Gold/GCQ24.csv',
        ],
        'JPY': [
            'data_export/JPY - Japanese Yen/JYU24.csv',
            'data_export/JPY - Japanese Yen/JYZ24.csv',
        ],
        'German Bunds': [
            'data_export/German Bunds - German Government Bonds/RXM25.csv',
            'data_export/German Bunds - German Government Bonds/RXU25.csv',
            'data_export/German Bunds - German Government Bonds/RXZ25.csv',
        ],
        'HeatingOil': [
            'data_export/HeatingOil/HOF22.csv',
            'data_export/HeatingOil/HOG22.csv',
            'data_export/HeatingOil/HOH22.csv',
        ],
    }

    contracts = contract_map.get(future_name, [])
    if not contracts:
        print(f"  ERROR: Unknown future '{future_name}'")
        return None

    # Find which contract overlaps with agent's period
    for contract_file in contracts:
        if not os.path.exists(contract_file):
            print(f"  Skipping {contract_file} (not found)")
            continue

        try:
            df = pd.read_csv(contract_file, header=None,
                            names=['ts', 'open', 'high', 'low', 'close', 'vol'])
            df['timestamp'] = pd.to_datetime(df['ts'], format='%Y.%m.%d.%H:%M:%S')

            contract_start = df['timestamp'].min()
            contract_end = df['timestamp'].max()

            # Check overlap
            overlap_start = max(agent_start, contract_start)
            overlap_end = min(agent_end, contract_end)

            if overlap_start < overlap_end:
                print(f"  ✓ Found matching contract: {contract_file}")
                print(f"    Contract period: {contract_start} to {contract_end}")
                print(f"    Overlap: {overlap_start} to {overlap_end}")
                return contract_file

        except Exception as e:
            print(f"  ERROR reading {contract_file}: {e}")

    print(f"  WARNING: No matching contract found")
    return None


def match_agent_to_our_data(agent_df, our_df, tick_size=0.25):
    """
    Match agent timestamps to our bar data.

    Args:
        agent_df: Agent trading data with timestamps
        our_df: Our OHLCV data with timestamps

    Returns:
        DataFrame with matched data: agent_timestamp, agent_price, our_bar, qualified
    """
    print("\nMatching agent timestamps to our data...")

    # Create timestamp index for both dataframes
    our_df['timestamp'] = pd.to_datetime(our_df['ts'], format='%Y.%m.%d.%H:%M:%S')
    our_df = our_df.set_index('timestamp')

    matched = []

    for idx, agent_row in agent_df.iterrows():
        agent_ts = agent_row['timestamp']

        # Find the closest bar in our data (within 1 minute tolerance)
        tolerance = pd.Timedelta(minutes=1)

        # Find bars within tolerance
        nearby_bars = our_df.loc[
            (our_df.index >= agent_ts - tolerance) &
            (our_df.index <= agent_ts + tolerance)
        ]

        if len(nearby_bars) == 0:
            matched.append({
                'agent_timestamp': agent_ts,
                'agent_price': agent_row['price'],
                'agent_vol': agent_row['vol'],
                'agent_pnl': agent_row['agent_pnl'],
                'our_bar_idx': None,
                'qualified': False,
                'skip_reason': 'No matching bar in our data'
            })
        else:
            # Use the closest bar
            closest_idx = (nearby_bars.index - agent_ts).abs().idxmin()
            closest_bar = our_df.loc[closest_idx]

            matched.append({
                'agent_timestamp': agent_ts,
                'agent_price': agent_row['price'],
                'agent_vol': agent_row['vol'],
                'agent_pnl': agent_row['agent_pnl'],
                'our_bar_idx': our_df.index.get_loc(closest_idx),
                'qualified': True,
                'skip_reason': None,
                'our_timestamp': closest_idx,
                'our_open': closest_bar['open'],
                'our_high': closest_bar['high'],
                'our_low': closest_bar['low'],
                'our_close': closest_bar['close'],
                'our_vol': closest_bar['vol'],
            })

    result_df = pd.DataFrame(matched)

    print(f"  Matched {len(result_df)} agent timestamps")
    print(f"  Qualified (have matching bar): {(result_df['qualified']).sum()}")
    print(f"  Skipped (no match): {(~result_df['qualified']).sum()}")

    return result_df


def apply_our_logic(matched_df, our_df, window_size=60, min_penalty=5.0,
                   max_level=10.0, tick_size=0.25, min_vol=100):
    """
    Apply our trading logic to matched agent timestamps.

    Args:
        matched_df: Matched data from match_agent_to_our_data()
        our_df: Our OHLCV data with full history
        window_size: Rolling window for ePDF
        min_penalty: Minimum penalty in ticks
        max_level: Maximum level in ticks
        tick_size: Price tick size
        min_vol: Minimum volume threshold

    Returns:
        DataFrame with our trading results for each agent timestamp
    """
    print(f"\nApplying our trading logic...")
    print(f"  Parameters: window={window_size}, penalty={min_penalty}, max_level={max_level}")
    print(f"  Volume filter: vol > {min_vol}")

    # Reset index for our_df
    our_df = our_df.reset_index(drop=True)

    # Initialize optimizer
    optimizer = UtilityOptimizer(window_size=window_size, min_penalty=min_penalty,
                                 max_level=max_level)

    # Add state detection
    detector = StateDetector(thresh=2.5)
    our_df = detector.detect_states(our_df)

    # Convert to numpy arrays for speed
    open_arr = our_df['open'].values
    high_arr = our_df['high'].values
    low_arr = our_df['low'].values
    close_arr = our_df['close'].values
    vol_arr = our_df['vol'].values
    state_arr = our_df['prev_state'].values

    # Track results
    results = []

    for idx, row in matched_df.iterrows():
        bar_idx = row['our_bar_idx']

        if bar_idx is None:
            # Already skipped - no matching bar
            results.append({
                **row,
                'our_buy_savings': np.nan,
                'our_sell_savings': np.nan,
                'our_total_savings': np.nan,
                'our_pnl': np.nan,
                'our_skip_reason': row['skip_reason']
            })
            continue

        # Check volume filter
        if vol_arr[bar_idx] < min_vol:
            results.append({
                **row,
                'our_buy_savings': np.nan,
                'our_sell_savings': np.nan,
                'our_total_savings': np.nan,
                'our_pnl': np.nan,
                'our_skip_reason': f'Low volume: {vol_arr[bar_idx]} < {min_vol}'
            })
            continue

        # Check if we have enough history for ePDF
        if bar_idx < window_size:
            results.append({
                **row,
                'our_buy_savings': np.nan,
                'our_sell_savings': np.nan,
                'our_total_savings': np.nan,
                'our_pnl': np.nan,
                'our_skip_reason': f'Not enough history: {bar_idx} < {window_size}'
            })
            continue

        # Update ePDF with history up to bar_idx-1
        for j in range(max(0, bar_idx - window_size), bar_idx):
            state = state_arr[j]
            if pd.notna(state):
                prev_j = max(0, j - 1)
                prev_range_dn = open_arr[prev_j] - low_arr[prev_j]
                prev_close = close_arr[prev_j]
                optimizer.epdf.update(state, prev_range_dn, prev_close)

        # Get optimized limits
        limits = optimizer.get_limits(our_df, bar_idx, tick_size)

        # Calculate savings for this bar
        buy_gap = open_arr[bar_idx] - low_arr[bar_idx]
        sell_gap = high_arr[bar_idx] - open_arr[bar_idx]

        buy_savings = 0.0
        sell_savings = 0.0

        for level, weight in limits:
            if buy_gap >= level:
                buy_savings += weight * level
            if sell_gap >= level:
                sell_savings += weight * level

        total_savings = buy_savings + sell_savings

        # Calculate our PnL (baseline + savings - missed penalty)
        baseline_pnl = close_arr[bar_idx] - open_arr[bar_idx]

        # Fill probability
        state = state_arr[bar_idx]
        if pd.isna(state):
            fill_prob = 0.0
        else:
            expected_close = optimizer.epdf.get_expected_close(state)
            penalty = max(min_penalty, (expected_close - open_arr[bar_idx]) / tick_size)

            buy_fill_prob = sum(w for l, w in limits if buy_gap >= l)
            sell_fill_prob = sum(w for l, w in limits if sell_gap >= l)
            fill_prob = buy_fill_prob + sell_fill_prob

        our_pnl = fill_prob * (baseline_pnl + total_savings * tick_size) - (1 - fill_prob) * penalty * tick_size

        results.append({
            **row,
            'our_buy_savings': buy_savings,
            'our_sell_savings': sell_savings,
            'our_total_savings': total_savings,
            'our_pnl': our_pnl,
            'our_skip_reason': None if total_savings > 0 else 'No savings achieved'
        })

    result_df = pd.DataFrame(results)

    # Print summary
    print(f"\n  Total agent timestamps: {len(result_df)}")
    print(f"  Our logic qualified: {(result_df['our_skip_reason'].isna()).sum()}")
    print(f"  Skipped by our logic: {(result_df['our_skip_reason'].notna()).sum()}")

    if (result_df['our_skip_reason'].notna()).sum() > 0:
        print("\n  Skip reasons:")
        print(result_df['our_skip_reason'].value_counts())

    return result_df


def generate_comparison_report(results_df, output_dir, future_name):
    """
    Generate comparison report with PnL curves and statistics.

    Args:
        results_df: Results from apply_our_logic()
        output_dir: Directory to save outputs
        future_name: Name of the future (e.g., 'Nasdaq')
    """
    print(f"\nGenerating comparison report...")

    os.makedirs(output_dir, exist_ok=True)

    # Filter to only qualified trades (our logic executed)
    qualified_df = results_df[results_df['our_skip_reason'].isna()].copy()

    # Calculate cumulative PnL
    qualified_df['agent_cumulative_pnl'] = qualified_df['agent_pnl'].cumsum()
    qualified_df['our_cumulative_pnl'] = qualified_df['our_pnl'].cumsum()

    # Statistics
    print("\n" + "="*70)
    print("COMPARISON STATISTICS")
    print("="*70)

    print(f"\nTotal agent timestamps: {len(results_df)}")
    print(f"Qualified (our logic executed): {len(qualified_df)}")
    print(f"Skipped (our logic didn't qualify): {len(results_df) - len(qualified_df)}")

    if len(qualified_df) > 0:
        print(f"\n--- Agent Trading ---")
        print(f"Total PnL: {qualified_df['agent_pnl'].sum():.2f} points")
        print(f"Mean PnL per trade: {qualified_df['agent_pnl'].mean():.4f} points")
        print(f"Std PnL: {qualified_df['agent_pnl'].std():.4f} points")
        print(f"Win rate: {(qualified_df['agent_pnl'] > 0).sum() / len(qualified_df) * 100:.1f}%")

        print(f"\n--- Our Logic Trading ---")
        print(f"Total PnL: {qualified_df['our_pnl'].sum():.2f} points")
        print(f"Mean PnL per trade: {qualified_df['our_pnl'].mean():.4f} points")
        print(f"Std PnL: {qualified_df['our_pnl'].std():.4f} points")
        print(f"Win rate: {(qualified_df['our_pnl'] > 0).sum() / len(qualified_df) * 100:.1f}%")

        print(f"\n--- Savings ---")
        print(f"Total buy savings: {qualified_df['our_buy_savings'].sum():.2f} ticks")
        print(f"Total sell savings: {qualified_df['our_sell_savings'].sum():.2f} ticks")
        print(f"Total savings: {qualified_df['our_total_savings'].sum():.2f} ticks")
        print(f"Average savings per trade: {qualified_df['our_total_savings'].mean():.2f} ticks")

        print(f"\n--- Comparison ---")
        improvement = qualified_df['our_cumulative_pnl'].iloc[-1] - qualified_df['agent_cumulative_pnl'].iloc[-1]
        print(f"Our logic improvement: {improvement:.2f} points ({improvement/abs(qualified_df['agent_cumulative_pnl'].iloc[-1])*100:.1f}%)")

        # Save detailed results
        output_file = os.path.join(output_dir, f'{future_name}_comparison_details.csv')
        qualified_df.to_csv(output_file, index=False)
        print(f"\n✓ Detailed results saved to: {output_file}")

        # Save skipped trades
        skipped_df = results_df[results_df['our_skip_reason'].notna()]
        if len(skipped_df) > 0:
            skipped_file = os.path.join(output_dir, f'{future_name}_skipped_trades.csv')
            skipped_df.to_csv(skipped_file, index=False)
            print(f"✓ Skipped trades saved to: {skipped_file}")

        # Generate PnL curves
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))

        # Cumulative PnL comparison
        ax1 = axes[0]
        ax1.plot(qualified_df['agent_timestamp'], qualified_df['agent_cumulative_pnl'],
                label='Agent', linewidth=2, color='blue', alpha=0.7)
        ax1.plot(qualified_df['agent_timestamp'], qualified_df['our_cumulative_pnl'],
                label='Our Logic', linewidth=2, color='red', alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
        ax1.set_xlabel('Time', fontsize=12)
        ax1.set_ylabel('Cumulative PnL (points)', fontsize=12)
        ax1.set_title(f'{future_name} - Cumulative PnL: Agent vs Our Logic', fontsize=14, fontweight='bold')
        ax1.legend(loc='best', fontsize=11)
        ax1.grid(True, alpha=0.3)

        # Savings over time
        ax2 = axes[1]
        ax2.plot(qualified_df['agent_timestamp'], qualified_df['our_total_savings'].cumsum(),
                label='Cumulative Savings', linewidth=2, color='green', alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
        ax2.set_xlabel('Time', fontsize=12)
        ax2.set_ylabel('Cumulative Savings (ticks)', fontsize=12)
        ax2.set_title(f'{future_name} - Cumulative Savings Over Time', fontsize=14, fontweight='bold')
        ax2.legend(loc='best', fontsize=11)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        chart_file = os.path.join(output_dir, f'{future_name}_pnl_comparison.png')
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        print(f"✓ PnL comparison chart saved to: {chart_file}")
        plt.close()

        # Generate summary text file
        summary_file = os.path.join(output_dir, f'{future_name}_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write(f"{future_name} - Agent vs Our Logic Comparison\n")
            f.write("="*70 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("PARAMETERS\n")
            f.write("-"*70 + "\n")
            f.write(f"Window size: 60\n")
            f.write(f"Min penalty: 5.0\n")
            f.write(f"Max level: 10.0\n")
            f.write(f"Tick size: 0.25\n")
            f.write(f"Min volume: 100\n\n")

            f.write("STATISTICS\n")
            f.write("-"*70 + "\n")
            f.write(f"Total agent timestamps: {len(results_df)}\n")
            f.write(f"Qualified (our logic executed): {len(qualified_df)}\n")
            f.write(f"Skipped (our logic didn't qualify): {len(results_df) - len(qualified_df)}\n\n")

            f.write("AGENT TRADING\n")
            f.write("-"*70 + "\n")
            f.write(f"Total PnL: {qualified_df['agent_pnl'].sum():.4f} points\n")
            f.write(f"Mean PnL per trade: {qualified_df['agent_pnl'].mean():.6f} points\n")
            f.write(f"Std PnL: {qualified_df['agent_pnl'].std():.6f} points\n")
            f.write(f"Win rate: {(qualified_df['agent_pnl'] > 0).sum() / len(qualified_df) * 100:.2f}%\n\n")

            f.write("OUR LOGIC TRADING\n")
            f.write("-"*70 + "\n")
            f.write(f"Total PnL: {qualified_df['our_pnl'].sum():.4f} points\n")
            f.write(f"Mean PnL per trade: {qualified_df['our_pnl'].mean():.6f} points\n")
            f.write(f"Std PnL: {qualified_df['our_pnl'].std():.6f} points\n")
            f.write(f"Win rate: {(qualified_df['our_pnl'] > 0).sum() / len(qualified_df) * 100:.2f}%\n\n")

            f.write("SAVINGS\n")
            f.write("-"*70 + "\n")
            f.write(f"Total buy savings: {qualified_df['our_buy_savings'].sum():.2f} ticks\n")
            f.write(f"Total sell savings: {qualified_df['our_sell_savings'].sum():.2f} ticks\n")
            f.write(f"Total savings: {qualified_df['our_total_savings'].sum():.2f} ticks\n")
            f.write(f"Average savings per trade: {qualified_df['our_total_savings'].mean():.4f} ticks\n\n")

            f.write("COMPARISON\n")
            f.write("-"*70 + "\n")
            f.write(f"Our logic improvement: {improvement:.4f} points\n")
            f.write(f"Improvement percentage: {improvement/abs(qualified_df['agent_cumulative_pnl'].iloc[-1])*100:.2f}%\n\n")

            if len(skipped_df) > 0:
                f.write("SKIP REASONS\n")
                f.write("-"*70 + "\n")
                for reason, count in skipped_df['our_skip_reason'].value_counts().items():
                    f.write(f"  {reason}: {count}\n")

        print(f"✓ Summary report saved to: {summary_file}")

    print("\n" + "="*70)
    print("COMPARISON COMPLETE")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(description='Compare Agent vs Our Logic Trading')
    parser.add_argument('--future', type=str, required=True,
                       choices=['Nasdaq', 'GBP', 'Gold', 'JPY', 'German Bunds', 'HeatingOil'],
                       help='Future name')
    parser.add_argument('--agent_file', type=str, required=True,
                       help='Path to agent data file')
    parser.add_argument('--window', type=int, default=60,
                       help='Rolling window size (default: 60)')
    parser.add_argument('--min_penalty', type=float, default=5.0,
                       help='Minimum penalty (default: 5.0)')
    parser.add_argument('--max_level', type=float, default=10.0,
                       help='Maximum level (default: 10.0)')
    parser.add_argument('--tick_size', type=float, default=0.25,
                       help='Tick size (default: 0.25)')
    parser.add_argument('--min_vol', type=int, default=100,
                       help='Minimum volume threshold (default: 100)')
    parser.add_argument('--output', type=str, default='agent_comparison_results',
                       help='Output directory (default: agent_comparison_results)')

    args = parser.parse_args()

    print("="*70)
    print(f"AGENT VS LOGIC COMPARISON - {args.future}")
    print("="*70)

    # Step 1: Load agent data
    agent_df = load_agent_data(args.agent_file)

    # Step 2: Find matching contract
    contract_file = find_matching_contract(agent_df, args.future)

    if contract_file is None:
        print("\nERROR: Could not find matching contract")
        return

    # Step 3: Load our data
    print(f"\nLoading our data from: {contract_file}")
    loader = DataLoader(tick_size=args.tick_size)
    our_df = loader.load_csv(contract_file)
    our_df = our_df[our_df['vol'] > args.min_vol].copy()
    print(f"  Loaded {len(our_df)} bars (vol > {args.min_vol})")

    # Step 4: Match agent timestamps to our data
    matched_df = match_agent_to_our_data(agent_df, our_df, args.tick_size)

    # Step 5: Apply our logic
    results_df = apply_our_logic(
        matched_df, our_df,
        window_size=args.window,
        min_penalty=args.min_penalty,
        max_level=args.max_level,
        tick_size=args.tick_size,
        min_vol=args.min_vol
    )

    # Step 6: Generate comparison report
    output_dir = os.path.join(args.output, args.future)
    generate_comparison_report(results_df, output_dir, args.future)


if __name__ == '__main__':
    main()