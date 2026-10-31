"""Test Corrected Methodology - Uses open[t] as reference"""
import matplotlib.pyplot as plt
import numpy as np
import os
from data_loader import DataLoader
from state_detection import StateDetector
from backtest_engine_corrected import BacktestEngine
from strategies_utility_clean import UtilityOptimizerStrategy

loader = DataLoader(tick_size=0.25)
df = loader.load_csv("os.path.join(os.environ.get("ORDER_DATA_ROOT", "data_export"), "Nasdaq", "NQH20.csv")")

print("Loaded", len(df), "bars")

# Detect states
detector = StateDetector(m=20, low_thresh=1.5, high_thresh=3.0)
df = detector.detect_states(df)
counts = df['prev_state'].value_counts()
print("Regimes:", {s: counts.get(s, 0) for s in ['Low', 'Med', 'High']})

# Run backtest with corrected engine
strategy = UtilityOptimizerStrategy(window_size=60, penalty_ticks=10.0, price_levels=[0.0, 1.0, 2.0])
engine = BacktestEngine(tick_size=0.25, warmup_bars=50)
result = engine.backtest(df, strategy)

print(f"Fill Rate: {result.fill_rate:.2%}")
print(f"Avg Savings: {result.avg_savings:.4f} ticks (${result.avg_savings * 0.25:.2f})")
print(f"Total Savings: {result.total_savings:.0f}ticks (${result.total_savings * 0.25:.2f})")

# Plot cumulative returns
fig, ax = plt.subplots(figsize=(10, 6))
cum_strategy = np.cumsum(result.strategy_returns)
cum_baseline = np.cumsum([r['open'] - r['close'] for r in df[50:].to_dict('records')])
ax.plot(cum_baseline, label='Baseline (Market Order)', color='gray', alpha=0.7)
ax.plot(cum_strategy, label='Utility Optimizer (Corrected)', color='blue', alpha=0.7)
ax.set_xlabel('Bar Index')
ax.set_ylabel('Cumulative Returns (ticks)')
ax.set_title('Backtest Results - Reference: open[t] (CORRECTED)')
ax.legend()
ax.grid(True, alpha=0.3)
os.makedirs('results', exist_ok=True)
fig.savefig('results/corrected_final.png', dpi=300)
plt.close(fig)
print("Saved: results/corrected_final.png")