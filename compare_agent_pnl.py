"""
Compare execution PnL between agent baseline and optimized limit orders.

This script:
1. Identifies validated timestamps where agent traded (price within OHLC range)
2. Calculates baseline: Agent's execution price vs market open
3. Applies optimized limit order strategy on same validated timestamps
4. Scales order volume conservatively (round down to full bars)
5. Generates comparison report and plots
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import matplotlib.pyplot as plt
from tqdm import tqdm
import argparse

from data_matcher import DataMatcher
from strategies_optimized_final import UtilityOptimizer
from state_detection import StateDetector


def load_matched_data(agent_file, contract_name):
    """
    Load agent data and match with contract data using DataMatcher.

    Args:
        agent_file: Path to agent data CSV
        contract_name: Contract name (e.g., 'NQH20')

    Returns:
        DataFrame with matched columns including OHLC and agent price/volume
    """
    print("Loading and matching data...")
    print(f"  Agent file: {agent_file}")
    print(f"  Contract: {contract_name}")

    # Initialize matcher with data_export directory
    matcher = DataMatcher(agent_file, 'data_export')

    # Load and match data (DataMatcher resamples to 5min and validates price)
    matched_df = matcher.match_data(contract_name)

    if matched_df is None:
        raise ValueError(f"Failed to match data for contract {contract_name}")

    # Filter to validated trades (price within OHLC range)
    validated_df = matched_df[matched_df['status'] == 'valid'].copy()
    validated_count = len(validated_df)

    print(f"\nMatched data:")
    print(f"  Total bars: {len(matched_df)}")
    print(f"  Validated (price within OHLC): {validated_count} ({validated_count/len(matched_df)*100:.1f}%)")
    print(f"  First: {validated_df.index[0]}")
    print(f"  Last: {validated_df.index[-1]}")
    print(f"  Price range: ${validated_df['price'].min():.2f} - ${validated_df['price'].max():.2f}")
    print(f"  Volume range: {validated_df['vol'].min():.0f} - {validated_df['vol'].max():.0f}")

    return validated_df


def calculate_baseline_pnl(matched_df, tick_size=0.25, position_size=1):
    """
    Calculate baseline PnL using agent's execution price.

    For buy orders: agent buys at agent price, market would execute at open
    For sell orders: agent sells at agent price, market would execute at open

    Args:
        matched_df: Matched dataframe with agent trades
        tick_size: Tick size in price units
        position_size: Position size in contracts

    Returns:
        Dict with baseline PnL metrics
    """
    print("\nCalculating baseline PnL (agent execution)...")

    # Filter to validated trades
    validated = matched_df[matched_df['status'] == 'valid'].copy()

    if len(validated) == 0:
        return {'total_pnl': 0.0, 'num_trades': 0, 'price_series': []}

    # Calculate baseline: agent executes at agent price vs market order at open
    # Savings = (market_open - agent_price)
    # Positive means agent saved vs market (good execution)
    # Negative means agent paid more than market (bad execution)

    validated['agent_savings'] = validated['open'] - validated['price']

    # Convert to ticks
    validated['savings_ticks'] = validated['agent_savings'] / tick_size

    # Total savings in ticks and dollars
    total_savings_ticks = validated['savings_ticks'].sum()
    total_savings_dollars = total_savings_ticks * tick_size * position_size * 20  # $20 per tick for NQ

    num_trades = len(validated)
    avg_savings_ticks = validated['savings_ticks'].mean()

    print(f"  Number of trades: {num_trades}")
    print(f"  Agent's savings vs market: {total_savings_ticks:.1f} ticks (${total_savings_dollars:,.2f})")
    print(f"  Avg savings per trade: {avg_savings_ticks:.2f} ticks")

    return {
        'total_savings_ticks': total_savings_ticks,
        'total_savings_dollars': total_savings_dollars,
        'num_trades': num_trades,
        'avg_savings_ticks': avg_savings_ticks,
        'savings_series': validated['savings_ticks'].cumsum().tolist(),
        'price_series': validated['price'].tolist()
    }


def run_optimized_on_validated(matched_df, contract_file,
                                window_size=60, min_penalty=5.0, max_level=10.0,
                                tick_size=0.25):
    """
    Run optimized limit order strategy on validated timestamps.

    Uses already-matched data from DataMatcher with agent timestamps
    and corresponding OHLCV from resampled contract data.

    Args:
        matched_df: Matched dataframe from DataMatcher (with agent trades + OHLCV)
        contract_file: Path to contract data CSV (for historical data)
        window_size: Lookback window size
        min_penalty: Minimum penalty for optimizer
        max_level: Maximum level for optimizer
        tick_size: Tick size

    Returns:
        Dict with optimized PnL metrics
    """
    print(f"\nRunning optimized strategy on validated timestamps...")

    # Load full 1-minute contract data for historical context
    df_1min = pd.read_csv(contract_file, header=None,
                          names=['ts', 'open', 'high', 'low', 'close', 'vol'])
    df_1min['datetime'] = pd.to_datetime(df_1min['ts'], format='%Y.%m.%d.%H:%M:%S')
    df_1min = df_1min.set_index('datetime').sort_index()

    print(f"  Loaded 1-minute contract data: {len(df_1min)} bars")

    # Initialize optimizer
    optimizer = strategies.UtilityOptimizer(
        window_size=window_size,
        min_penalty=min_penalty,
        max_level=max_level
    )

    # Initialize state detector
    detector = StateDetector(m=20, thresh=2.5)

    # Add state detection columns to 1-minute data
    df_1min['range_dn_ticks'] = (df_1min['open'] - df_1min['low']) / tick_size
    df_1min['range_up_ticks'] = (df_1min['high'] - df_1min['open']) / tick_size
    df_1min = detector.detect_states(df_1min)

    # Get validated bars from matched_df (already has OHLCV from 5-min resampling)
    validated_df = matched_df[matched_df['status'] == 'valid'].copy()

    print(f"  Validated bars: {len(validated_df)}")

    # Arrays to store results
    buy_savings = np.zeros(len(validated_df))
    sell_savings = np.zeros(len(validated_df))
    total_savings = np.zeros(len(validated_df))
    trade_status = ['unknown'] * len(validated_df)
    trade_reason = [''] * len(validated_df)

    # Process each validated bar
    for i in tqdm(range(len(validated_df)), desc="Optimizing"):
        current_time = validated_df.index[i]

        # Get historical 1-minute data (last 60 minutes before current time)
        start_time = current_time - timedelta(minutes=window_size)

        # Get historical 1-minute data in that time window
        historical_mask = (df_1min.index >= start_time) & (df_1min.index < current_time)
        historical_data = df_1min[historical_mask]

        if len(historical_data) < 12:  # Need at least 12 5-min bars (60 min)
            trade_status[i] = 'skipped'
            trade_reason[i] = f'Insufficient history ({len(historical_data)}/{12} 5-min bars in last {window_size} minutes)'
            continue

        # Get current row from validated_df (5-minute OHLCV)
        row = validated_df.iloc[i]

        # Calculate buy/sell gaps using 5-minute OHLCV
        # BUY SIDE: open - low (potential savings for buy orders)
        buy_gap = row['open'] - row['low']
        # SELL SIDE: high - open (potential savings for sell orders)
        sell_gap = row['high'] - row['open']

        # Get state from historical data (last 5-min bar's state)
        if len(historical_data) > 0:
            last_historical = historical_data.iloc[-1]
            state = last_historical.get('prev_state', None)
        else:
            state = None

        if state is None or pd.isna(state):
            trade_status[i] = 'skipped'
            trade_reason[i] = 'No state detected'
            continue

        # Resample historical data to 5-minute for optimizer
        historical_5min = historical_data.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum',
            'range_dn_ticks': 'first',
            'range_up_ticks': 'first',
            'prev_state': 'first'
        }).dropna()

        if len(historical_5min) < window_size:
            trade_status[i] = 'skipped'
            trade_reason[i] = f'Insufficient 5-min history ({len(historical_5min)}/{window_size})'
            continue

        # Get optimal levels using historical 5-minute data
        window_data = historical_5min.tail(window_size)
        limits = optimizer.get_limits(window_data, window_size-1, tick_size)

        # Calculate savings
        buy_save = 0.0
        for level, weight in limits:
            if buy_gap >= level:
                buy_save += weight * level

        sell_save = 0.0
        for level, weight in limits:
            if sell_gap >= level:
                sell_save += weight * level

        # Convert to ticks
        buy_save_ticks = buy_save / tick_size
        sell_save_ticks = sell_save / tick_size
        total_save_ticks = buy_save_ticks + sell_save_ticks

        buy_savings[i] = buy_save_ticks
        sell_savings[i] = sell_save_ticks
        total_savings[i] = total_save_ticks
        trade_status[i] = 'executed'
        trade_reason[i] = 'Successfully optimized'

    # Calculate results
    executed_mask = np.array([s == 'executed' for s in trade_status])
    executed_count = executed_mask.sum()

    total_optimized_savings = total_savings.sum()
    total_buy_savings = buy_savings.sum()
    total_sell_savings = sell_savings.sum()

    total_savings_dollars = total_optimized_savings * tick_size * 20  # $20 per tick

    print(f"  Processed: {len(validated_df)} validated bars")
    print(f"  Executed: {executed_count} ({executed_count/len(validated_df)*100:.1f}%)")
    print(f"  Total savings: {total_optimized_savings:.1f} ticks (${total_savings_dollars:,.2f})")
    print(f"    Buy savings: {total_buy_savings:.1f} ticks")
    print(f"    Sell savings: {total_sell_savings:.1f} ticks")

    # Save detailed results
    results_df = validated_df.copy()
    results_df['buy_savings_ticks'] = buy_savings
    results_df['sell_savings_ticks'] = sell_savings
    results_df['total_savings_ticks'] = total_savings
    results_df['trade_status'] = trade_status
    results_df['trade_reason'] = trade_reason

    return {
        'total_savings_ticks': total_optimized_savings,
        'total_savings_dollars': total_savings_dollars,
        'buy_savings_ticks': total_buy_savings,
        'sell_savings_ticks': total_sell_savings,
        'executed_count': executed_count,
        'total_count': len(validated_df),
        'results_df': results_df,
        'savings_series': pd.Series(total_savings).cumsum()
    }


def generate_comparison_report(matched_df, baseline_metrics, optimized_metrics,
                               output_dir, agent_file, contract_name, params):
    """
    Generate comparison report and plots.

    Args:
        matched_df: Matched dataframe
        baseline_metrics: Baseline PnL metrics
        optimized_metrics: Optimized PnL metrics
        output_dir: Output directory
        agent_file: Agent file path
        contract_name: Contract name
        params: Dictionary of parameters used
    """
    print(f"\nGenerating comparison report...")

    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f'{contract_name}_1min_{timestamp}')
    os.makedirs(output_path, exist_ok=True)

    # Generate summary text
    summary = f"""
