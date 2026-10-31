"""
Simple agent PnL comparison - use matched data directly.

Approach:
1. Get validated data from DataMatcher (already has OHLC and agent price/volume)
2. Calculate baseline: Agent savings = Open - Agent_Price
3. Apply optimized limit order strategy on same validated timestamps
4. Save detailed trade records with limit levels, weights, state, direction
"""

import pandas as pd
import numpy as np
from tqdm import tqdm
import os
from datetime import datetime
import argparse

from data_matcher import DataMatcher
from strategies_optimized_final import UtilityOptimizer
from state_detection import StateDetector


def compare_agent_vs_optimized(agent_file, contract_name,
                                window_size=60, min_penalty=5.0,
                                max_level=10.0, tick_size=0.25):
    """
    Compare agent execution vs optimized limit orders.

    Args:
        agent_file: Path to agent data CSV
        contract_name: Contract name (e.g., 'NQH20')
        window_size: Window size for ePDF
        min_penalty: Minimum penalty
        max_level: Maximum level
        tick_size: Tick size

    Returns:
        Dict with baseline and optimized results
    """
    print("="*70)
    print("AGENT vs OPTIMIZED COMPARISON")
    print("="*70)

    # Step 1: Load matched validated data
    print("\n1. Loading validated data...")
    matcher = DataMatcher(agent_file, 'data_export')
    matched_df = matcher.match_data(contract_name)

    if matched_df is None:
        raise ValueError(f"Failed to match data for {contract_name}")

    # Filter to validated (price within OHLC) AND actual trades (vol > 0)
    validated_df = matched_df[(matched_df['status'] == 'valid') & (matched_df['vol'] > 0)].copy()
    print(f"   Validated price matches: {len(matched_df[matched_df['status'] == 'valid'])}")
    print(f"   Actual trades (vol > 0): {len(validated_df)}")

    # Step 2: Calculate baseline (agent performance)
    print("\n2. Calculating baseline (agent execution)...")
    validated_df['agent_savings'] = validated_df['open'] - validated_df['price']
    validated_df['agent_savings_ticks'] = validated_df['agent_savings'] / tick_size

    # Calculate agent buy and sell savings separately
    # If agent_price <= open: agent is buying (got <= market price)
    # If agent_price > open: agent is selling (got > market price)
    validated_df['agent_buy_savings_ticks'] = 0.0
    validated_df['agent_sell_savings_ticks'] = 0.0

    buy_mask = validated_df['price'] <= validated_df['open']
    validated_df.loc[buy_mask, 'agent_buy_savings_ticks'] = (
        validated_df.loc[buy_mask, 'open'] - validated_df.loc[buy_mask, 'price']
    ) / tick_size

    sell_mask = validated_df['price'] > validated_df['open']
    validated_df.loc[sell_mask, 'agent_sell_savings_ticks'] = (
        validated_df.loc[sell_mask, 'price'] - validated_df.loc[sell_mask, 'open']
    ) / tick_size

    baseline_savings_ticks = validated_df['agent_savings_ticks'].sum()
    baseline_buy_savings_ticks = validated_df['agent_buy_savings_ticks'].sum()
    baseline_sell_savings_ticks = validated_df['agent_sell_savings_ticks'].sum()
    baseline_savings_dollars = baseline_savings_ticks * tick_size * 20  # $20/tick for NQ

    print(f"   Agent total savings: {baseline_savings_ticks:.1f} ticks (${baseline_savings_dollars:,.2f})")
    print(f"   Agent buy savings:   {baseline_buy_savings_ticks:.1f} ticks")
    print(f"   Agent sell savings:  {baseline_sell_savings_ticks:.1f} ticks")
    print(f"   Avg per trade: {validated_df['agent_savings_ticks'].mean():.2f} ticks")

    # Step 3: Prepare for optimization
    print("\n3. Preparing optimization...")

    # Add required columns
    validated_df['range_dn_ticks'] = (validated_df['open'] - validated_df['low']) / tick_size
    validated_df['range_up_ticks'] = (validated_df['high'] - validated_df['open']) / tick_size

    # Detect states
    detector = StateDetector(m=60, thresh=2.5)
    validated_df = detector.detect_states(validated_df)

    # Initialize optimizer
    optimizer = UtilityOptimizer(
        window_size=window_size,
        min_penalty=min_penalty,
        max_level=max_level
    )

    # Step 4: Apply optimized strategy on validated timestamps
    print("\n4. Applying optimized strategy...")
    print(f"   Window: {window_size}, Min penalty: {min_penalty}, Max level: {max_level}")

    warmup = window_size  # Need historical data
    total_trades = len(validated_df) - warmup

    optimized_savings = np.zeros(total_trades)
    buy_savings = np.zeros(total_trades)
    sell_savings = np.zeros(total_trades)

    # Track detailed trade records
    trade_records = []

    # Convert to numpy arrays for speed
    open_arr = validated_df['open'].values
    high_arr = validated_df['high'].values
    low_arr = validated_df['low'].values
    close_arr = validated_df['close'].values
    agent_price_arr = validated_df['price'].values
    vol_arr = validated_df['vol'].values
    agent_savings_arr = validated_df['agent_savings_ticks'].values

    print(f"   Processing {total_trades} trades (warmup={warmup})...")

    for i in tqdm(range(warmup, len(validated_df)), desc="Optimizing"):
        # Get current bar info
        current_time = validated_df.index[i]
        state = validated_df.iloc[i]['prev_state']

        # Determine trade direction based on agent's price
        # If agent_price <= open, agent is BUYING (got <= market price)
        # If agent_price > open, agent is SELLING (got > market price)
        # This matches the baseline calculation: agent_savings = (open - price) / tick_size
        if agent_price_arr[i] <= open_arr[i]:
            direction = 'buy'
        else:
            direction = 'sell'

        # Get optimal limits for the specific direction
        limits = optimizer.get_limits(validated_df, i, tick_size, direction)

        # Calculate savings for the direction we're trading
        if direction == 'buy':
            buy_gap_dollars = open_arr[i] - low_arr[i]
            buy_gap_ticks = buy_gap_dollars / tick_size  # Convert to ticks
            buy_save = 0.0
            buy_levels_used = []
            for level, weight in limits:
                if buy_gap_ticks >= level:  # Compare ticks to ticks!
                    buy_save += weight * level
                    buy_levels_used.append(f"{level:.1f}t@{weight:.2f}")
            
            total_save = buy_save  # Only count buy savings (already in ticks!)
            sell_save = 0.0
            sell_levels_used = []
        else:  # sell direction
            sell_gap_dollars = high_arr[i] - open_arr[i]
            sell_gap_ticks = sell_gap_dollars / tick_size  # Convert to ticks
            sell_save = 0.0
            sell_levels_used = []
            for level, weight in limits:
                if sell_gap_ticks >= level:  # Compare ticks to ticks!
                    sell_save += weight * level
                    sell_levels_used.append(f"{level:.1f}t@{weight:.2f}")
            
            total_save = sell_save  # Only count sell savings (already in ticks!)
            buy_save = 0.0
            buy_levels_used = []

        idx = i - warmup
        optimized_savings[idx] = total_save
        buy_savings[idx] = buy_save
        sell_savings[idx] = sell_save

        # Save detailed trade record
        trade_records.append({
            'timestamp': current_time,
            'state': state,
            'direction': direction,
            'agent_price': agent_price_arr[i],
            'open': open_arr[i],
            'high': high_arr[i],
            'low': low_arr[i],
            'close': close_arr[i],
            'vol': vol_arr[i],
            'agent_savings_ticks': agent_savings_arr[i],
            'agent_buy_savings_ticks': validated_df.iloc[i]['agent_buy_savings_ticks'],
            'agent_sell_savings_ticks': validated_df.iloc[i]['agent_sell_savings_ticks'],
            'optimized_buy_savings': buy_save,
            'optimized_sell_savings': sell_save,
            'optimized_total_savings': total_save,
            'savings_difference': total_save - agent_savings_arr[i],
            'optimized_limits': str(limits),
            'buy_levels_used': '|'.join(buy_levels_used),
            'sell_levels_used': '|'.join(sell_levels_used)
        })

    total_optimized_savings = optimized_savings.sum()
    total_optimized_buy_savings = buy_savings.sum()
    total_optimized_sell_savings = sell_savings.sum()
    total_optimized_dollars = total_optimized_savings * tick_size * 20

    print(f"   Optimized total savings: {total_optimized_savings:.1f} ticks (${total_optimized_dollars:,.2f})")
    print(f"   Optimized buy savings:   {total_optimized_buy_savings:.1f} ticks")
    print(f"   Optimized sell savings:  {total_optimized_sell_savings:.1f} ticks")

    # Step 5: Comparison
    improvement = total_optimized_savings - baseline_savings_ticks
    improvement_pct = (improvement / baseline_savings_ticks * 100) if baseline_savings_ticks > 0 else 0

    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"{'Metric':<25} {'Agent':<15} {'Optimized':<15} {'Difference':<15}")
    print("-"*70)
    print(f"{'Total Savings':<25} {baseline_savings_ticks:<15.1f} {total_optimized_savings:<15.1f} {improvement:+.1f}")
    print(f"{'Buy Savings':<25} {baseline_buy_savings_ticks:<15.1f} {total_optimized_buy_savings:<15.1f} {total_optimized_buy_savings - baseline_buy_savings_ticks:+.1f}")
    print(f"{'Sell Savings':<25} {baseline_sell_savings_ticks:<15.1f} {total_optimized_sell_savings:<15.1f} {total_optimized_sell_savings - baseline_sell_savings_ticks:+.1f}")
    print("-"*70)
    print(f"{'Dollars':<25} ${baseline_savings_dollars:,.2f}     ${total_optimized_dollars:,.2f}     ${improvement * tick_size * 20:+,.2f}")
    print(f"{'Improvement %':<25} {'':<15} {'':<15} {improvement_pct:+.1f}%")
    print("="*70)

    # Step 6: Save detailed trade records
    print("\n5. Saving trade records...")
    output_dir = 'agent_comparison_results'
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = os.path.join(output_dir, f'{contract_name}_detailed_trades_{timestamp}.csv')

    # Create DataFrame from trade records
    trades_df = pd.DataFrame(trade_records)
    trades_df.to_csv(csv_file, index=False)
    print(f"   Saved {len(trades_df)} trade records to: {csv_file}")

    # Save summary
    summary_file = os.path.join(output_dir, f'{contract_name}_summary_{timestamp}.txt')
    with open(summary_file, 'w') as f:
        f.write("AGENT vs OPTIMIZED COMPARISON SUMMARY\n")
        f.write("="*70 + "\n\n")
        f.write(f"Contract: {contract_name}\n")
        f.write(f"Agent file: {agent_file}\n")
        f.write(f"Parameters: window={window_size}, min_penalty={min_penalty}, max_level={max_level}\n\n")
        f.write(f"Total validated trades: {total_trades}\n")
        f.write(f"Warmup bars: {warmup}\n\n")
        f.write("PERFORMANCE:\n")
        f.write("-"*60 + "\n")
        f.write(f"Total Savings:\n")
        f.write(f"  Agent:      {baseline_savings_ticks:.1f} ticks (${baseline_savings_dollars:,.2f})\n")
        f.write(f"  Optimized:  {total_optimized_savings:.1f} ticks (${total_optimized_dollars:,.2f})\n")
        f.write(f"  Improvement: {improvement:+.1f} ticks ({improvement_pct:+.1f}%)\n\n")
        f.write(f"Buy Savings:\n")
        f.write(f"  Agent:      {baseline_buy_savings_ticks:.1f} ticks\n")
        f.write(f"  Optimized:  {total_optimized_buy_savings:.1f} ticks\n")
        f.write(f"  Difference: {total_optimized_buy_savings - baseline_buy_savings_ticks:+.1f} ticks\n\n")
        f.write(f"Sell Savings:\n")
        f.write(f"  Agent:      {baseline_sell_savings_ticks:.1f} ticks\n")
        f.write(f"  Optimized:  {total_optimized_sell_savings:.1f} ticks\n")
        f.write(f"  Difference: {total_optimized_sell_savings - baseline_sell_savings_ticks:+.1f} ticks\n\n")
        f.write(f"Avg improvement/trade: {improvement/total_trades:.2f} ticks\n\n")
        f.write(f"Detailed trades saved to: {csv_file}\n")

    print(f"   Saved summary to: {summary_file}")

    return {
        'baseline_savings_ticks': baseline_savings_ticks,
        'baseline_buy_savings_ticks': baseline_buy_savings_ticks,
        'baseline_sell_savings_ticks': baseline_sell_savings_ticks,
        'baseline_savings_dollars': baseline_savings_dollars,
        'optimized_savings_ticks': total_optimized_savings,
        'optimized_buy_savings_ticks': total_optimized_buy_savings,
        'optimized_sell_savings_ticks': total_optimized_sell_savings,
        'optimized_savings_dollars': total_optimized_dollars,
        'improvement_ticks': improvement,
        'improvement_pct': improvement_pct,
        'num_trades': total_trades,
        'baseline_cumulative': validated_df['agent_savings_ticks'].cumsum().tolist()[warmup:],
        'optimized_cumulative': optimized_savings.cumsum().tolist(),
        'trade_records': trade_records,
        'trades_df': trades_df,
        'output_file': csv_file
    }


