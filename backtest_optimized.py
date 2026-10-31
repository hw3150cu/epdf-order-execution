"""ROLLING Backtest - Dynamic optimization at each time step
Supports parameter tuning with sub-folder saving for each configuration.

Usage:
    # Quick test (3000 bars - ~5 minutes)
    python backtest_optimized.py --max_bars 3000

    # Single run with default parameters (full dataset - ~1-2 hours)
    python backtest_optimized.py

    # Parameter sweep with limit (5000 bars per config - ~30 minutes)
    python backtest_optimized.py --sweep --max_bars 5000 --cores 3

    # Custom configuration
    python backtest_optimized.py --window 60 --min_penalty 5.0 --max_level 10.0 --max_bars 5000
"""
import warnings
# Suppress delta_grad warnings from scipy.optimize (normal for linear-like utility functions)
warnings.filterwarnings('ignore', message='.*delta_grad.*', category=UserWarning)

from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import os
import argparse
from datetime import datetime
import pandas as pd
from itertools import product
from multiprocessing import Pool, cpu_count
from functools import partial


def run_backtest(df, window_size, min_penalty, max_level, tick_size=0.25, warmup=1000, verbose=True):
    """
    Run rolling backtest with specified parameters.
    
    Args:
        df: DataFrame with OHLC data and state detection
        window_size: Rolling window for ePDF
        min_penalty: Minimum penalty in ticks
        max_level: Maximum level in ticks
        tick_size: Price tick size
        warmup: Number of bars for warmup
        verbose: Print progress
        
    Returns:
        dict with results including savings_history, trade_records, etc.
    """
    # Rolling optimizer
    optimizer = UtilityOptimizer(window_size=window_size, min_penalty=min_penalty, max_level=max_level)
    
    # Run ROLLING backtest
    save = 0.0
    buy_save = 0.0
    sell_save = 0.0
    fill = 0
    buy_fill = 0
    sell_fill = 0
    total = len(df) - warmup
    
    # Track parameter evolution
    params_history = []
    
    # Use numpy arrays for metrics (faster than list append)
    total_bars = len(df) - warmup
    savings_history = np.zeros(total_bars)
    buy_savings_history = np.zeros(total_bars)
    sell_savings_history = np.zeros(total_bars)
    fill_history = np.zeros(total_bars, dtype=int)
    buy_fill_history = np.zeros(total_bars, dtype=int)
    sell_fill_history = np.zeros(total_bars, dtype=int)
    execution_score_history = np.zeros(total_bars)
    
    # Trade records for export (only sample every 100 bars to save time)
    trade_records = []
    trade_record_interval = 100
    
    # OPTIMIZATION: Convert DataFrame to numpy arrays BEFORE loop
    # This is 50-100x faster than df.iloc[i]['field'] access
    open_arr = df['open'].values
    high_arr = df['high'].values
    low_arr = df['low'].values
    close_arr = df['close'].values
    vol_arr = df['vol'].values
    state_arr = df['prev_state'].values
    ts_arr = df['ts'].values
    
    # Keep df reference for optimizer (still needs DataFrame structure)
    # Can optimize this later by passing numpy arrays to optimizer too
    
    iterator = range(warmup, len(df))
    if verbose:
        print(f"\nStarting backtest: {total} bars from {warmup} to {len(df)}")
        print(f"Configuration: window={window_size}, penalty={min_penalty}, max_level={max_level}")
        print("Testing: BUY orders (open-low) + SELL orders (high-open)")
        print("-" * 60)
        import sys
        sys.stdout.flush()
        # Use tqdm for progress bar with estimated time
        iterator = tqdm(iterator, desc="Progress", unit="bar", mininterval=0.1, miniters=100)
    else:
        # For parallel runs, don't use tqdm
        iterator = tqdm(iterator, desc="Progress", unit="bar", mininterval=0.1, miniters=100, disable=True)
    
    for i in iterator:
        # Update tqdm description with current progress
        if verbose and hasattr(iterator, 'set_postfix'):
            progress = (i - warmup) / total * 100
            iterator.set_postfix({'progress': f'{progress:.1f}%'})
        # Step 1: Check liquidity (already filtered: vol > 100)
        
        # Step 2 & 3: Get DYNAMIC optimized params at time t
        # This updates ePDF with history up to t-1 and optimizes
        limits = optimizer.get_limits(df, i, tick_size)
        
        # Track params evolution (sample every 5000 bars)
        if i % 5000 == 0:
            params_history.append((i, limits))
        
        # OPTIMIZATION: Use numpy arrays instead of df.iloc[i] (50-100x faster)
        
        # BUY SIDE: Test limit buy orders below the open (open - low)
        buy_gap = open_arr[i] - low_arr[i]
        buy_save = 0.0
        for level, weight in limits:
            if buy_gap >= level:
                buy_save += weight * level
        
        # SELL SIDE: Test limit sell orders above the open (high - open)
        sell_gap = high_arr[i] - open_arr[i]
        sell_save = 0.0
        for level, weight in limits:
            if sell_gap >= level:
                sell_save += weight * level
        
        # Total savings from both buy and sell orders
        bar_save = buy_save + sell_save
        
        save += bar_save
        if bar_save > 0:
            fill += 1
        
        # Track buy/sell separately
        buy_save += buy_save
        sell_save += sell_save
        if buy_save > 0:
            buy_fill += 1
        if sell_save > 0:
            sell_fill += 1
        
        # Track history using numpy arrays (much faster than list append)
        idx = i - warmup
        savings_history[idx] = bar_save
        buy_savings_history[idx] = buy_save
        sell_savings_history[idx] = sell_save
        fill_history[idx] = 1 if bar_save > 0 else 0
        buy_fill_history[idx] = 1 if buy_save > 0 else 0
        sell_fill_history[idx] = 1 if sell_save > 0 else 0
        
        # OPTIMIZATION: Use numpy arrays instead of df.iloc[i]['field']
        state = state_arr[i]
        expected_close = optimizer.epdf.get_expected_close(state)
        penalty = max(optimizer.min_penalty, (expected_close - open_arr[i]) / tick_size)
        
        # Fill probability: sum of weights for levels that triggered
        # BUY SIDE: levels that filled below open
        buy_fill_prob = 0.0
        for level, weight in limits:
            if buy_gap >= level:
                buy_fill_prob += weight
        
        # SELL SIDE: levels that filled above open
        sell_fill_prob = 0.0
        for level, weight in limits:
            if sell_gap >= level:
                sell_fill_prob += weight
        
        # Total fill probability (combined buy and sell)
        fill_prob = buy_fill_prob + sell_fill_prob
        
        # OPTIMIZATION: Use numpy arrays for calculations
        baseline_pnl = close_arr[i] - open_arr[i]
        
        # Optimized expected PnL: fill * (baseline + savings) - (1 - fill) * penalty
        optimized_pnl_expected = fill_prob * (baseline_pnl + bar_save * tick_size) - (1 - fill_prob) * penalty * tick_size
        
        # Execution score: ratio of improvement to baseline
        if abs(baseline_pnl) > 0 and bar_save > 0:
            execution_score = 1.0 + (bar_save * tick_size) / abs(baseline_pnl)
        else:
            execution_score = 0.0
        
        # Track execution score
        execution_score_history[idx] = execution_score
        
        # Only record trade details periodically (every 100 bars) to avoid overhead
        if i % trade_record_interval == 0:
            record = {
                'bar_index': i,
                'timestamp': ts_arr[i],
                'open': open_arr[i],
                'high': high_arr[i],
                'low': low_arr[i],
                'close': close_arr[i],
                'vol': vol_arr[i],
                'state': state,
                'buy_gap': buy_gap,
                'sell_gap': sell_gap,
                'buy_savings_ticks': buy_save,
                'sell_savings_ticks': sell_save,
                'total_savings_ticks': bar_save,
                'buy_fill_prob': buy_fill_prob,
                'sell_fill_prob': sell_fill_prob,
                'total_fill_prob': fill_prob,
                'expected_close': expected_close,
                'penalty_ticks': penalty,
                'baseline_pnl_realized': baseline_pnl,
                'optimized_pnl_expected': optimized_pnl_expected,
                'pnl_im': optimized_pnl_expected - baseline_pnl,
                'execution_score': execution_score,
            }
            
            # Add each level and weight as separate column
            for idx2, (level, weight) in enumerate(limits, 1):
                record[f'level_{idx2}'] = int(level)  # Round to integer
                record[f'weight_{idx2}'] = round(weight, 1)  # Round to 0.1
            
            trade_records.append(record)
    
    # Print completion message
    if verbose:
        print(f"\n{'='*60}")
        print(f"✓ Completed {total} bars")
        print(f"  Total fills: {fill}/{total} ({fill/total*100:.1f}%)")
        print(f"    Buy fills: {buy_fill}/{total} ({buy_fill/total*100:.1f}%)")
        print(f"    Sell fills: {sell_fill}/{total} ({sell_fill/total*100:.1f}%)")
        print(f"  Total savings: {save:.1f} ticks")
        print(f"    Buy savings: {buy_save:.1f} ticks")
        print(f"    Sell savings: {sell_save:.1f} ticks")
        print(f"{'='*60}\n")
    
    # Calculate summary statistics
    tick_value = tick_size * 50  # $12.5 per tick for NQ
    savings_dollars = save * tick_value
    
    return {
        'window_size': window_size,
        'min_penalty': min_penalty,
        'max_level': max_level,
        'tick_size': tick_size,
        'warmup': warmup,
        'total_trades': total,
        'fills': fill,
        'fill_rate': fill / total * 100 if total > 0 else 0,
        'buy_fills': buy_fill,
        'buy_fill_rate': buy_fill / total * 100 if total > 0 else 0,
        'sell_fills': sell_fill,
        'sell_fill_rate': sell_fill / total * 100 if total > 0 else 0,
        'total_savings_ticks': save,
        'total_savings_dollars': savings_dollars,
        'avg_savings_ticks': save / total if total > 0 else 0,
        'avg_savings_dollars': save / total * tick_value if total > 0 else 0,
        'buy_savings_ticks': buy_save,
        'buy_savings_dollars': buy_save * tick_value,
        'buy_avg_savings_ticks': buy_save / total if total > 0 else 0,
        'sell_savings_ticks': sell_save,
        'sell_savings_dollars': sell_save * tick_value,
        'sell_avg_savings_ticks': sell_save / total if total > 0 else 0,
        'tick_value': tick_value,
        'savings_history': savings_history,
        'buy_savings_history': buy_savings_history,
        'sell_savings_history': sell_savings_history,
        'fill_history': fill_history,
        'buy_fill_history': buy_fill_history,
        'sell_fill_history': sell_fill_history,
        'execution_score_history': execution_score_history,
        'params_history': params_history,
        'trade_records': trade_records,
    }


