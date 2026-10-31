"""ROLLING Backtest - Improved: Integer constraints, timestamp mapping, attribution"""
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import ePDFBuilder
from scipy.optimize import minimize
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import os

# Load data
loader = DataLoader(tick_size=0.25)
df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
df = df[(df['vol'] > 100)].copy()

print(f"Loaded {len(df)} bars (vol > 100)")
print(f"Timestamp range: {df['ts'].iloc[0]} to {df['ts'].iloc[-1]}")

# Detect states
detector = StateDetector(thresh=2.5)
df = detector.detect_states(df)

class OptimizedOptimizer:
    """Optimizer with integer constraints (levels) and 0.1 (weights)"""
    
    def __init__(self, window_size=60, min_penalty=5.0, max_level_ticks=20.0):
        self.window_size = window_size
        self.min_penalty = min_penalty
        self.max_level_ticks = max_level_ticks
        self.epdf = ePDFBuilder(window_size)
    
    def get_limits(self, df, i, tick_size):
        """Get (level_ticks, weight) with constraints:
           - levels: integers (0, 1, 2, ... , 20)
Weights: sum to 1, multiples of 0.1
        """
        if i < 1:
            return [(0., 0.33), (1., 0.33), (2., 0.34)]
        
        row = df.iloc[i]
        state = row['prev_state']
        
        # Update ePDF
        prev = df.iloc[i-1]
        self.epdf.update(state, prev['range_dn_ticks'], prev['close'] - prev['open'])
        
        # Need history
        if len(self.epdf.epdfs_range_dn[state]) < 10:
            return [(0., 0.33), (1., 0.33), (2., 0.34)]
        
        # Calculate penalty
        expected_movement = self.epdf.get_expected_close(state)
        penalty = max(self.min_penalty, (expected_movement - row['open']) / tick_size)
        
        def objective(x):
            p1, p2, p3, w1, w2, w3 = x
            fiberglass = [p1, p2, p3]
            weights = [w1, w2, w3]
            
            # Fill probs
            probs = [self.epdf.get_fill_prob(state, l) for l in levels]
            
            # Utility
            fill_prob = sum(w*pr for w, pr in zip(weights, probs))
            reward = sum(w*pr*l for w, pr, l in zip(weights, probs, levels))
            miss_penalty = (1. - fill_prob) * penalty
            return -(reward - miss_penalty)
        
        # Optimization constraints:
        # - levels: integers from 0 to 20
        # - weights: sum to 1, multiples of 0.1
        max_int = int(self.max_level_ticks)
        
        # Try multiple integer combinations
        best = None
        best_obj = float('inf')
        
        for _ in range(50):  # Try 50 random starts
            # Generate integer levels
            levels = np.random.randint(0, max_int + 1, 3)
            levels.sort()
            
            # Generate weights (0.1 multiples)
            w = np.random.rand(3)
            w = np.round(w, 1)
            if w.sum() > 0:
                w = w / w.sum()
            
            # Evaluate
            x = np.concatenate([levels.astype(float), w])
            obj = objective(x)
            
            # Optimize
            # Discrete optimization: try nearby integer points
            for offset in [-1, 0, 1]:
                x_candidate = x.copy()
                for j in [0, 1, 2]:
                    x_candidate[j] = max(0., min(x_candidate[j] + offset, float(max_int)))
                x_candidate[0], x_candidate[1], x_candidate[2] = x_candidate[0], x_candidate[1], x_candidate[2]
                
                obj_cand = objective(x_candidate)
                if obj_cand < best_obj:
                    best_obj = obj_cand
                    best = x_candidate.copy()
        
        if best is None:
            return [(0., 0.33), (1., 0.33), (2., 0.34)]
        
        # Round weights to 0.1
        best[3:6] = np.round(best[3:6], 1)
        best[3:6] = best[3:6] / best[3:6].sum()
        
        # Convert levels to integers
        levels_int = [int(x) for x in best[:3]]
        weights = best[3:6]
        
        return [(float(levels_int[0]), weights[0]), (float(levels_int[1]), weights[1]), (float(levels_int[2]), weights[2])]

# Run backtest
optimizer = OptimizedOptimizer(window_size=60, min_penalty=5.0, max_level_ticks=20.)

save = 0.0
fill = 0
warmup = 1000
total = len(df) - warmup

# Track history
params_history = []
savings_history = []
fill_history = []
execution_score_history = []
baseline_pnl_history = []
optimized_pnl_history = []

# Trade records
trade_records = []