EXECUTION PnL COMPARISON REPORT
{'='*60}

Data Source:
  Agent file: {agent_file}
  Contract: {contract_name}
  Validated timestamps: {len(matched_df[matched_df['status'] == 'valid'])}

Parameters:
  Bar frequency: 1min
  Window size: {params['window_size']}
  Min penalty: {params['min_penalty']}
  Max level: {params['max_level']}
  Tick size: 0.25

{'='*60}
BASELINE PERFORMANCE (Agent Execution)
{'='*60}
Agent's savings vs market: {baseline_metrics['total_savings_ticks']:.1f} ticks (${baseline_metrics['total_savings_dollars']:,.2f})
Number of trades: {baseline_metrics['num_trades']}
Avg savings per trade: {baseline_metrics['avg_savings_ticks']:.2f} ticks

{'='*60}
OPTIMIZED PERFORMANCE (Limit Orders)
{'='*60}
Total savings: {optimized_metrics['total_savings_ticks']:.1f} ticks (${optimized_metrics['total_savings_dollars']:,.2f})
Executed trades: {optimized_metrics['executed_count']}/{optimized_metrics['total_count']} ({optimized_metrics['executed_count']/optimized_metrics['total_count']*100:.1f}%)
  Buy savings: {optimized_metrics['buy_savings_ticks']:.1f} ticks
  Sell savings: {optimized_metrics['sell_savings_ticks']:.1f} ticks