def save_results(results, output_dir, prefix=''):
    """
    Save backtest results to files.
    
    Args:
        results: dict from run_backtest()
        output_dir: Directory to save files
        prefix: Optional prefix for filenames
    """
    os.makedirs(output_dir, exist_ok=True)
    
    window = results['window_size']
    penalty = results['min_penalty']
    max_lvl = results['max_level']
    
    # Create plots
    savings_history = results['savings_history']
    fill_history = results['fill_history']
    execution_score_history = results['execution_score_history']
    params_history = results['params_history']
    
    # Plot 1: Cumulative Savings
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    cum_savings = np.cumsum(savings_history)
    ax1.plot(cum_savings, label='Cumulative Savings (ticks)', color='blue', linewidth=1.5)
    ax1.set_xlabel('Bar Index')
    ax1.set_ylabel('Cumulative Savings (ticks)')
    ax1.set_title(f'Rolling Optimization - Cumulative Savings\n(w={window}, p={penalty}, l={max_lvl})')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    fig1.savefig(os.path.join(output_dir, f'{prefix}cumulative_savings.png'), dpi=300)
    plt.close(fig1)
    
    # Plot 2: Parameter Evolution (Levels)
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    if params_history:
        bars = [p[0] for p in params_history]
        levels_history = []
        for t, limits in params_history:
            levels_history.append([l for l, w in limits])
        levels_history = np.array(levels_history)
        
        ax2.plot(bars, levels_history[:, 0], label='Level 1', marker='o')
        ax2.plot(bars, levels_history[:, 1], label='Level 2', marker='s')
        ax2.plot(bars, levels_history[:, 2], label='Level 3', marker='^')
        ax2.set_xlabel('Bar Index')
        ax2.set_ylabel('Optimized Levels (ticks)')
        ax2.set_title(f'Rolling Optimization - Dynamic Parameter Evolution\n(w={window}, p={penalty}, l={max_lvl})')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    fig2.savefig(os.path.join(output_dir, f'{prefix}parameter_levels.png'), dpi=300)
    plt.close(fig2)
    
    # Plot 3: Savings Distribution
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    savings_positive = [s for s in savings_history if s > 0]
    if savings_positive:
        ax3.hist(savings_positive, bins=100, alpha=0.7, color='green')
        ax3.axvline(results['avg_savings_ticks'], color='red', linestyle='--', linewidth=2, 
                   label=f'Mean: {results["avg_savings_ticks"]:.2f} ticks')
    ax3.set_xlabel('Savings per Trade (ticks)')
    ax3.set_ylabel('Frequency')
    ax3.set_title(f'Rolling Optimization - Savings Distribution\n(w={window}, p={penalty}, l={max_lvl})')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    fig3.savefig(os.path.join(output_dir, f'{prefix}savings_distribution.png'), dpi=300)
    plt.close(fig3)
    
    # Plot 4: Rolling Fill Rate
    fig4, ax4 = plt.subplots(figsize=(10, 6))
    window = 500
    if len(fill_history) > window:
        rolling_fill_rate = []
        for i in range(window, len(fill_history)):
            rolling_fill_rate.append(np.mean(fill_history[i-window:i]) * 100)
        ax4.plot(rolling_fill_rate, label='Rolling Fill Rate (%)', color='purple', linewidth=1.5)
        ax4.axhline(results['fill_rate'], color='red', linestyle='--', linewidth=2, 
                   label=f'Avg: {results["fill_rate"]:.1f}%')
    ax4.set_xlabel('Bar Index')
    ax4.set_ylabel('Fill Rate (%)')
    ax4.set_title(f'Rolling Optimization - Fill Rate ({window}-bar window)\n(w={window}, p={penalty}, l={max_lvl})')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    fig4.savefig(os.path.join(output_dir, f'{prefix}fill_rate.png'), dpi=300)
    plt.close(fig4)
    
    # Plot 5: Execution Score Over Time
    fig5, ax5 = plt.subplots(figsize=(10, 6))
    ax5.plot(execution_score_history, label='Execution Score', color='blue', alpha=0.5)
    ax5.axhline(1.0, color='green', linestyle='--', linewidth=2, label='Break-even')
    ax5.set_xlabel('Bar')
    ax5.set_ylabel('Execution Score (>1 = improvement)')
    ax5.set_title(f'Execution Score Over Time\n(w={window}, p={penalty}, l={max_lvl})')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    fig5.savefig(os.path.join(output_dir, f'{prefix}execution_score.png'), dpi=300)
    plt.close(fig5)
    
    # Plot 6: Cumulative Comparison
    fig6, ax6 = plt.subplots(figsize=(10, 6))
    warmup = results['warmup']
    # We need to reconstruct this from trade records
    if results['trade_records']:
        baseline_pnls = [r['baseline_pnl_realized'] for r in results['trade_records']]
        optimized_pnls = [r['baseline_pnl_realized'] + r['optimized_savings_ticks'] * results['tick_size'] 
                        for r in results['trade_records']]
        cum_baseline = np.cumsum(baseline_pnls)
        cum_optimized = np.cumsum(optimized_pnls)
        ax6.plot(cum_baseline, label='Baseline', color='gray')
        ax6.plot(cum_optimized, label='Optimized', color='blue')
    ax6.set_xlabel('Bar')
    ax6.set_ylabel('Cumulative Return ($)')
    ax6.set_title(f'Cumulative Return Comparison\n(w={window}, p={penalty}, l={max_lvl})')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    fig6.savefig(os.path.join(output_dir, f'{prefix}cumulative_comparison.png'), dpi=300)
    plt.close(fig6)
    
    # Export trade records to CSV
    trades_df = pd.DataFrame(results['trade_records'])
    trades_df.to_csv(os.path.join(output_dir, f'{prefix}trade_records.csv'), index=False)
    
    # Export summary to text file
    summary_path = os.path.join(output_dir, f'{prefix}summary.txt')
    with open(summary_path, 'w') as f:
        f.write("="*60 + "\n")
        f.write("ROLLING BACKTEST RESULTS\n")
        f.write("="*60 + "\n")
        f.write(f"Parameters:\n")
        f.write(f"  Window Size: {results['window_size']}\n")
        f.write(f"  Min Penalty: {results['min_penalty']}\n")
        f.write(f"  Max Level: {results['max_level']}\n")
        f.write(f"  Tick Size: {results['tick_size']}\n")
        f.write(f"  Tick Value: ${results['tick_value']}\n")
        f.write("\n")
        f.write("Results:\n")
        f.write(f"  Total Trades: {results['total_trades']}\n")
        f.write(f"  Fills: {results['fills']} ({results['fill_rate']:.1f}%)\n")
        f.write(f"  Total Savings: {results['total_savings_ticks']:.1f} ticks (${results['total_savings_dollars']:,.2f})\n")
        f.write(f"  Avg Savings: {results['avg_savings_ticks']:.2f} ticks/trade (${results['avg_savings_dollars']:.2f})\n")
        f.write("="*60 + "\n")
    
    return summary_path


