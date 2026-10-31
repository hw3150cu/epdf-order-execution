#!/usr/bin/env python3
"""
Compare Execution PnL: Agent Baseline vs Optimized Limit Order Logic

This script:
1. Matches agent trading data with NQH20 contract (best price validation)
2. Trades on 1-minute bars (configurable: 1min, 5min, 15min, 60min)
3. Calculates agent's PnL (baseline - market orders at current price)
4. Applies our optimized limit order logic at same timestamps
5. Generates PnL comparison curves
6. Keeps ALL timestamps with status explanations

Usage:
    python compare_execution_pnl.py --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv --bar_freq 1min --window 60 --min_penalty 5.0 --max_level 10.0
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


def resample_to_frequency(df, freq):
    """
    Resample data to specified frequency using OHLC aggregation.

    Args:
        df: DataFrame with datetime index and OHLCV columns
        freq: Frequency string ('1min', '5min', '15min', '60min')

    Returns:
        Resampled DataFrame
    """
    df_resampled = df.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'vol': 'sum'
    }).dropna()

    return df_resampled


def load_and_match_data(agent_file, contract_name, bar_freq='1min'):
    """
    Load agent data and match with contract data.

    Args:
        agent_file: Path to agent data
        contract_name: Contract to use (e.g., 'NQH20')
        bar_freq: Bar frequency ('1min', '5min', '15min', '60min')

    Returns:
        Matched DataFrame with status columns
    """
    print("="*70)
    print("LOADING AND MATCHING DATA")
    print("="*70)

    # Use DataMatcher
    matcher = DataMatcher(agent_file)
    matched_df = matcher.match_data(contract_name)

    if matched_df is None:
        print("ERROR: Failed to match data")
        return None

    # Filter to only price-validated bars (valid for comparison)
    valid_df = matched_df[matched_df['status'] == 'valid'].copy()

    print(f"\nMatched with price validation:")
    print(f"  Total bars: {len(matched_df)}")
    print(f"  Valid (can compare): {len(valid_df)} ({len(valid_df)/len(matched_df)*100:.1f}%)")
    print(f"  Will be skipped: {len(matched_df) - len(valid_df)}")

    return matched_df


def calculate_baseline_pnl(df, tick_size=0.25, position_size=1):
    """
    Calculate agent's baseline PnL (market order execution).

    Assumption: Agent enters at current price and exits at next bar's close.

    Args:
        df: DataFrame with price and OHLC columns
        tick_size: Tick size for futures
        position_size: Number of contracts

    Returns:
        DataFrame with baseline PnL columns added
    """
    print("\nCalculating baseline PnL (market order execution)...")

    df = df.copy()

    # Calculate price change from current bar to next bar's close
    df['next_close'] = df['close'].shift(-1)

    # Agent enters at current price, exits at next bar's close
    df['baseline_pnl_ticks'] = (df['next_close'] - df['price']) / tick_size * position_size
    df['baseline_pnl_cumulative'] = df['baseline_pnl_ticks'].cumsum()

    # Handle last row (no next close)
    df.loc[df.index[-1], 'baseline_pnl_ticks'] = 0

    print(f"  Total PnL: {df['baseline_pnl_ticks'].sum():.1f} ticks")
    print(f"  Final cumulative: {df['baseline_pnl_cumulative'].iloc[-1]:.1f} ticks")

    return df


def apply_optimized_logic(df, window_size=60, min_penalty=5.0, max_level=10.0,
                         tick_size=0.25, position_size=1, min_vol=100):
    """
    Apply our optimized limit order logic at each timestamp.

    Only processes bars that are price-validated (status == 'valid').

    Args:
        df: Matched DataFrame with OHLCV data
        window_size: Rolling window for ePDF
        min_penalty: Minimum penalty in ticks
        max_level: Maximum level in ticks
        tick_size: Tick size
        position_size: Number of contracts
        min_vol: Minimum volume threshold

    Returns:
        DataFrame with optimized PnL columns added
    """
    print(f"\nApplying optimized logic (window={window_size}, penalty={min_penalty}, max_level={max_level})...")

    # Initialize optimizer
    optimizer = UtilityOptimizer(window_size=window_size,
                               min_penalty=min_penalty,
                               max_level=max_level)

    # Initialize state detector
    detector = StateDetector(thresh=2.5)

    # Prepare data for state detection
    df = df.copy()

    # Add required columns for state detector
    df['range_dn_ticks'] = (df['open'] - df['low']) / tick_size  # For BUY orders
    df['range_up_ticks'] = (df['high'] - df['open']) / tick_size  # For SELL orders
    
    # Add ts column for detector
    df['ts'] = df.index.strftime('%Y.%m.%d.%H:%M:%S')
    df = detector.detect_states(df)

    # Initialize tracking arrays
    optimized_pnl_ticks = np.zeros(len(df))
    buy_savings = np.zeros(len(df))
    sell_savings = np.zeros(len(df))
    trade_status = [''] * len(df)
    trade_reason = [''] * len(df)

    # Process bars (only on price-validated bars)
    valid_indices = df[df['status'] == 'valid'].index

    print(f"  Processing {len(valid_indices)} valid bars...")

    # Use datetime column if available, otherwise use index
    time_col = 'datetime' if 'datetime' in df.columns else df.index.name

    for i in tqdm(range(len(df)), desc="Optimizing"):
        idx = df.index[i]

        # Skip non-validated bars
        if idx not in valid_indices:
            trade_status[i] = 'skipped'
            trade_reason[i] = df.loc[idx, 'status_reason']
            continue

        row = df.iloc[i]
        
        # Check warmup period using time-based window (last 60 minutes)
        if time_col in df.columns:
            current_time = row[time_col]
            time_window_start = current_time - pd.Timedelta(minutes=60)
            
            # Get bars within last 60 minutes (before current bar)
            historical_mask = (df.index < i) & (df.index >= 0)
            historical_bars = df[historical_mask].copy()
            historical_bars = historical_bars[historical_bars[time_col] >= time_window_start]
        else:
            # If no datetime column, use index position as proxy
            historical_bars = df.iloc[max(0, i-window_size):i].copy()
        
        # Count only valid bars within the time window
        valid_in_window = (historical_bars['status'] == 'valid').sum()
        
        if valid_in_window < window_size:
            trade_status[i] = 'skipped'
            trade_reason[i] = f'Warmup period ({valid_in_window}/{window_size} valid bars in last 60 min)'
            continue

        # Check liquidity
        if row['vol'] < min_vol:
            trade_status[i] = 'skipped'
            trade_reason[i] = f'Low liquidity (vol={row["vol"]:.0f} < {min_vol})'
            continue

        # Check state
        state = row.get('prev_state', None)
        if state is None or pd.isna(state):
            trade_status[i] = 'skipped'
            trade_reason[i] = 'No state detected'
            continue

        # Get historical data for optimizer (use time-based window)
        # Take the last 'window_size' valid bars from the historical window
        valid_historical = historical_bars[historical_bars['status'] == 'valid'].tail(window_size)
        window_data = valid_historical.copy()

        # Get optimal levels
        limits = optimizer.get_limits(window_data, len(window_data)-1, tick_size)

        # Calculate savings
        # BUY SIDE: open - low (limit buy below open)
        buy_gap = row['open'] - row['low']
        buy_save = 0.0
        for level, weight in limits:
            if buy_gap >= level:
                buy_save += weight * level

        # SELL SIDE: high - open (limit sell above open)
        sell_gap = row['high'] - row['open']
        sell_save = 0.0
        for level, weight in limits:
            if sell_gap >= level:
                sell_save += weight * level

        # Total savings
        total_save = buy_save + sell_save
        buy_savings[i] = buy_save
        sell_savings[i] = sell_save

        # Calculate penalty based on expected close
        expected_close = optimizer.epdf.get_expected_close(state)
        penalty = max(min_penalty, (expected_close - row['open']) / tick_size)

        # Fill probability
        buy_fill_prob = 0.0
        sell_fill_prob = 0.0
        for level, weight in limits:
            if buy_gap >= level:
                buy_fill_prob += weight
            if sell_gap >= level:
                sell_fill_prob += weight

        total_fill_prob = buy_fill_prob + sell_fill_prob

        # Baseline PnL: enter at current price, exit at next close
        next_close = row.get('next_close', row['close'])
        baseline_pnl = (next_close - row['price']) / tick_size * position_size

        # Optimized PnL: enter at limit price (save ticks), exit at next close
        # Expected PnL = fill_prob * (baseline + savings) - (1 - fill_prob) * penalty
        optimized_pnl = (total_fill_prob * (baseline_pnl + total_save * position_size) -
                        (1 - total_fill_prob) * penalty * position_size)

        optimized_pnl_ticks[i] = optimized_pnl

        if total_save > 0:
            trade_status[i] = 'executed'
            trade_reason[i] = f'Fill prob={total_fill_prob:.2f}, Buy save={buy_save:.1f}, Sell save={sell_save:.1f}'
        else:
            trade_status[i] = 'executed'
            trade_reason[i] = f'No savings achieved'

    # Add columns to DataFrame
    df['optimized_pnl_ticks'] = optimized_pnl_ticks
    df['optimized_pnl_cumulative'] = optimized_pnl_ticks.cumsum()
    df['buy_savings_ticks'] = buy_savings
    df['sell_savings_ticks'] = sell_savings
    df['trade_status'] = trade_status
    df['trade_reason'] = trade_reason

    # Calculate stats
    executed_count = (df['trade_status'] == 'executed').sum()
    total_valid = len(valid_indices)

    print(f"  Executed: {executed_count}/{total_valid} ({executed_count/total_valid*100:.1f}%)")
    print(f"  Total PnL: {df['optimized_pnl_ticks'].sum():.1f} ticks")
    print(f"  Final cumulative: {df['optimized_pnl_cumulative'].iloc[-1]:.1f} ticks")
    print(f"  Total savings: {(df['buy_savings_ticks'] + df['sell_savings_ticks']).sum():.1f} ticks")

    return df


def generate_comparison_report(df, output_dir, agent_file, contract_name, params):
    """
    Generate comprehensive comparison report.

    Args:
        df: DataFrame with all PnL calculations
        output_dir: Output directory
        agent_file: Agent file name
        contract_name: Contract used
        params: Dictionary of parameters
    """
    print("\n" + "="*70)
    print("GENERATING COMPARISON REPORT")
    print("="*70)

    os.makedirs(output_dir, exist_ok=True)

    # Filter to valid bars only for comparison
    valid_df = df[df['status'] == 'valid'].copy()

    if len(valid_df) == 0:
        print("ERROR: No valid bars for comparison!")
        return

    # Calculate statistics
    tick_value = 0.25 * 50  # NQ tick value: $12.5 per tick

    # Baseline stats
    baseline_total_pnl = valid_df['baseline_pnl_ticks'].sum()
    baseline_final_pnl = valid_df['baseline_pnl_cumulative'].iloc[-1]

    # Optimized stats
    optimized_total_pnl = valid_df['optimized_pnl_ticks'].sum()
    optimized_final_pnl = valid_df['optimized_pnl_cumulative'].iloc[-1]

    # Improvement
    improvement = optimized_final_pnl - baseline_final_pnl
    improvement_pct = (improvement / abs(baseline_final_pnl) * 100) if baseline_final_pnl != 0 else 0

    # Savings
    total_savings = (valid_df['buy_savings_ticks'] + valid_df['sell_savings_ticks']).sum()
    buy_savings = valid_df['buy_savings_ticks'].sum()
    sell_savings = valid_df['sell_savings_ticks'].sum()

    # Trade status
    executed_count = (valid_df['trade_status'] == 'executed').sum()
    skipped_count = (valid_df['trade_status'] == 'skipped').sum()

    # Create summary
    summary = f"""
{'='*70}
EXECUTION PNL COMPARISON: BASELINE vs OPTIMIZED
{'='*70}

