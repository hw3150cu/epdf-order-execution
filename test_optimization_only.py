"""Test just the optimization function to isolate bottleneck"""

import warnings
warnings.filterwarnings('ignore', message='.*delta_grad.*')

from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer
import time

print("Testing optimization function in isolation...")
print("="*60)

# Load data
loader = DataLoader()
df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
df = df[(df['vol'] > 100)].iloc[:300].copy()

detector = StateDetector()
df = detector.detect_states(df)

optimizer = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

# Test 20 optimization calls
print("\nTesting 20 consecutive optimizations:")
print("-"*60)

times = []
for i in range(150, 170):
    start = time.time()
    limits = optimizer.get_limits(df, i, 0.25)
    elapsed = (time.time() - start) * 1000
    times.append(elapsed)
    print(f"Bar {i}: {elapsed:6.2f}ms  -> {limits}")

avg_time = sum(times) / len(times)
total_bars = 59000
estimated_minutes = (avg_time / 1000) * total_bars / 60

print("-"*60)
print(f"\nResults:")
print(f"  Average optimization time: {avg_time:.2f}ms")
print(f"  Estimated time for {total_bars} bars: {estimated_minutes:.1f} minutes ({estimated_minutes/60:.2f} hours)")

print("\n" + "="*60)
if avg_time < 50:
    print("✓ GOOD: Optimization is fast enough")
elif avg_time < 100:
    print("⚠ ACCEPTABLE: Optimization is reasonable")
else:
    print("✗ SLOW: Optimization is the main bottleneck!")
    print("   Consider:")
    print("   1. Caching optimization results")
    print("   2. Using discrete grid search instead")
    print("   3. Pre-computing lookup table")
print("="*60)