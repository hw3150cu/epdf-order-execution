"""Test multi-start SLSQP implementation"""

import warnings
warnings.filterwarnings('ignore', message='.*delta_grad.*', category=UserWarning)

import pandas as pd
import numpy as np
import time
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer

print("="*70)
print("MULTI-START SLSQP TEST")
print("="*70)

# Load data
print("\n1. Loading data...")
loader = DataLoader()
df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
df = df[(df['vol'] > 100)].iloc[:500].copy()

detector = StateDetector()
df = detector.detect_states(df)

print(f"   Testing with {len(df)} bars")

# Initialize optimizer
print("\n2. Initializing optimizer...")
optimizer = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

# Test on 50 bars
print("\n3. Testing on 50 bars...")
print("-"*70)

results = []
times = []
success_count = 0
fallback_count = 0

for i in range(150, 200):
    start = time.time()
    limits = optimizer.get_limits(df, i, 0.25)
    elapsed = (time.time() - start) * 1000
    times.append(elapsed)
    results.append(limits)
    
    # Check if it's the default fallback
    levels = [round(l[0], 2) for l in limits]
    weights = [round(l[1], 2) for l in limits]
    
    if levels == [0.0, 1.0, 2.0] and weights == [0.33, 0.33, 0.33]:
        fallback_count += 1
        print(f"Bar {i}: {elapsed:6.1f}ms -> FALLBACK (default)")
    else:
        success_count += 1
        print(f"Bar {i}: {elapsed:6.1f}ms -> levels={levels}, weights={weights}")

# Summary statistics
print("\n" + "="*70)
print("SUMMARY STATISTICS")
print("="*70)

avg_time = np.mean(times)
median_time = np.median(times)
min_time = np.min(times)
max_time = np.max(times)

print(f"\nTiming:")
print(f"  Average: {avg_time:.2f}ms per bar")
print(f"  Median:  {median_time:.2f}ms per bar")
print(f"  Min:     {min_time:.2f}ms per bar")
print(f"  Max:     {max_time:.2f}ms per bar")

print(f"\nSuccess rate:")
print(f"  Optimized (non-default): {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
print(f"  Fallback (default):      {fallback_count}/{len(results)} ({fallback_count/len(results)*100:.1f}%)")

print(f"\nExtrapolated to 59,000 bars:")
print(f"  Average time: {avg_time/1000*59000/60:.1f} minutes")
print(f"  Median time:  {median_time/1000*59000/60:.1f} minutes")

# Analyze results
print(f"\nResult analysis:")
all_levels = [[round(l[0], 2) for l in r] for r in results]
avg_levels = np.mean(all_levels, axis=0)
print(f"  Average levels: {avg_levels}")

all_weights = [[round(l[1], 2) for l in r] for r in results]
avg_weights = np.mean(all_weights, axis=0)
print(f"  Average weights: {avg_weights}")

# Check variety
unique_levels = set(tuple(round(l[0], 1) for l in r) for r in results if r[0][0] != 0.0)
print(f"  Unique level combinations: {len(unique_levels)}")

print("\n" + "="*70)
if avg_time < 100:
    print("✓ EXCELLENT: Multi-start SLSQP is fast (<100ms per bar)")
    print(f"  Expected time for 59k bars: {avg_time/1000*59000/60:.1f} minutes")
elif avg_time < 200:
    print("✓ GOOD: Multi-start SLSQP is acceptable (<200ms per bar)")
    print(f"  Expected time for 59k bars: {avg_time/1000*59000/60:.1f} minutes")
else:
    print("⚠ WARNING: Multi-start SLSQP is slow (>200ms per bar)")
    print(f"  Expected time for 59k bars: {avg_time/1000*59000/60:.1f} minutes")

if success_count/len(results) > 0.8:
    print("✓ GOOD: Optimization succeeds most of the time")
elif success_count/len(results) > 0.5:
    print("⚠ WARNING: Optimization fails frequently")
else:
    print("✗ BAD: Optimization rarely succeeds")
print("="*70)