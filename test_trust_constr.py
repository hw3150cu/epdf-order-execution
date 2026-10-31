"""
Test trust-constr optimization method
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
expected_movement = epdf.get_expected_close(state)
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
    levels = sorted(x[:3])
    weights = x[3:]
    
    expected_savings = 0
    for l, w in zip(levels, weights):
        prob_fill = epdf.get_fill_prob(state, l)
        gain = prob_fill * l
        savings_if_missed = (open_price - expected_close) / tick
        loss = (1 - prob_fill) * savings_if_missed
        expected_savings += w * (gain - loss)
    
    return -expected_savings

# NOTE: SLSQP is skipped due to getting stuck at local minima
# BACKLOG: Debug SLSQP - investigate why it always returns initial guess
# Using trust-constr only for now

print("\n" + "="*60)
print("OPTIMIZATION RESULTS (trust-constr method):")
print("="*60)

best_result = None
best_objective = float('-inf')

for initial in [0., 0.5, 1., 2., 5.]:
    x0 = [initial, initial+1., initial+2., 1./3., 1./3., 1./3.]
    bounds = [(0., 10.)]*3 + [(0., 1.)]*3
    cons = {'type': 'eq', 'fun': lambda x: sum(x[3:6]) - 1.}

    print(f"\nInitial: {[initial, initial+1., initial+2.]}")
    print(f"  Objective: {objective(x0):.6f}")

    try:
        result = minimize(objective, x0, method='trust-constr',
                          bounds=bounds, constraints=cons,
                          options={'disp': False})
        
        if result.success:
            p = result.x[:3]
            w = result.x[3:]
            w = w / w.sum()
            final_obj = -result.fun
            print(f"  → {list(zip(p, w))} (obj={final_obj:.6f})")
            
            if final_obj > best_objective:
                best_objective = final_obj
                best_result = (p, w)
        else:
            print(f"  → Failed: {result.message}")
    except Exception as e:
        print(f"  → Error: {e}")

print("\n" + "="*60)
print(f"BEST RESULT: {best_result} (objective={best_objective:.6f})")
print("="*60)