{'='*60}
IMPROVEMENT
{'='*60}
Total improvement: {optimized_metrics['total_savings_ticks'] - baseline_metrics['total_savings_ticks']:+.1f} ticks
Percentage: {(optimized_metrics['total_savings_ticks'] / baseline_metrics['total_savings_ticks'] * 100 - 100):+.1f}% if baseline > 0

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    # Write summary
    summary_file = os.path.join(output_path, 'summary.txt')
    with open(summary_file, 'w') as f:
        f.write(summary)

    print(f"\n{summary}")

    # Save detailed results
    results_file = os.path.join(output_path, 'detailed_results.csv')
    optimized_metrics['results_df'].to_csv(results_file, index=True)
    print(f"\nDetailed results saved to: {results_file}")

    # Generate plots
    create_comparison_plots(matched_df, baseline_metrics, optimized_metrics, output_path)

    print(f"\nComparison report generated: {output_path}")
    return output_path


def create_comparison_plots(matched_df, baseline_metrics, optimized_metrics, output_path):
    """
    Create comparison plots.

    Args:
        matched_df: Matched dataframe
        baseline_metrics: Baseline PnL metrics
        optimized_metrics: Optimized PnL metrics
        output_path: Output directory for plots
    """
    print("Creating comparison plots...")

    validated_df = matched_df[matched_df['status'] == 'valid']

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Execution PnL Comparison: Baseline vs Optimized', fontsize=16, fontweight='bold')

    # Plot 1: PnL curves
    ax1 = axes[0, 0]
    if 'savings_series' in baseline_metrics:
        baseline_cumsum = baseline_metrics['savings_series']
        ax1.plot(baseline_cumsum, label='Baseline (Agent)', linewidth=2, color='blue')

    if 'savings_series' in optimized_metrics:
        optimized_cumsum = optimized_metrics['savings_series']
        ax1.plot(optimized_cumsum, label='Optimized (Limit Orders)', linewidth=2, color='red')

    ax1.set_xlabel('Trade Number')
    ax1.set_ylabel('Cumulative Savings (ticks)')
    ax1.set_title('Cumulative Savings Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: PnL difference
    ax2 = axes[0, 1]
    if 'savings_series' in baseline_metrics and 'savings_series' in optimized_metrics:
        baseline_cumsum = baseline_metrics['savings_series']
        optimized_cumsum = optimized_metrics['savings_series']

        # Align lengths
        min_len = min(len(baseline_cumsum), len(optimized_cumsum))
        difference = np.array(optimized_cumsum[:min_len]) - np.array(baseline_cumsum[:min_len])

        ax2.plot(difference, linewidth=2, color='green')
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax2.fill_between(range(len(difference)), difference, 0, where=difference >= 0,
                        color='green', alpha=0.3, label='Optimized better')
        ax2.fill_between(range(len(difference)), difference, 0, where=difference < 0,
                        color='red', alpha=0.3, label='Baseline better')

    ax2.set_xlabel('Trade Number')
    ax2.set_ylabel('Difference (ticks)')
    ax2.set_title('PnL Difference (Optimized - Baseline)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Savings distribution
    ax3 = axes[1, 0]
    results_df = optimized_metrics['results_df']
    executed_savings = results_df[results_df['trade_status'] == 'executed']['total_savings_ticks']

    if len(executed_savings) > 0:
        ax3.hist(executed_savings, bins=50, edgecolor='black', alpha=0.7)
        ax3.axvline(x=executed_savings.mean(), color='red', linestyle='--',
                   linewidth=2, label=f'Mean: {executed_savings.mean():.2f} ticks')
        ax3.axvline(x=0, color='black', linestyle='-', alpha=0.5)

    ax3.set_xlabel('Savings per Trade (ticks)')
    ax3.set_ylabel('Frequency')
    ax3.set_title('Distribution of Savings per Trade')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Plot 4: Trade status
    ax4 = axes[1, 1]
    results_df = optimized_metrics['results_df']
    status_counts = results_df['trade_status'].value_counts()

    colors = ['green' if s == 'executed' else 'orange' for s in status_counts.index]
    ax4.bar(status_counts.index, status_counts.values, edgecolor='black', alpha=0.7, color=colors)

    for i, (status, count) in enumerate(status_counts.items()):
        ax4.text(i, count + 10, f'{count}', ha='center', fontweight='bold')

    ax4.set_xlabel('Trade Status')
    ax4.set_ylabel('Count')
    ax4.set_title('Trade Execution Status')
    ax4.set_xticks(range(len(status_counts)))
    ax4.set_xticklabels(status_counts.index, rotation=15, ha='right')
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    # Save plot
    plot_file = os.path.join(output_path, 'comparison_plots.png')
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"  Plots saved to: {plot_file}")


def main():
    """Main function with CLI interface."""
    parser = argparse.ArgumentParser(description='Compare execution PnL: Agent baseline vs Optimized')
    parser.add_argument('--agent_file', type=str, required=True,
                       help='Path to agent data CSV')
    parser.add_argument('--contract', type=str, default=None,
                       help='Contract name (e.g., NQH20). Auto-detect if not specified')
    parser.add_argument('--bar_freq', type=str, default='1min',
                       choices=['1min', '5min', '15min', '60min'],
                       help='Bar frequency for data (default: 1min)')
    parser.add_argument('--window', type=int, default=60,
                       help='Lookback window size (default: 60)')
    parser.add_argument('--min_penalty', type=float, default=5.0,
                       help='Minimum penalty for optimizer (default: 5.0)')
    parser.add_argument('--max_level', type=float, default=10.0,
                       help='Maximum level for optimizer (default: 10.0)')
    parser.add_argument('--output_dir', type=str, default='execution_pnl_comparison',
                       help='Output directory for results (default: execution_pnl_comparison)')

    args = parser.parse_args()

    print("="*70)
    print("EXECUTION PnL COMPARISON: Agent Baseline vs Optimized Limit Orders")
    print("="*70)

    # Step 1: Load validated timestamps
    matched_df, validated_indices, validated_count = load_validated_timestamps(
        args.agent_file, args.contract, args.bar_freq
    )

    # Step 2: Calculate baseline PnL
    baseline_metrics = calculate_baseline_pnl(matched_df)

    # Step 3: Run optimized strategy on validated timestamps
    # Find contract file in data_export directory
    future_name = args.agent_file.split('/')[-2] if '/' in args.agent_file else 'Nasdaq'
    contract_dir = f'data_export/{future_name}'
    contract_file = os.path.join(contract_dir, f'{args.contract}.csv')

    if not os.path.exists(contract_file):
        # Try alternative naming convention
        contract_files = [f for f in os.listdir(contract_dir) if args.contract in f]
        if contract_files:
            contract_file = os.path.join(contract_dir, contract_files[0])
        else:
            raise FileNotFoundError(f"Could not find contract file for {args.contract} in {contract_dir}")

    optimized_metrics = run_optimized_on_validated(
        matched_df, contract_file,
        window_size=args.window,
        min_penalty=args.min_penalty,
        max_level=args.max_level
    )

    # Step 4: Generate comparison report
    params = {
        'window_size': args.window,
        'min_penalty': args.min_penalty,
        'max_level': args.max_level
    }

    generate_comparison_report(
        matched_df, baseline_metrics, optimized_metrics,
        args.output_dir, args.agent_file, args.contract, params
    )

    print("\n" + "="*70)
    print("COMPARISON COMPLETE")
    print("="*70)


if __name__ == '__main__':
    main()