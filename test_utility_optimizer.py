"""
Test Runner for Utility-Based Optimization Strategy
Tests on first 10k bars for speed
"""

import matplotlib.pyplot as plt
import numpy as np
import os

from data_loader import DataLoader
from state_detection import StateDetector
from epdf import build_epdfs
from backtest_engine import BacktestEngine
from strategies_utility_clean import UtilityOptimizerStrategy
from visualizer import Visualizer


def plot_optimization_results(trades: list):
    """
    Plot optimization analysis.
    
    Args:
        trades: List of trade dicts
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Weight distribution across levels
    level_weights = [[] for _ in range(3)]  # 3 levels
    for trade in trades:
        if 'limit_weights' in trade:
            for i, w in enumerate(trade['limit_weights']):
                level_weights[i].append(w)
    
    for i, weights in enumerate(level_weights):
        axes[0, 0].hist(weights, bins=20, alpha=0.7, label=f'Level {i} ({i} ticks)')
    axes[0, 0].set_xlabel('Weight')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Optimized Weight Distribution by Price Level')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Plot 2: Fill rate over time (rolling)
    fill_rates = [trade['fill_rate'] for trade in trades]
    rolling_fill = np.convolve(fill_rates, np.ones(100)/100, mode='valid')
    axes[0, 1].plot(rolling_fill)
    axes[0, 1].set_xlabel('Bar Index')
    axes[0, 1].set_ylabel('Rolling Fill Rate (100 bars)')
    axes[0, 1].set_title('Rolling Fill Rate Over Time')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Plot 3: Savings distribution
    savings = [trade['savings'] for trade in trades]
    axes[1, 0].hist(savings, bins=50, alpha=0.7, color='green')
    axes[1, 0].axvline(np.mean(savings), color='red', linestyle='--', 
                        label=f'Mean: {np.mean(savings):.4f} ticks')
    axes[1, 0].set_xlabel('Savings (ticks)')
    axes[1, 0].set_ylabel('Frequency')
    axes[1, 0].set_title('Savings Distribution')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # Plot 4: Cumulative savings
    cum_savings = np.cumsum([trade['savings'] for trade in trades])
    axes[1, 1].plot(cum_savings)
    axes[1, 1].set_xlabel('Bar Index')
    axes[1, 1].set_ylabel('Cumulative Savings (ticks)')
    axes[1, 1].set_title('Cumulative Savings Over Backtest')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def main():
    """Main test runner"""
    print("=" * 80)
    print("UTILITY-BASED OPTIMIZER TEST (First 10k bars)")
    print("=" * 80)
    
    # Create results directory
    os.makedirs('results', exist_ok=True)
    
    # 1. Load data
    print("\n1. Loading data...")
    data_path = "os.path.join(os.environ.get("ORDER_DATA_ROOT", "data_export"), "Nasdaq", "NQH20.csv")"
    loader = DataLoader(tick_size=0.25)
    df = loader.load_csv(data_path)
    print(f"   Loaded {len(df)} bars")
    
    # Limit to first 10k bars for speed
    df = df.iloc[:10000]
    print(f"   Using first {len(df)} bars for optimization test")
    
    # 2. Detect states
    print("\n2. Detecting volatility states...")
    detector = StateDetector(m=20, low_thresh=1.5, high_thresh=3.0)
    df = detector.detect_states(df)
    print(f"   States detected")
    
    # 3. Initialize utility optimizer
    print("\n3. Initializing utility optimizer...")
    strategy = UtilityOptimizerStrategy(
        window_size=60,
        penalty_ticks=10.0,
        price_levels=[0.0, 1.0, 2.0]  # close, close-1 tick, close-2 ticks
    )
    print(f"   Penalty: {strategy.penalty_ticks} ticks")
    print(f"   Price levels: {strategy.price_levels}")
    
    # 4. Run backtest
    print("\n4. Running backtest with utility optimization...")
    engine = BacktestEngine(tick_size=0.25, warmup_bars=50)
    result = engine.backtest(df, strategy)
    
    print(f"   Fill Rate: {result.fill_rate:.2%}")
    print(f"   Avg Savings: {result.avg_savings:.4f} ticks")
    print(f"   Total Savings: {result.total_savings:.0f} ticks")
    
    # 5. Plot optimization results
    print("\n5. Plotting optimization results...")
    fig = plot_optimization_results(result.trades)
    output_path = 'results/utility_optimization_results.png'
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"   Saved to: {output_path}")
    plt.close(fig)
    
    # 6. Compare with baseline
    print("\n6. Comparing with market-order baseline...")
    fig, ax = plt.subplots(figsize=(12, 6))
    
    baseline_cum = np.cumsum(result.baseline_returns)
    strategy_cum = np.cumsum(result.strategy_returns)
    
    ax.plot(baseline_cum, label='Baseline (Market Order)', alpha=0.7, color='gray')
    ax.plot(strategy_cum, label='Utility Optimizer', alpha=0.7, color='blue')
    ax.set_xlabel('Bar Index')
    ax.set_ylabel('Cumulative Returns (ticks)')
    ax.set_title('Cumulative Returns: Baseline vs Utility Optimizer')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    output_path = 'results/utility_vs_baseline.png'
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"   Saved to: {output_path}")
    plt.close(fig)
    
    # Summary
    print("\n" + "=" * 80)
    print("UTILITY OPTIMIZER TEST COMPLETE!")
    print("=" * 80)
    print(f"\nKey Metrics:")
    print(f"  Fill Rate: {result.fill_rate:.2%}")
    print(f"  Avg Savings: {result.avg_savings:.4f} ticks (${result.avg_savings * 0.25:.2f})")
    print(f"  Total Savings: {result.total_savings:.0f} ticks (${result.total_savings * 0.25:.2f})")
    print(f"\nOutputs:")
    print(f"  ✓ results/utility_optimization_results.png")
    print(f"  ✓ results/utility_vs_baseline.png")


if __name__ == '__main__':
    main()