if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Compare agent PnL with optimized limit order strategy')
    parser.add_argument('--window', type=int, choices=[60, 120, 240], default=60,
                        help='Window size for ePDF (default: 60)')
    parser.add_argument('--all', action='store_true',
                        help='Run comparison with all window sizes (60, 120, 240)')
    args = parser.parse_args()

    if args.all:
        # Test with NQH20 - multiple window sizes
        window_sizes = [60, 120, 240]
        print("\n" + "="*70)
        print("TESTING DIFFERENT WINDOW SIZES")
        print("="*70 + "\n")
        all_results = []
        for window_size in window_sizes:
            print(f"\n>>> Testing with window_size={window_size} <<<\n")
            results = compare_agent_vs_optimized(
                agent_file='data_export/Nasdaq/AIAgent_Nasdaq.csv',
                contract_name='NQH20',
                window_size=window_size,
                min_penalty=5.0,
                max_level=10.0,
                tick_size=0.25
            )
            results['window_size'] = window_size
            all_results.append(results)

        # Summary comparison
        print("\n" + "="*70)
        print("SUMMARY COMPARISON ACROSS WINDOW SIZES")
        print("="*70)
        print(f"{'Window':<10} {'Total':<15} {'Buy':<12} {'Sell':<12} {'Improvement':<15} {'Trades':<10}")
        print("-"*70)
        for r in all_results:
            print(f"{r['window_size']:<10} "
                  f"{r['baseline_savings_ticks']:<15.1f} "
                  f"{r['baseline_buy_savings_ticks']:<12.1f} "
                  f"{r['baseline_sell_savings_ticks']:<12.1f} "
                  f"{r['improvement_ticks']:<15.1f} "
                  f"{r['num_trades']:<10}")
        print("="*70)
        print("\nDetailed breakdown:")
        print(f"{'Window':<10} {'Agent':<15} {'Optimized':<15} {'Diff':<10}")
        print("-"*70)
        for r in all_results:
            buy_diff = r['optimized_buy_savings_ticks'] - r['baseline_buy_savings_ticks']
            sell_diff = r['optimized_sell_savings_ticks'] - r['baseline_sell_savings_ticks']
            print(f"{r['window_size']:<10} Buy:  {r['baseline_buy_savings_ticks']:<7.1f} -> {r['optimized_buy_savings_ticks']:<7.1f} {buy_diff:+7.1f}")
            print(f"{'':<10} Sell: {r['baseline_sell_savings_ticks']:<7.1f} -> {r['optimized_sell_savings_ticks']:<7.1f} {sell_diff:+7.1f}")
            print("-"*70)
        print("="*70)
    else:
        # Run with single window size
        print("\n" + "="*70)
        print(f"AGENT vs OPTIMIZED COMPARISON (Window Size: {args.window})")
        print("="*70 + "\n")
        results = compare_agent_vs_optimized(
            agent_file='data_export/Nasdaq/AIAgent_Nasdaq.csv',
            contract_name='NQH20',
            window_size=args.window,
            min_penalty=5.0,
            max_level=10.0,
            tick_size=0.25
        )