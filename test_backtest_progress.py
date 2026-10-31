"""Quick test to verify backtest progress is visible"""

import warnings
warnings.filterwarnings('ignore', message='.*delta_grad.*', category=UserWarning)

from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer
import sys

print("=" * 60)
print("QUICK BACKTEST TEST (1000 bars)")
print("=" * 60)

# Load data
print("\nLoading data...")
loader = DataLoader(tick_size=0.25)
df = loader.load_csv("data_export/Nasdaq/NQH20.csv")
df = df[(df['vol'] > 100)].copy()
print(f"Loaded {len(df)} bars")

# Test with only first 2000 bars
df = df.iloc[:2000].copy()
print(f"Testing with first {len(df)} bars")

# Detect states
print("\nDetecting states...")
detector = StateDetector(thresh=2.5)
df = detector.detect_states(df)

# Run backtest
print("\nRunning backtest...")
print("-" * 60)

optimizer = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

warmup = 100
total = len(df) - warmup

for i in range(warmup, len(df)):
    # Simple progress every 100 bars
    if (i - warmup) % 100 == 0:
        progress = (i - warmup) / total * 100
        print(f"\rProgress: {progress:.1f}% ({i-warmup}/{total} bars)", end='', flush=True)

    # Get optimized limits
    limits = optimizer.get_limits(df, i, tick=0.25)

    # Calculate savings
    row = df.iloc[i]
    gap = row['open'] - row['low']
    bar_save = 0.0

    for level, weight in limits:
        if gap >= level:
            bar_save += weight * level

print(f"\n\n✓ Completed!")
print("-" * 60)
print("\nQuick test PASSED!")
print("Progress output is working correctly.")
print()