def _run_single_config(args):
    """
    Worker function for multiprocessing - runs a single backtest configuration.
    
    Args:
        args: Tuple of (df_dict, window, penalty, max_level, tick_size, sweep_dir)
        
    Returns:
        dict with results summary
    """
    df_dict, window, penalty, max_level, tick_size, sweep_dir = args
    
    # Reconstruct DataFrame from dict (for multiprocessing serialization)
    import pandas as pd
    df = pd.DataFrame(df_dict)
    
    # Create sub-folder for this configuration
    config_name = f"w{window}_p{penalty}_l{max_level}"
    run_dir = os.path.join(sweep_dir, config_name)
    
    # Run backtest (verbose=False for parallel runs)
    results = run_backtest(
        df, 
        window_size=window, 
        min_penalty=penalty, 
        max_level=max_level,
        tick_size=tick_size,
        verbose=False
    )
    
    # Save results to sub-folder
    save_results(results, run_dir)
    
    # Return summary for comparison
    return {
        'window': window,
        'min_penalty': penalty,
        'max_level': max_level,
        'fill_rate': results['fill_rate'],
        'total_savings_ticks': results['total_savings_ticks'],
        'avg_savings_ticks': results['avg_savings_ticks'],
        'total_savings_dollars': results['total_savings_dollars'],
        'avg_savings_dollars': results['avg_savings_dollars'],
        'config_name': config_name,
        'run_dir': run_dir,
    }