Agent File: {os.path.basename(agent_file)}
Contract: {contract_name}
Parameters:
  Window: {params['window_size']}
  Penalty: {params['min_penalty']}
  Max Level: {params['max_level']}
  Min Volume: {params['min_vol']}
  Bar Frequency: {params['bar_freq']}

DATA STATISTICS:
  Total bars (all): {len(df)}
  Valid bars (price validated): {len(valid_df)}
  Executed trades: {executed_count}
  Skipped trades: {skipped_count}

BASELINE PERFORMANCE (Market Orders):
  Total PnL: {baseline_total_pnl:.1f} ticks (${baseline_total_pnl * tick_value:,.2f})
  Final Cumulative: {baseline_final_pnl:.1f} ticks (${baseline_final_pnl * tick_value:,.2f})
  Avg PnL/Trade: {baseline_total_pnl/len(valid_df):.2f} ticks (${baseline_total_pnl/len(valid_df) * tick_value:.2f})

OPTIMIZED PERFORMANCE (Limit Orders):
  Total PnL: {optimized_total_pnl:.1f} ticks (${optimized_total_pnl * tick_value:,.2f})
  Final Cumulative: {optimized_final_pnl:.1f} ticks (${optimized_final_pnl * tick_value:,.2f})
  Avg PnL/Trade: {optimized_total_pnl/len(valid_df):.2f} ticks (${optimized_total_pnl/len(valid_df) * tick_value:.2f})

