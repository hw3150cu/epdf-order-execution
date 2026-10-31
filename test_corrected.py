"""
Test Runner for CORRECTED Methodology
- Uses open[t] as reference price
- Configurable tick_size
"""

import matplotlib.pyplot as plt
import numpy as np
import os

from data_loader import DataLoader
from state_detection import StateDetector
from backtest_engine_corrected import BacktestEngine
from strategies_utility_clean import UtilityOptimizerStrategy


def test_corrected_methodology(tick_size: float = 0.25):
    """
    Test the corrected methodology on full dataset.
    """
    print("=" * 80)
    print("CORRECTED METHODOLOGY TEST")
    print("=" * 80)
    
    os.makedirs('results', exist_ok=True)
    
    # 1. Load data
    print("\n1. Loading data...")
    loader = DataLoader(tick_size=tick_size)
    data_path = "os.path.join(os.environ.get("ORDER_DATA_ROOT", "data_export"), "Nasdaq", "NQH20.csv")"
    df = loader.load_csv(data_path)
    print(f"   Loaded {len(df)} bars")
    print(f"   Tick size: ${tick_size}")
    
    # 2. Detect states
    print("\n2. Detecting volatility regimes...")
    detector = StateDetector(m=20, low_thresh=1.5, high_thresh=3.0)
    df = detector.detect_states(df)
    counts = df['prev_state'].value_counts()
    print(f"   Regime distribution:")
    for state in ['Low', 'Med', 'High']:
        n = counts.get(state, 0)
        pct = n / len(df) * 100
        print(f"     {state}: {n:,} bars ({pct:.1f}%)")
    
    # 3. Initialize strategy
    print("\n3. Initializing utility optimizer...")
    strategy = UtilityOptimizerStrategy(
        window_size=60,
        penalty_ticks=10.0,
        price_levels=[0.0, 1.0, 2.0]
    )
    print(f"   Reference: open[t] (CORRECTED)")
    print(f"   Penalty: {strategy.penalty_ticks} ticks (${strategy.penalty * tick_size:.2f})")
    print(f"   Price levels: {strategy.price_levels} ticks")
    
    # 4. Run backtest
    print("\n4. Running backtest with CORRECTED reference price...")
    engine = BacktestEngine(tick_size=tick_size, warmup_bars=50)
    result = engine.backtest(df, strategy)
    
    print(f"   Fill Rate: {result.fill_rate:.2%}")
    print(f"   Avg Savings: {result.avg_savings:.4f} ticks (${result.avg_savings * tick_size:.2f})")
    print(f"   Total Savings: {result.total_savings:.0f} ticks (${result.total_savings * tick_size:.2f})")
    
    # 5. Plot results
    print("\n5. Plotting results...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Cumulative returns
    cum_strategy = np.cumsum(result.strategy_returns)
    cum_baseline = np.cumsum(result.baseline_returns)
    
    axes[0, 0].plot(cum_baseline, label='Baseline (Market at Close)', color='gray', alpha=0.7)
    axes[0, 0].plot(cum_strategy, label='Utility Optimizer', color='blue', alpha=0.7)
    axes[0, 0].set_xlabel('Bar Index')
    axes[0, 0].set_ylabel('Cumulative Returns (ticks)')
    axes[0, 0].set_title('Cumulative Returns (CORRECTED: open[t] reference)')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Plot 2: Savings distribution
    axes[0, 1].hist(result.strategy_returns, bins=50, color='green', alpha=0.7)
    axes[0, 1].axvline(result.avg_savings, color='red', linestyle='--', 
                        label=f'Mean: {result.avg_savings:.4f} ticks')
    axes[0, 1].set_xlabel('Savings (ticks)')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 1].set_title('Savings Distribution (Reference: open[t])')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0, .3)
    
    # Plot 3: Rolling fill rate
    fill_rates = [trade['fill_rate'] for trade in result.trades]
    rolling_fill = np.convolve(fill_rates, np.ones(100)/100, mode='valid')
    axes[1, 0].plot(rolling_fill)
    axes[1, 0].set_xlabel('Bar Index')
    axes[1, 0].set_ylabel('Rolling Fill Rate (100 bars)')
    [0].set_xlabel('Bar', index)
    axes[1, 0].set_title('Rolling Fill Rate Over Time')
    axes[1, 0].grid(True, alpha=0.3)
    
    # Plot 4: Weight distribution
    weights_by_level = [[], [], []]
    for trade in result.trades:
        if 'limit_weights' in trade:
            for i, w in enumerate(trade['limit_weights']):
                weights_by_level[i].append(w)
    
    for i in range(3):
        axes[1, 1].hist(weights_by_level[i], bins=20, alpha=0.5,
                          label=f'Level {i} ({i} ticks)')
    axes[1, 1].set_xlabel('Weight')
    [1].set_ylabel('Frequency', axis[1], .set_xlabel('Bar'))
    axes[1, 1].set_title('Optimized Weight Distribution by Price Level')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight()
    output_path = 'results/corrected_results.png'
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"   Saved to: {output_path}")
    plt.close(fig)
    
    # Summary
    print("\n" + "=" * 80)
    print("CORRECTED METHODOLOGY TEST COMPLETE!")
    print("=" * 80)
    print(f"\nKey Metrics:")
    print(f"  Fill Rate: {result.fill_rate:.2%}")
    print(f"  Avg Savings: {result.avg_savings:.4f} ticks (${result.avg_savings * tick_size:.2f})")
    print(f"  Total Savings: {result.total_savings:.0f} ticks (${result.total_savings * tick:.2f})")
    print(f"\nComparison:")
    print(f"  Reference Price: open[t] (CORRECTED)")
    print(f"  Old (close[t-1]): See results/utility_vs_baseline.png")
    print(f"  New (open[t]): See results/corrected_results.png")
    print("\n" + "=" * 80)


if __name__ == '__main__':
    test_corrected_methodology(tick_size=0.25)