"""
Test optimized strategy with scipy.optimize
"""

import pandas as pd
import numpy as np
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized import UtilityOptimizerStrategy
import matplotlib.pyplot as plt

# Load data
print("Loading data...")
data_loader = DataLoader(tick_size=0.25)
df = data_loader.load_csv("data_export/Nasdaq/NQH20.csv")

# Detect states
print("Detecting states...")
state_detector = StateDetector()
df = state_detector.detect_states(df)

# Create strategy
strategy = UtilityOptimizerStrategy(
    window_size=60,
    min_penalty_ticks=5.0,
    max_price_level=10.0
)

# Test optimization on a subset
print("\nTesting optimization...")
start_bar = 150  # Need to accumulate enough history
test_bars = min(100, len(df) - start_bar)

results = []

for i in range(start_bar, start_bar + test_bars):
    row = df.iloc[i]
    prev_state = row['prev_state']
    
    limit_orders = strategy.get_limit_prices(df, i, tick_size=0.25)
    
    if i % 20 == 0:
        print(f"Bar {i}, State {prev_state}: {limit_orders}")
    
    # Extract levels and weights
    levels = [level for level, weight in limit_orders]
    weights = [weight for level, weight in limit_orders]
    
    results.append({
        'bar': i,
        'state': prev_state,
        'p1': levels[0],
        'p2': levels[1],
        'p3': levels[2],
        'w1': weights[0],
        'w2': weights[1],
        'w3': weights[2]
    })

results_df = pd.DataFrame(results)

# Print statistics
print("\n=== Optimization Results ===")
print(f"Total bars tested: {len(results_df)}")
print(f"\nPrice Levels (p1, p2, p3):")
print(results_df[['p1', 'p2', 'p3']].describe())
print(f"\nWeights (w1, w2, w3):")
print(results_df[['w1', 'w2', 'w3']].describe())

# By state
print("\n=== By State ===")
for state in ['Low', 'High']:
    state_df = results_df[results_df['state'] == state]
    
    if len(state_df) > 0:
        print(f"\n{state} (n={len(state_df)}):")
        print(f"  Avg Levels: p1={state_df['p1'].mean():.2f}, p2={state_df['p2'].mean():.2f}, p3={state_df['p3'].mean():.2f}")
        print(f"  Avg Weights: w1={state_df['w1'].mean():.2f}, w2={state_df['w2'].mean():.2f}, w3={state_df['w3'].mean():.2f}")

print("\nDone!")