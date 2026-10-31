"""
Debug and fix SLSQP optimization to match trust-constr results
"""

import warnings
warnings.filterwarnings('ignore', message='.*delta_grad.*')

import pandas as pd
import numpy as np
import time
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import UtilityOptimizer
from scipy.optimize import minimize

print("="*70)
print("SLSQP DEBUG - Comparing SLSQP vs trust-constr")
print("="*70)

# Load data
print("\n1. Loading data...")
loader = DataLoader()
df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
df = df[(df['vol'] > 100)].iloc[:300].copy()
print(f"   Loaded {len(df)} bars")

# Detect states
print("\n2. Detecting states...")
detector = StateDetector()
df = detector.detect_states(df)

# Initialize optimizer
optimizer = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

# Build history
for i in range(1, 150):
    prev = df.iloc[i-1]
    state = df.iloc[i]['prev_state']
    optimizer.epdf.update(
        state,
        prev['range_dn_ticks'],
        prev['close'] - prev['open']
    )

# Test at bar 150
test_bar = 150
row = df.iloc[test_bar]
prev = df.iloc[test_bar-1]
state = row['prev_state']
tick = 0.25

print(f"\n3. Testing optimization at bar {test_bar}")
print(f"   State: {state}")
print(f"   Open: {row['open']:.2f}, Close: {row['close']:.2f}")

# Get penalty
expected_close = optimizer.epdf.get_expected_close(state)
penalty = max(optimizer.min_penalty, (expected_close - row['open']) / tick)
print(f"   Penalty: {penalty:.4f}")

# Define objective function
def objective(x):
    """Objective function for optimization"""
    p1, p2, p3, w1, w2, w3 = x
    levels = [p1, p2, p3]
    weights = [w1, w2, w3]
    
    # Fill probs
    probs = [optimizer.epdf.get_fill_prob(state, l) for l in levels]
    
    # Utility
    fill_prob = sum(w*pr for w, pr in zip(weights, probs))
    reward = sum(w*pr*l for w, pr, l in zip(weights, probs, levels))
    miss_penalty = (1. - fill_prob) * penalty
    return -(reward - miss_penalty)

# Setup constraints
bounds = [(0., optimizer.max_level)]*3 + [(0., 1.)]*3
cons = {'type': 'eq', 'fun': lambda x: sum(x[3:6]) - 1.}
x0 = [0., 1., 2., 1./3., 1./3., 1./3.]

print(f"\n4. Testing trust-constr (baseline)...")
start = time.time()
result_tc = minimize(
    objective, x0,
    method='trust-constr',
    bounds=bounds,
    constraints=cons,
    options={'disp': False}
)
time_tc = (time.time() - start) * 1000

print(f"   Success: {result_tc.success}")
print(f"   Time: {time_tc:.2f}ms")
print(f"   Objective: {result_tc.fun:.6f}")
print(f"   Levels: {result_tc.x[:3]}")
print(f"   Weights: {result_tc.x[3:6]}")

print(f"\n5. Testing SLSQP (different configurations)...")

# Test 1: Basic SLSQP
print("\n   Test 5.1: Basic SLSQP")
try:
    result_sl = minimize(
        objective, x0,
        method='SLSQP',
        bounds=bounds,
        constraints=cons,
        options={'disp': False}
    )
    print(f"     Success: {result_sl.success}")
    print(f"     Message: {result_sl.message}")
    print(f"     Objective: {result_sl.fun:.6f}")
    print(f"     Levels: {result_sl.x[:3]}")
    print(f"     Weights: {result_sl.x[3:6]}")
except Exception as e:
    print(f"     Error: {e}")

# Test 2: SLSQP with relaxed tolerance
print("\n   Test 5.2: SLSQP with relaxed tolerance (ftol=1e-6)")
try:
    result_sl2 = minimize(
        objective, x0,
        method='SLSQP',
        bounds=bounds,
        constraints=cons,
        options={'disp': False, 'ftol': 1e-6, 'eps': 1e-8}
    )
    print(f"     Success: {result_sl2.success}")
    print(f"     Message: {result_sl2.message}")
    print(f"     Objective: {result_sl2.fun:.6f}")
    print(f"     Levels: {result_sl2.x[:3]}")
    print(f"     Weights: {result_sl2.x[3:6]}")
except Exception as e:
    print(f"     Error: {e}")

# Test 3: SLSQP with maxiter
print("\n   Test 5.3: SLSQP with maxiter=500")
try:
    result_sl3 = minimize(
        objective, x0,
        method='SLSQP',
        bounds=bounds,
        constraints=cons,
        options={'disp': False, 'maxiter': 500, 'ftol': 1e-8}
    )
    print(f"     Success: {result_sl3.success}")
    print(f"     Message: {result_sl3.message}")
    print(f"     Objective: {result_sl3.fun:.6f}")
    print(f"     Levels: {result_sl3.x[:3]}")
    print(f"     Weights: {result_sl3.x[:3]}")
except Exception as e:
    print(f"     Error: {e}")

print("\n" + "="*70)
print("SUMMARY:")
print("="*70)
print(f"trust-constr: {'✓ Works' if result_tc.success else '✗ Failed'} (time={time_tc:.2f}ms)")
print("="*70)