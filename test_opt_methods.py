"""
Test different optimization methods
"""

import pandas as pd
import numpy as np
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import ePDFBuilder
from scipy.optimize import minimize

# Load data
print("Loading data...")
data_loader = DataLoader(tick_size=0.25)
df = data_loader.load_csv("data_export/Nasdaq/NQH20.csv")

# Liquidity filter: high volume and actual price movement
print("Filtering for liquid periods...")
df = df[(df['vol'] > 100) & (df['high'] > df['low'])].copy()
print(f"  Kept {len(df)}/{len(data_loader.load_csv('data_export/Nasdaq/NQH20.csv'))} bars after filtering")

# Detect states
print("Detecting...")
state_detector = StateDetector(thresh=2.5)
df = state_detector.detect_states(df)

# Build ePDF
print("Building...")
epdf = ePDFBuilder(window_size=60)
for i in range(60, min(5000, len(df))):
    row = df.iloc[i]
    prev = df.iloc[i-1]
    movement = prev['close'] - prev['open']
    epdf.update(row['vol_state'], prev['range_dn_ticks'], movement)

# Test state
state = 'Low' if len(epdf.epdfs_range_dn['Low']) > 0 else 'High'
print(f"\nTesting: {state}")

# Get E1: Fill probability distribution (from range_dn)
print(f"\n[1] Fill Probability Estimate:")
print(f"  From: Historical range_dn distribution (open - low)")

# E2: Expected close price (from close - open)
print(f"\n[2] Expected Close Price Estimate:")
open_price = df.iloc[min(5000, len(df)-1)]['open']
tick = 0.25
expected_movement = epdf.get_expected_close(state)  # E(close - open | state)
expected_close = open_price + expected_movement
print(f"  From: Historical (close - open) distribution")
print(f"  At t={min(5000, len(df)-1)}: open={open_price:.2f}")
print(f"  Expected movement: {expected_movement:.2f}")
print(f"  Expected close: {expected_close:.2f}")

# Debug: Show fill probabilities for different levels
print("\nFill probabilities for different levels:")
for level in [0, 0.5, 1, 2, 3, 5, 10]:
    prob = epdf.get_fill_prob(state, level)
    print(f"  Level {level}: {prob:.3f}")

# Objective
def objective(x):
    # Ensure levels are sorted to maintain slicing logic
    levels = sorted(x[:3])
    weights = x[3:]

    expected_savings = 0
    for l, w in zip(levels, weights):
        prob_fill = epdf.get_fill_prob(state, l)

        # Win: Expected ticks saved
        gain = prob_fill * l

        # Savings if miss: Buy at open, price goes to close
        # If close < open: We SAVE by waiting (negative cost = credit)
        savings_if_missed = (open_price - expected_close) / tick

        # Total expected savings: weighted combination
        # GAIN is POSITIVE (savings if filled)
        # savings_if_missed can be NEGATIVE (saved if market moves favorably)
        loss = (1 - prob_fill) * savings_if_missed
        expected_savings += w * (gain - loss)

    return -expected_savings # Maximize savings

# Debug: Check objective value at initial guess
x0 = [0., 1., 2., 1./3., 1./3., 1./3.]
print(f"\nObjective at initial guess: {objective(x0):.6f}")

# Debug: Test putting all weight on level 0
x0_all_level0 = [0., 1., 2., 1., 0., 0.]  # All weight on p1=0
print(f"Objective with all weight on level 0: {objective(x0_all_level0):.6f}")

# Debug: Test all weight on level 5
x0_all_level5 = [5., 6., 7., 0., 1., 0.]  # All weight on p2=6
print(f"Objective with all weight on level 6: {objective(x0_all_level5):.6f}")

# Try methods with different starting points
for initial in [0., 0.5, 1., 2., 5.]:
    x0 = [initial, initial+1., initial+2., 1./3., 1./3., 1./3.]
    bounds = [(0., 10.)]*3 + [(0., 1.)]*3
    cons = {'type': 'eq', 'fun': lambda x: sum(x[3:6]) - 1.}

    print(f"\nInitial: levels ~ {[initial, initial+1., initial+2.]}")
    print(f"  Objective: {objective(x0):.6f}")

    for method in ['SLSQP', 'trust-constr']:
        try:
            print(f"\n{method}:")
            result = minimize(objective, x0, method=method,
                              bounds=bounds, constraints=cons,
                              options={'disp': True})
            print(f"  Success: {result.success}")
            print(f"  Message: {result.message}")
            if result.success:
                p, w = result.x[:3], result.x[3:]
                w = w / w.sum()
                print(f"  Result: {list(zip(p, w))}")
        except Exception as e:
            print(f"  Error: {e}")
print("\nDone!")