import pandas as pd
import numpy as np
from tqdm import tqdm
from collections import deque

# 1. SETUP: Load/Create Sample Data
# Format: timestamp, open, high, low, close, volume
df = pd.read_csv('data_export/Nasdaq/NQH20.csv', header=None) 
df.columns=['ts', 'open', 'high', 'low', 'close', 'vol']
df['range_dn_ticks'] = (df['open'] - df['low']) / 0.25  # Convert to Ticks (0.25 spread)

# 2. ALGORITHM 1: Recursive EWMA/EWMV (State Detection)
m = 20  # Half-life
lam = 1 - (2 / (m + 1))

sumW, sumWX, sumWSS = 0, 0, 0
states = []

print("Step 2: Calculating EWMA/EWMV and volatility states...")
for i in tqdm(range(len(df)), desc="Processing bars", unit="bar"):
    val = df['range_dn_ticks'].iloc[i]
    
    if i == 0:
        ewma, ewmv = val, 0
        sumW, sumWX, sumWSS = 1, val, 0
    else:
        # Recursive update
        sumW = lam * sumW + 1
        sumWX = lam * sumWX + val
        ewma = sumWX / sumW
        sumWSS = lam * sumWSS + (val - ewma)**2
        ewmv = np.sqrt(sumWSS / sumW)
    
    # Define "State" based on Volatility (Standard Deviations)
    # We use the previous minute's volatility to define the "Current State"
    state = "Low" if ewmv < 1.5 else "High" if ewmv > 3.0 else "Med"
    states.append(state)

df['vol_state'] = states
df['prev_state'] = df['vol_state'].shift(1) # Crucial: use lagged state to avoid look-ahead

# 3. ePDF CONSTRUCTION (Mining Historical Data)
# Using deque with maxlen=60 for O(1) push/pop operations
WINDOW_SIZE = 60
epdfs = {
    "Low": deque(maxlen=WINDOW_SIZE),
    "Med": deque(maxlen=WINDOW_SIZE),
    "High": deque(maxlen=WINDOW_SIZE)
}

print(f"Using fixed-size deques (maxlen={WINDOW_SIZE}) for O(1) operations")

# 4. BACKTEST SIMULATION (The Slicing & Execution Engine)
total_savings = 0
results = []

print("\nStep 4: Running backtest simulation...")
for i in tqdm(range(50, len(df)), desc="Backtesting", unit="trade"): # Start after 50 bars to "warm up" history
    row = df.iloc[i]
    prev_state = row['prev_state']
    
    # A. Update the ePDF with the bar that JUST finished
    finished_bar = df.iloc[i-1]
    epdfs[finished_bar['vol_state']].append(finished_bar['range_dn_ticks'])
    
    # B. Decision: If we have enough history, place a limit order
    if len(epdfs[prev_state]) > 10:
        # RULE-BASED SLICING: 
        # Slice 1: 50% at the Median (Safe)
        # Slice 2: 50% at the 80th Percentile (Greedy/Magic Spread)
        p50 = np.percentile(epdfs[prev_state], 50)
        p80 = np.percentile(epdfs[prev_state], 80)
        limit_price_ticks = (p50 + p80) / 2 # Simple average of slices for this example
        
        limit_price = row['open'] - (limit_price_ticks * 0.25)
        
        # C. Verification (Fill Logic)
        if row['low'] <= limit_price:
            # FILLED! Savings = Open - Limit
            exec_price = limit_price
            outcome = "Filled"
        else:
            # MISSED! Must buy at Close. Slippage = Open - Close
            exec_price = row['close']
            outcome = "MarketOrder_At_Close"
            
        savings = row['open'] - exec_price
        total_savings += savings
        results.append(savings)

print(f"Backtest Complete.")
print(f"Average Slippage Savings per trade: {np.mean(results):.4f} points")
print(f"Total Points Saved: {total_savings:.2f}")