SAVINGS ANALYSIS:
  Total Savings: {total_savings:.1f} ticks (${total_savings * tick_value:,.2f})
    Buy Side: {buy_savings:.1f} ticks (${buy_savings * tick_value:,.2f})
    Sell Side: {sell_savings:.1f} ticks (${sell_savings * tick_value:,.2f})

COMPARISON:
  Improvement: {improvement:+.1f} ticks ({improvement:+,.2f})
  Improvement %: {improvement_pct:+.1f}%
  Better performance: {'OPTIMIZED' if improvement > 0 else 'BASELINE'}

{'='*70}
"""

    print(summary)

    # Save summary
    summary_file = os.path.join(output_dir, 'summary.txt')
    with open(summary_file, 'w') as f:
        f.write(summary)
    print(f"Summary saved to: {summary_file}")

    # Save detailed results
    results_file = os.path.join(output_dir, 'detailed_results.csv')
    columns_to_save = [
        'status', 'status_reason', 'trade_status', 'trade_reason',
        'price', 'open', 'high', 'low', 'close', 'vol',
        'baseline_pnl_ticks', 'baseline_pnl_cumulative',
        'optimized_pnl_ticks', 'optimized_pnl_cumulative',
        'buy_savings_ticks', 'sell_savings_ticks'
    ]
    valid_df[columns_to_save].to_csv(results_file)
    print(f"Detailed results saved to: {results_file}")

    # Create comparison plots
    create_comparison_plots(valid_df, output_dir, tick_value)

    return summary


def create_comparison_plots(df, output_dir, tick_value):
    """Create PnL comparison visualizations"""

    print("\nCreating comparison plots...")

    # Figure 1: Cumulative PnL Comparison
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(df.index, df['baseline_pnl_cumulative'],
            label='Baseline (Market Orders)', color='blue', linewidth=2, alpha=0.7)
    ax.plot(df.index, df['optimized_pnl_cumulative'],
            label='Optimized (Limit Orders)', color='green', linewidth=2, alpha=0.7)

    ax.set_title('Cumulative PnL: Baseline vs Optimized', fontsize=14, fontweight='bold')
    ax.set_ylabel('PnL (ticks)', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    plot_file = os.path.join(output_dir, 'pnl_comparison.png')
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {plot_file}")

    # Figure 2: PnL Difference
    fig, ax = plt.subplots(figsize=(14, 6))

    pnl_diff = df['optimized_pnl_cumulative'] - df['baseline_pnl_cumulative']
    ax.plot(df.index, pnl_diff, color='purple', linewidth=2, alpha=0.7)
    ax.fill_between(df.index, pnl_diff, 0, where=(pnl_diff > 0), color='green', alpha=0.3, label='Improvement')
    ax.fill_between(df.index, pnl_diff, 0, where=(pnl_diff < 0), color='red', alpha=0.3, label='Underperformance')

    ax.set_title('PnL Difference (Optimized - Baseline)', fontsize=14, fontweight='bold')
    ax.set_ylabel('PnL Difference (ticks)', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    plot_file = os.path.join(output_dir, 'pnl_difference.png')
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {plot_file}")

    # Figure 3: Savings Distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Buy savings
    buy_saving_valid = df[df['buy_savings_ticks'] > 0]['buy_savings_ticks']
    if len(buy_saving_valid) > 0:
        axes[0].hist(buy_saving_valid, bins=50, color='green', alpha=0.7, edgecolor='black')
    axes[0].set_title('Buy Side Savings Distribution', fontsize=12, fontweight='bold')
    axes[0].set_xlabel('Savings (ticks)', fontsize=10)
    axes[0].set_ylabel('Frequency', fontsize=10)
    axes[0].grid(True, alpha=0.3)

    # Sell savings
    sell_saving_valid = df[df['sell_savings_ticks'] > 0]['sell_savings_ticks']
    if len(sell_saving_valid) > 0:
        axes[1].hist(sell_saving_valid, bins=50, color='blue', alpha=0.7, edgecolor='black')
    axes[1].set_title('Sell Side Savings Distribution', fontsize=12, fontweight='bold')
    axes[1].set_xlabel('Savings (ticks)', fontsize=10)
    axes[1].set_ylabel('Frequency', fontsize=10)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_file = os.path.join(output_dir, 'savings_distribution.png')
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {plot_file}")

    # Figure 4: Trade Status Pie Chart
    fig, ax = plt.subplots(figsize=(10, 6))

    status_counts = df['trade_status'].value_counts()
    colors = ['green' if status == 'executed' else 'orange' for status in status_counts.index]
    ax.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%',
           colors=colors, startangle=90, textprops={'fontsize': 11})
    ax.set_title('Trade Status Distribution', fontsize=14, fontweight='bold')

    plt.tight_layout()
    plot_file = os.path.join(output_dir, 'trade_status.png')
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {plot_file}")


def main():
    parser = argparse.ArgumentParser(description='Compare Execution PnL: Baseline vs Optimized')
    parser.add_argument('--agent_file', type=str, required=True,
                       help='Path to agent data file')
    parser.add_argument('--contract', type=str, default='NQH20',
                       help='Contract to use (default: NQH20)')
    parser.add_argument('--bar_freq', type=str, default='1min',
                       choices=['1min', '5min', '15min', '60min'],
                       help='Bar frequency (default: 1min)')
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
    parser.add_argument('--output', type=str, default='execution_pnl_comparison',
                       help='Output directory (default: execution_pnl_comparison)')

    args = parser.parse_args()

    print("="*70)
    print("EXECUTION PNL COMPARISON")
    print("="*70)
    print(f"Agent file: {args.agent_file}")
    print(f"Contract: {args.contract}")
    print(f"Bar frequency: {args.bar_freq}")
    print(f"Parameters: window={args.window}, penalty={args.min_penalty}, max_level={args.max_level}")

    params = {
        'window_size': args.window,
        'min_penalty': args.min_penalty,
        'max_level': args.max_level,
        'tick_size': args.tick_size,
        'min_vol': args.min_vol,
        'bar_freq': args.bar_freq
    }

    # Step 1: Load and match data
    matched_df = load_and_match_data(args.agent_file, args.contract, args.bar_freq)
    if matched_df is None:
        print("ERROR: Failed to load and match data")
        return

    # Step 2: Calculate baseline PnL
    matched_df = calculate_baseline_pnl(matched_df, args.tick_size)

    # Step 3: Apply optimized logic
    matched_df = apply_optimized_logic(matched_df,
                                      window_size=args.window,
                                      min_penalty=args.min_penalty,
                                      max_level=args.max_level,
                                      tick_size=args.tick_size,
                                      min_vol=args.min_vol)

    # Step 4: Generate comparison report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(args.output, f'{args.contract}_{args.bar_freq}_{timestamp}')
    generate_comparison_report(matched_df, output_dir, args.agent_file, args.contract, params)

    print("\n" + "="*70)
    print("COMPARISON COMPLETE")
    print(f"Results saved to: {output_dir}")
    print("="*70)


if __name__ == '__main__':
    main()