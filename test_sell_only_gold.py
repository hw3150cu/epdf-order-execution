"""
Test sell-only optimization on Gold GCM24.
"""

from data_matcher import DataMatcher
from strategies_optimized_final import UtilityOptimizer
from state_detection import StateDetector
from tqdm import tqdm
import pandas as pd
import numpy as np

# Gold tick size is 0.10
tick_size = 0.10

print('='*70)
print('SELL-ONLY TEST: GOLD GCM24')
print('='*70)

matcher = DataMatcher('data_export/Gold/AIAgent_Gold.csv', 'data_export/Gold')
matched_df = matcher.match_data('GCM24')

if matched_df is None:
    print('Failed to match data')
    exit()

validated_df = matched_df[(matched_df['status'] == 'valid') & (matched_df['vol'] > 0)].copy()
print(f'Validated matches: {len(matched_df[matched_df["status"] == "valid"])}')
print(f'Actual trades:     {len(validated_df)}')

# Agent baseline
validated_df['agent_savings_ticks'] = (validated_df['price'] - validated_df['open']) / tick_size
sell_mask = validated_df['price'] > validated_df['open']
agent_sell_savings = validated_df.loc[sell_mask, 'agent_savings_ticks'].sum()
print(f'Agent sell:       {agent_sell_savings:.1f} ticks')

# Filter to sell only
sell_only_df = validated_df[sell_mask].copy()
print(f'Sell trades:      {len(sell_only_df)}')

# Add columns
sell_only_df['range_dn_ticks'] = (sell_only_df['open'] - sell_only_df['low']) / tick_size
sell_only_df['range_up_ticks'] = (sell_only_df['high'] - sell_only_df['open']) / tick_size

# Detect states
detector = StateDetector(m=60, thresh=2.5)
sell_only_df = detector.detect_states(sell_only_df)

# Optimize
optimizer = UtilityOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)
warmup = 60
total_trades = len(sell_only_df) - warmup

optimized_savings = np.zeros(total_trades)
open_arr = sell_only_df['open'].values
high_arr = sell_only_df['high'].values

for i in tqdm(range(warmup, len(sell_only_df)), desc='Optimizing'):
    limits = optimizer.get_limits(sell_only_df, i, tick_size, direction='sell')

    sell_gap_dollars = high_arr[i] - open_arr[i]
    sell_gap_ticks = sell_gap_dollars / tick_size

    sell_save = 0.0
    for level, weight in limits:
        if sell_gap_ticks >= level:
            sell_save += weight * level

    optimized_savings[i - warmup] = sell_save

optimized_total = optimized_savings.sum()
improvement = optimized_total - agent_sell_savings
improvement_pct = (improvement / agent_sell_savings * 100) if agent_sell_savings > 0 else 0

print()
print('='*70)
print('RESULTS (SELL ONLY)')
print('='*70)
print(f'Agent sell:      {agent_sell_savings:.1f} ticks')
print(f'Optimized sell:  {optimized_total:.1f} ticks')
print(f'Improvement:     {improvement:+.1f} ticks ({improvement_pct:+.1f}%)')
print('='*70)