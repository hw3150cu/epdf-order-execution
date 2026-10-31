"""
Test Runner for Phase 2: Backtesting + Fill Probability
"""

import matplotlib.pyplot as plt
import numpy as np
import os

from data_loader import DataLoader
from state_detection import StateDetector
from epdf import build_epdfs
from backtest_engine import BacktestEngine
from strategies import LimitOrderStrategy
from visualizer import Visualizer


def calculate_fill_probability_curve(trades: list) -> tuple:
    """
    Calculate P(fill | distance from open) for fill probability chart.
    
    Args:
        trades: List of trade dicts with new structure
    
    Returns:
        (distances, fill_probabilities)
    """
    # Bin trades by distance to best (lowest) limit price
    distances = []
    filled_per_distance = {}
    
    for trade in trades:
        # Distance to best (lowest) mode
        best_limit = min([p for p in trade['limit_prices']])
        distance = trade['open'] - best_limit
        distances.append(distance)
        
        if distance not in filled_per_distance:
            filled_per_distance[distance] = []
        # fill_rate > 0 means at least partially filled
        filled_per_distance[distance].append(trade['fill_rate'] > 0)
    
    # Calculate fill probability per distance
    sorted_distances = sorted(filled_per_distance.keys())
    fill_probs = []
    
    for dist in sorted_distances:
        filled_count = sum(filled_per_distance[dist])
        total_count = len(filled_per_distance[dist])
        fill_prob = filled_count / total_count if total_count > 0 else 0
        fill_probs.append(fill_prob)
    
    return np.array(sorted_distances), np.array(fill_probs)


def plot_fill_probability_curve(distances: np.ndarray, fill_probs: np.ndarray, save_path: str = None):
    """
    Plot fill probability curve (survival-style).
    
    Args:
        distances: Distance from open (ticks)
        fill_probs: Fill probability at each distance
        save_path: Path to save plot
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(distances, fill_probs, 'b-o', linewidth=2, markersize=6)
    ax.set_xlabel('Distance from Open (ticks)', fontsize=12)
    ax.set_ylabel('Fill Probability', fontsize=12)
    ax.set_title('Fill Probability vs. Limit Order Distance', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.05])
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def main():
    """Run Phase 2 test"""
    print("="*80)
    print("PHASE 2: BACKTESTING + FILL PROBABILITY")
    print("="*80)
    
    # Load data
    print("\n1. Loading data...")
    loader = DataLoader()
    df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
    print(f"   Loaded {len(df)} bars")
    
    # Detect states
    print("\n2. Detecting states...")
    detector = StateDetector()
    df = detector.detect_states(df)
    
    # Build ePDFs
    print("\n3. Building ePDFs...")
    epdfs = build_epdfs(df)
    
    # Run backtest
    print("\n4. Running backtest...")
    engine = BacktestEngine(warmup_bars=50)
    strategy = LimitOrderStrategy()
    result = engine.backtest(df, strategy)
    
    print(f"   Fill Rate: {result.fill_rate:.2%}")
    print(f"   Avg Savings: {result.avg_savings:.4f} ticks")
    print(f"   Total Savings: {result.total_savings:.0f} ticks")
    
    # Create output directory
    os.makedirs('results', exist_ok=True)
    
    # Plot fill probability curve
    print("\n5. Plotting fill probability curve...")
    distances, fill_probs = calculate_fill_probability_curve(result.trades)
    plot_fill_probability_curve(
        distances,
        fill_probs,
        save_path='results/fill_probability_curve.png'
    )
    print("   Saved to: results/fill_probability_curve.png")
    
    # Plot cumulative returns comparison
    print("\n6. Plotting backtest comparison...")
    visualizer = Visualizer()
    visualizer.plot_backtest_comparison(
        result.baseline_returns,
        result.strategy_returns,
        save_path='results/backtest_comparison.png'
    )
    print("   Saved to: results/backtest_comparison.png")
    
    # Plot ePDF histograms
    print("\n7. Plotting ePDF histograms...")
    visualizer.plot_epdf_histogram(
        epdfs,
        bins=30,
        save_path='results/epdf_histograms_phase2.png'
    )
    print("   Saved to: results/epdf_histograms_phase2.png")
    
    print("\n" + "="*80)
    print("PHASE 2 COMPLETE!")
    print("="*80)
    print("\nKey Deliverables (PDF Requirements):")
    print("  ✓ ePDF Histograms: results/epdf_histograms_phase2.png")
    print("  ✓ Fill Probability Chart: results/fill_probability_curve.png")
    print("  ✓ Backtest Comparison: results/backtest_comparison.png")
    print("\nMetrics:")
    print(f"  Fill Rate: {result.fill_rate:.2%}")
    print(f"  Avg Savings: {result.avg_savings:.4f} ticks")
    print("="*80)


if __name__ == "__main__":
    main()