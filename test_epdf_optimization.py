"""
Quick test to verify ePDF optimization works correctly
Tests both correctness and performance
"""

import warnings
warnings.filterwarnings('ignore', message='.*delta_grad.*', category=UserWarning)

import pandas as pd
import numpy as np
import time
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer

print("="*60)
print("TESTING EPDF OPTIMIZATION FIX")
print("="*60)

# Load data
print("\n1. Loading data...")
loader = DataLoader()
df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
print(f"   Loaded {len(df)} bars")

# Detect states
print("\n2. Detecting states...")
detector = StateDetector()
df = detector.detect_states(df)

# Test with smaller dataset
test_df = df.iloc[0:500].copy()
print(f"   Testing with first {len(test_df)} bars")

# Initialize optimizer
optimizer = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

print("\n3. Testing correctness of fill probability lookup...")
# Build up some history
for i in range(1, 150):
    prev = test_df.iloc[i-1]
    state = test_df.iloc[i]['prev_state']
    optimizer.epdf.update(
        state,
        prev['range_dn_ticks'],
        prev['close'] - prev['open']
    )

# Test fill probabilities at different levels
state = 'Low'
print(f"   Testing state: {state}")
print(f"   Buffer count: {optimizer.epdf.counts[state]}")

test_levels = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
print(f"\n   Fill probabilities:")
for level in test_levels:
    prob = optimizer.epdf.get_fill_prob(state, level)
    print(f"     Level {level:4.1f}: {prob:.4f}")

# Verify monotonic decreasing (higher level = lower fill prob)
probs = [optimizer.epdf.get_fill_prob(state, l) for l in test_levels]
is_monotonic = all(probs[i] >= probs[i+1] for i in range(len(probs)-1))
print(f"\n   Monotonic decreasing check: {'✓ PASS' if is_monotonic else '✗ FAIL'}")

# Verify probabilities in [0, 1]
in_range = all(0.0 <= p <= 1.0 for p in probs)
print(f"   Range [0,1] check: {'✓ PASS' if in_range else '✗ FAIL'}")

print("\n4. Testing performance...")
# Time 1000 fill probability queries
start_time = time.time()
for _ in range(1000):
    _ = optimizer.epdf.get_fill_prob(state, 1.0)
elapsed = (time.time() - start_time) * 1000
print(f"   1000 fill_prob() calls: {elapsed:.2f}ms ({elapsed/1000:.4f}ms per call)")

# Time 100 optimization calls
print("\n5. Testing optimization performance...")
opt_times = []
for i in range(150, 160):
    start = time.time()
    limits = optimizer.get_limits(test_df, i, tick=0.25)
    opt_time = (time.time() - start) * 1000
    opt_times.append(opt_time)
    print(f"   Bar {i}: {opt_time:.2f}ms, levels={limits}")

avg_opt_time = np.mean(opt_times)
print(f"\n   Average optimization time: {avg_opt_time:.2f}ms")
print(f"   Estimated time per bar: {avg_opt_time:.2f}ms")

# Extrapolate to larger datasets
bars_1000 = avg_opt_time * 1000 / 1000
bars_5000 = avg_opt_time * 5000 / 1000
bars_59000 = avg_opt_time * 59000 / 1000

print(f"\n6. Estimated total execution times:")
print(f"   1,000 bars:  {bars_1000:.1f} seconds ({bars_1000/60:.1f} minutes)")
print(f"   5,000 bars:  {bars_5000:.1f} seconds ({bars_5000/60:.1f} minutes)")
print(f"   59,000 bars: {bars_59000:.1f} seconds ({bars_59000/60:.1f} minutes)")

print("\n" + "="*60)
if avg_opt_time < 100:
    print(f"✓ SUCCESS: Optimization is fast ({avg_opt_time:.2f}ms per bar)")
    print("  Expected: <100ms per bar")
elif avg_opt_time < 500:
    print(f"⚠ WARNING: Optimization is acceptable ({avg_opt_time:.2f}ms per bar)")
    print("  Expected: <100ms per bar, but <500ms is OK")
else:
    print(f"✗ FAILURE: Optimization is too slow ({avg_opt_time:.2f}ms per bar)")
    print("  Expected: <100ms per bar")
print("="*60)