def run_parameter_sweep(df, windows, penalties, max_levels, base_output_dir='results/sweep', tick_size=0.25, n_cores=3):
    """
    Run parameter sweep with multiprocessing and save results to sub-folders.
    
    Args:
        df: DataFrame with OHLC data
        windows: List of window sizes to test
        penalties: List of min_penalty values to test
        max_levels: List of max_level values to test
        base_output_dir: Base directory for results
        tick_size: Price tick size
        n_cores: Number of CPU cores for parallel processing
        
    Returns:
        DataFrame with summary of all runs
    """
    # Create timestamp for this sweep run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    sweep_dir = os.path.join(base_output_dir, f'sweep_{timestamp}')
    os.makedirs(sweep_dir, exist_ok=True)
    
    total_runs = len(windows) * len(penalties) * len(max_levels)
    n_cores = min(n_cores, cpu_count())
    
    print(f"\n{'='*60}")
    print(f"PARAMETER SWEEP: {total_runs} configurations")
    print(f"  Windows: {windows}")
    print(f"  Penalties: {penalties}")
    print(f"  Max Levels: {max_levels}")
    print(f"  Output: {sweep_dir}")
    print(f"  Cores: {n_cores} (of {cpu_count()} available)")
    print(f"{'='*60}\n")
    
    # Prepare arguments for multiprocessing
    # Convert df to dict for better serialization
    df_dict = df.to_dict('list')
    configs = list(product(windows, penalties, max_levels))
    
    # Prepare all arguments
    all_args = [
        (df_dict, window, penalty, max_level, tick_size, sweep_dir)
        for window, penalty, max_level in configs
    ]
    
    # Run with multiprocessing
    all_results = []
    
    if n_cores > 1:
        print(f"Starting parallel processing with {n_cores} cores...")
        
        with Pool(processes=n_cores) as pool:
            # Use imap for progress tracking
            for i, result in enumerate(pool.imap(_run_single_config, all_args), 1):
                all_results.append(result)
                print(f"  [{i}/{total_runs}] Completed: {result['config_name']} "
                      f"(savings: {result['total_savings_ticks']:.1f} ticks)")
    else:
        # Fallback to sequential if n_cores=1
        print("Running sequentially (n_cores=1)...")
        for i, args in enumerate(all_args, 1):
            result = _run_single_config(args)
            all_results.append(result)
            print(f"  [{i}/{total_runs}] Completed: {result['config_name']}")
    
    # Create comparison summary
    comparison_df = pd.DataFrame(all_results)
    comparison_df = comparison_df.sort_values('total_savings_ticks', ascending=False)
    comparison_path = os.path.join(sweep_dir, 'comparison.csv')
    comparison_df.to_csv(comparison_path, index=False)
    
    # Create comparison plot
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Total Savings by Configuration
    ax1 = axes[0, 0]
    bars = ax1.barh(comparison_df['config_name'], comparison_df['total_savings_ticks'])
    ax1.set_xlabel('Total Savings (ticks)')
    ax1.set_title('Total Savings by Configuration')
    ax1.axvline(0, color='red', linestyle='--', alpha=0.5)
    
    # Plot 2: Fill Rate by Configuration
    ax2 = axes[0, 1]
    ax2.barh(comparison_df['config_name'], comparison_df['fill_rate'])
    ax2.set_xlabel('Fill Rate (%)')
    ax2.set_title('Fill Rate by Configuration')
    
    # Plot 3: Avg Savings vs Fill Rate
    ax3 = axes[1, 0]
    scatter = ax3.scatter(comparison_df['fill_rate'], comparison_df['avg_savings_ticks'], 
                         c=comparison_df['min_penalty'], cmap='viridis', s=100)
    plt.colorbar(scatter, ax=ax3, label='Min Penalty')
    ax3.set_xlabel('Fill Rate (%)')
    ax3.set_ylabel('Avg Savings (ticks)')
    ax3.set_title('Avg Savings vs Fill Rate')
    ax3.axhline(0, color='red', linestyle='--', alpha=0.5)
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Heatmap of Total Savings (window x penalty)
    ax4 = axes[1, 1]
    if len(windows) > 1 and len(penalties) > 1:
        pivot = comparison_df.pivot_table(
            values='total_savings_ticks', 
            index='window', 
            columns='min_penalty',
            aggfunc='mean'
        )
        import seaborn as sns
        sns.heatmap(pivot, annot=True, fmt='.0f', cmap='RdYlGn', center=0, ax=ax4)
        ax4.set_title('Total Savings (ticks)')
    else:
        ax4.text(0.5, 0.5, 'Need multiple windows\nand penalties for heatmap', 
                ha='center', va='center', transform=ax4.transAxes)
        ax4.set_title('Heatmap (insufficient data)')
    
    plt.tight_layout()
    fig.savefig(os.path.join(sweep_dir, 'comparison_plot.png'), dpi=300)
    plt.close(fig)
    
    # Print best configuration
    best = comparison_df.iloc[0]
    print(f"\n{'='*60}")
    print("SWEEP COMPLETE!")
    print(f"{'='*60}")
    print(f"Best Configuration: {best['config_name']}")
    print(f"  Fill Rate: {best['fill_rate']:.1f}%")
    print(f"  Total Savings: {best['total_savings_ticks']:.1f} ticks (${best['total_savings_dollars']:,.2f})")
    print(f"  Avg Savings: {best['avg_savings_ticks']:.2f} ticks/trade")
    print(f"\nResults saved to: {sweep_dir}")
    print(f"Comparison CSV: {comparison_path}")
    print(f"{'='*60}")
    
    return comparison_df, sweep_dir


