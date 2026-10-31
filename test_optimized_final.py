"""
Test optimized strategy (2-regime, corrected utility)
"""

import pandas as pd
import numpy as np
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer

# Load data
print("Loading data...")
data_loader = DataLoader(tick_size=0.25)
df = data_loader.load_csv("data_export/Nasdaq/NQH20.csv")

# Detect states (2-regime)
print("Detecting states...")
state_detector = StateDetector(thresh=2.5)
df = state_detector.detect_states(df)

# Create strategy
strategy = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

# Test
print("\nTesting optimization...")
start_bar = 150
test_bars = 100

results = []
for i in range(start_bar, start_bar + test_bars):
    row = df.iloc[i]
    state = row['prev_state']
    
    limits = strategy.get_limits(df, i, tick=0.25)
    
    if i % 20 == 0:
        print(f"Bar {i}, State {state}: {limits}")
    
    levels = [l for l, w in limits]
    weights = [w for l, w in limits]
    
    results.append({
        'bar': i,
        'state': state,
        'p1': levels[0], 'p2': levels[1], 'p3': levels[2],
        'w1': weights[0], 'w2': weights[1], 'w3': weights[2]
    })

results_df = pd.DataFrame(results)

# Statistics
print("\n=== Optimization Results ===")
print(f"Total bars: {len(results_df)}")
print(f"\nPrice Levels:")
print(results_df[['p1', 'p2', 'p3']].describe())
print(f"\nWeights:")
print(results_df[['w1', 'w2', 'w3']].describe())

# By state
print("\n=== By State ===")
for state in ['Low', 'High']:
    state_df = results_df[results_df['state'] == state]
    if len(state_df) > 0:
        print(f"\n{state} (n={len(state_df)}):")
        print(f"  Levels: p1={state_df['p1'].mean():.2f}, p2={state_df['p2'].mean():.2f}, p3={state_df['p3'].mean():.2f}")
        print(f"  Weights: w1={state_df['w1'].mean():.2f}, w2={state_df['w2'].mean():.2f}, w3={state_df['w3'].mean():.2f}")

print("\nDone!")