for i in tqdm(range(warmup, len(df)), desc="Rolling backtest", unit="bar"):
    # Get optimized params
    limits = optimizer.get_limits(df, i, 0.25)
    
    # Track params
    if i % 5000 == 0:
        params_history.append((i, limits))
    
    # Execute
    row = df.iloc[i]
    original_ts = row['ts']
    gap = row['open'] - row['low']
    bar_save = 0.0
    
    for level, weight in limits:
        if gap >= level:
            bar_save += weight * level
    
    save += bar_save
    if bar_save > 0:
        fill += 1
    
    # Calculate metrics
    baseline_pnl = row['close'] - row['open']
    baseline_pnl_ticks = baseline_pnl / 0.25
    
    # Execution score: optimized / baseline
    if bar_save > 0 and abs(baseline_pnl) > 0:
        execution_score = 1.0 + (bar_save * 0.25) / abs(baseline_pnl)
    else:
        execution_score = 0.0
    
    # Optimized realized
    optimized_pnl = baseline_pnl + bar_save * 0.25
    
    # Track
    savings_history.append(bar_save)
    fill_history.append(1 if bar_save > 0 else 0)
    execution_score_history.append(execution_score)
    baseline_pnl_history.append(baseline_pnl_ticks)
    optimized_pnl_history.append(optimized_pnl / 0.25)
    
    # Record
    record = {
        'bar_index': i,
        'timestamp': original_ts,
        'open': row['open'],
        'high': row['high'],
        'low': row['low'],
        'close': row['close'],
        'vol': row['eba'],
        'state': row['prev_state'],
        'gap_ticks': gap,
        'optimized_savings_ticks': bar_save,
        'optimized_savings_dollars': bar_save * 12.5,
        'baseline_pnl_ticks': baseline_pnl_ticks,
        'baseline_pnl_dollars': baseline_pnl * 12.5,
        'optimized_pnl_ticks': optimized_pnl / 0.25,
        'optimized_pnl_dollars': optimized_pnl * 12.5,
        'execution_score': execution_score,
    }
    
    # Add columns
    for idx, (level, weight) in enumerate(limits, 1):
        record[f'level_{idx}'] = int(level)
        record[f'weight_{idx}'] = np.round(weight, 1)
    
    trade_records.append(record)

# Results
tick_value = 12.5
savings_dollars = save * tick_value

print("\n" + "="*60)
print("ROLLING BACKTEST RESULTS (Improved)")
print("="*60)
print(f"Total Trades: {total}")
print(f"Fills: {fill} ({fill/total*100:.1f}%)")
print(f"Total Savings: {save_correct:.1f} (${savings_dollars:,.2f})")
print(f"Avg Savings: {save/total:.2f} ticks/trade (${save/total*tick_value:.2f})")
print(f"Tick Value: ${tick_value}")

# Attribution
avg_score = np.mean([s for s in execution_score_history if s > 0])
print(f"\n" + "="*60)
print("ATTRIBUTION")
print("="*60)
print(f"Avg Execution Score: {avg_score:.4f} (score > 1 = improvement)")

print(f"\n📊 PARAMETER EVOLUTION:")
for t, limits in params_history:
    print(f"  Bar {t}: {[(int(l), round(w, 1)) for l,w in limits]}")

# Export
trades_df = pd.DataFrame(trade_records)
trades_df.to_csv('results/trade_records_improved_v2.csv', index=False)

# Plot
os.makedirs('results', exist_ok=True)

# Plot: Execution Score
fig1, ax1 = plt.subplots(figsize=(10, 6))
ax1.plot(execution_score_history, label='Execution Score', color='blue', alpha=0.5)
ax1.axhline(1.0, color='green', linestyle='--', linewidth=2, label='Break-even')
ax1.set_xlabel('Bar')
ax1.set_ylabel('Execution Score (>1 = improvement)')
ax1.set_title('Execution Score Over Time')
ax1.legend()
ax1.grid(True)
fig1.savefig('results/improved_execution_score.png', dpi=300)
plt.close(fig1)

# Scatter: Savings colored by score
fig2, ax2 = plt.subplots(figsize=(10, 6))
for i in range(0, len(savings_history), 100):
    if savings_history[i] > 0:
        ax2.scatter(i, savings_history[i], 
                   c=[execution_score_history[i]], 
                   cmap='RdYl sealing', s=20, alpha=0.6)
ax2.set_xlabel('Bar')
ax2.set_ylabel('Savings (ticks)')
ax2.set_title('Saved Ticks (color=score)')
fig2.savefig('results/improved_savings_scatter.png', dpi=300)
plt.close(fig2)

# Bin: Savings
fig3, ax3 = plt.subplots(figsize=(10, 6))
ax3.hist([s for s in savings_history if s > 0], bins=50, edgecolor='black', alpha=0.7)
ax3.axvline(save/total, color='red', linestyle='--')
ax3.set_xlabel('Savings (ticks)')
ax3.set_ylabel('Frequency')
ax3.set_title('Savings Distribution')
fig3.savefig('results/improved_savings_hist.png', dpi=300)
plt.close(fig3)

# Cumulative
fig4, ax4 = plt.subplots(figsize=(10, 6))
cum_baseline = np.cumsum(baseline_pnl_history)
cum_optimized = np.cumsum(optimized_pnl_history)
ax4.plot(cum_baseline, label='Baseline', color='gray')
ax4.plot(cum_optimized, label='Optimized', color='blue')
ax4.set_xlabel('Bar')
ax4.set_ylabel('Cumulative Ticks')
ax4.set_title('Cumulative Return')
ax4.legend()
ax4.grid(True)
fig4.savefig('results/improved_cumulative.png', dpi=300)
plt.close(fig4)

print(f"\n💾 Saved to results/")
print(f"  - trade_records_improved_v2.csv ({len(trades_df)} trades)")
print(f"  - improved_*.png (4 plots)")
print("="*60)