def main():
    parser = argparse.ArgumentParser(description='Rolling Backtest with Parameter Tuning')
    parser.add_argument('--sweep', action='store_true', help='Run parameter sweep')
    parser.add_argument('--window', type=int, default=60, help='Window size for ePDF')
    parser.add_argument('--min_penalty', type=float, default=5.0, help='Minimum penalty in ticks')
    parser.add_argument('--max_level', type=float, default=10.0, help='Maximum level in ticks')
    parser.add_argument('--tick_size', type=float, default=0.25, help='Price tick size')
    parser.add_argument('--data', type=str, default='data_export/Nasdaq/NQH20.csv', help='Path to data file')
    parser.add_argument('--output', type=str, default='results', help='Output directory')
    parser.add_argument('--vol_filter', type=int, default=100, help='Volume filter threshold')
    parser.add_argument('--max_bars', type=int, default=None, help='Limit to first N bars for quick testing (e.g., 3000, 5000)')
    parser.add_argument('--warmup', type=int, default=None, help='Warmup bars (defaults to 1000, or 20% of max_bars if specified)')
    
    # Sweep parameters
    parser.add_argument('--windows', type=str, default='60,120,240,480', help='Comma-separated window sizes for sweep')
    parser.add_argument('--penalties', type=str, default='3,5,10', help='Comma-separated penalties for sweep')
    parser.add_argument('--max_levels', type=str, default='3,5', help='Comma-separated max levels for sweep')
    parser.add_argument('--cores', type=int, default=3, help='Number of CPU cores for parallel processing (sweep only)')
    
    args = parser.parse_args()
    
    # Load data
    loader = DataLoader(tick_size=args.tick_size)
    df = loader.load_csv(args.data)
    df = df[(df['vol'] > args.vol_filter)].copy()
    
    print(f"Loaded {len(df)} bars (vol > {args.vol_filter})")
    
    # Apply max_bars limit for quick testing
    if args.max_bars is not None:
        original_len = len(df)
        df = df.iloc[:args.max_bars].copy()
        print(f"  Limited to first {len(df)} bars (was {original_len})")
        # Default warmup to 20% of max_bars for small datasets
        if args.warmup is None:
            args.warmup = max(100, int(args.max_bars * 0.2))
    else:
        # Default warmup for full dataset
        args.warmup = 1000 if args.warmup is None else args.warmup
    
    # Detect states
    detector = StateDetector(thresh=2.5)
    df = detector.detect_states(df)
    
    if args.sweep:
        # Parse sweep parameters
        windows = [int(x) for x in args.windows.split(',')]
        penalties = [float(x) for x in args.penalties.split(',')]
        max_levels = [float(x) for x in args.max_levels.split(',')]
        
        # Run parameter sweep
        comparison_df, sweep_dir = run_parameter_sweep(
            df, 
            windows=windows,
            penalties=penalties,
            max_levels=max_levels,
            base_output_dir=args.output,
            tick_size=args.tick_size,
            n_cores=args.cores
        )
    else:
        # Single run
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        config_name = f"w{args.window}_p{args.min_penalty}_l{args.max_level}"
        run_dir = os.path.join(args.output, f'run_{timestamp}_{config_name}')
        
        print(f"\nRunning single configuration: {config_name}")
        print(f"Output: {run_dir}\n")
        
        results = run_backtest(
            df,
            window_size=args.window,
            min_penalty=args.min_penalty,
            max_level=args.max_level,
            tick_size=args.tick_size,            warmup=args.warmup,            verbose=True  # Enable progress output
        )
        
        save_results(results, run_dir)
        
        print(f"\n{'='*60}")
        print("BACKTEST COMPLETE!")
        print(f"{'='*60}")
        print(f"Total Fill Rate: {results['fill_rate']:.1f}%")
        print(f"  Buy Fill Rate: {results['buy_fill_rate']:.1f}%")
        print(f"  Sell Fill Rate: {results['sell_fill_rate']:.1f}%")
        print(f"\nTotal Savings: {results['total_savings_ticks']:.1f} ticks (${results['total_savings_dollars']:,.2f})")
        print(f"  Buy Savings: {results['buy_savings_ticks']:.1f} ticks (${results['buy_savings_dollars']:,.2f})")
        print(f"  Sell Savings: {results['sell_savings_ticks']:.1f} ticks (${results['sell_savings_dollars']:,.2f})")
        print(f"Avg Savings: {results['avg_savings_ticks']:.2f} ticks/trade (${results['avg_savings_dollars']:.2f})")
        print(f"\nResults saved to: {run_dir}")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()