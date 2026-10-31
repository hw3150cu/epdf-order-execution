"""
Test sell-only optimization to isolate sell order performance.
"""

import pandas as pd
import numpy as np
from tqdm import tqdm
import os
from datetime import datetime

from data_matcher import DataMatcher
from strategies_optimized_final import UtilityOptimizer
from state_detection import StateDetector


def test_sell_only(agent_file, contract_name,
                   window_size=60, min_penalty=5.0,
                   max_level=10.0, tick_size=0.25):
    """
    Test optimized strategy on sell orders only.
    
    Args:
        agent_file: Path to agent data file
        contract_name: Contract to test
        window_size: ePDF window size
        min_penalty: Minimum penalty
        max_level: Maximum level
        tick_size: Contract tick size
    
    Returns:
        Results dict with sell-only metrics
    """
    print("="*70)
    print("SELL-ONLY OPTIMIZATION TEST")
    print("="*70)

    # Step 1: Load matched validated data
    print("\n1. Loading validated data...")
    matcher = DataMatcher(agent_file, 'data_export')
    matched_df = matcher.match_data(contract_name)

    if matched_df is None:
        raise ValueError(f"Failed to match data for {contract_name}")

    # Filter to validated (price within OHLC) AND actual trades (vol > 0)
    validated_df = matched_df[(matched_df['status'] == 'valid') & (matched_df['vol'] > 0)].copy()
    print(f"   Validated price matches: {len(matched_df[matched_df['status'] == 'valid'])}")
    print(f"   Actual trades (vol > 0): {len(validated_df)}")

    # Step 2: Calculate baseline (agent performance)
    print("\n2. Calculating baseline (agent execution)...")
    validated_df['agent_savings'] = validated_df['open'] - validated_df['price']
    validated_df['agent_savings_ticks'] = validated_df['agent_savings'] / tick_size

    # Calculate agent buy and sell savings separately
    validated_df['agent_buy_savings_ticks'] = 0.0
    validated_df['agent_sell_savings_ticks'] = 0.0

    buy_mask = validated_df['price'] <= validated_df['open']
    validated_df.loc[buy_mask, 'agent_buy_savings_ticks'] = (
        validated_df.loc[buy_mask, 'open'] - validated_df.loc[buy_mask, 'price']
    ) / tick_size

    sell_mask = validated_df['price'] > validated_df['open']
    validated_df.loc[sell_mask, 'agent_sell_savings_ticks'] = (
        validated_df.loc[sell_mask, 'price'] - validated_df.loc[sell_mask, 'open']
    ) / tick_size

    agent_total_savings = validated_df['agent_savings_ticks'].sum()
    agent_buy_savings = validated_df['agent_buy_savings_ticks'].sum()
    agent_sell_savings = validated_df['agent_sell_savings_ticks'].sum()
    
    print(f"   Agent total savings:  {agent_total_savings:.1f} ticks")
    print(f"   Agent buy savings:    {agent_buy_savings:.1f} ticks")
    print(f"   Agent sell savings:   {agent_sell_savings:.1f} ticks")

    # Step 3: Filter to sell orders only
    print("\n3. Filtering to sell orders only...")
    sell_only_df = validated_df[sell_mask].copy()
    print(f"   Total trades:         {len(validated_df)}")
    print(f"   Buy trades:          {len(buy_mask[buy_mask])}")
    print(f"   Sell trades:         {len(sell_mask[sell_mask])} ← Using these")

    # Step 4: Add required columns
    sell_only_df['range_dn_ticks'] = (sell_only_df['open'] - sell_only_df['low']) / tick_size
    sell_only_df['range_up_ticks'] = (sell_only_df['high'] - sell_only_df['open']) / tick_size

    # Detect states
    detector = StateDetector(m=60, thresh=2.5)
    sell_only_df = detector.detect_states(sell_only_df)

    # Initialize optimizer
    optimizer = UtilityOptimizer(
        window_size=window_size,
        min_penalty=min_penalty,
        max_level=max_level
    )

    # Step 5: Apply optimized strategy on sell orders
    print(f"\n4. Applying optimized strategy on sell orders only...")
    print(f"   Window: {window_size}, Min penalty: {min_penalty}, Max level: {max_level}")

    warmup = window_size
    total_trades = len(sell_only_df) - warmup

    if total_trades <= 0:
        print("   ERROR: Not enough sell trades after warmup!")
        return None

    optimized_savings = np.zeros(total_trades)

    # Convert to numpy arrays for speed
    open_arr = sell_only_df['open'].values
    high_arr = sell_only_df['high'].values
    agent_price_arr = sell_only_df['price'].values
    agent_savings_arr = sell_only_df['agent_sell_savings_ticks'].values

    print(f"   Processing {total_trades} sell trades (warmup={warmup})...")

    for i in tqdm(range(warmup, len(sell_only_df)), desc="Optimizing"):
        # Get optimal limits for sell direction
        limits = optimizer.get_limits(sell_only_df, i, tick_size, direction='sell')

        # Calculate sell savings
        sell_gap_dollars = high_arr[i] - open_arr[i]
        sell_gap_ticks = sell_gap_dollars / tick_size

        sell_save = 0.0
        for level, weight in limits:
            if sell_gap_ticks >= level:
                sell_save += weight * level

        idx = i - warmup
        optimized_savings[idx] = sell_save

    total_optimized_savings = optimized_savings.sum()

    print(f"   Optimized sell savings: {total_optimized_savings:.1f} ticks")

    # Step 6: Comparison (sell only)
    print("\n" + "="*70)
    print("RESULTS (SELL ORDERS ONLY)")
    print("="*70)
    print(f"Agent sell:      {agent_sell_savings:.1f} ticks")
    print(f"Optimized sell:  {total_optimized_savings:.1f} ticks")
    improvement = total_optimized_savings - agent_sell_savings
    improvement_pct = (improvement / agent_sell_savings * 100) if agent_sell_savings > 0 else 0
    print(f"Improvement:     {improvement:+.1f} ticks ({improvement_pct:+.1f}%)")
    print("="*70)

    return {
        'agent_sell_savings': agent_sell_savings,
        'optimized_sell_savings': total_optimized_savings,
        'improvement': improvement,
        'improvement_pct': improvement_pct,
        'num_sell_trades': len(sell_mask[sell_mask]),
        'num_trades_processed': total_trades
    }


if __name__ == '__main__':
    print("\n" + "="*70)
    print("SELL-ONLY OPTIMIZATION TEST")
    print("="*70 + "\n")

    results = test_sell_only(
        agent_file='data_export/Nasdaq/AIAgent_Nasdaq.csv',
        contract_name='NQH20',
        window_size=60,
        min_penalty=5.0,
        max_level=10.0,
        tick_size=0.25
    )

    if results:
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Agent sell performance:  {results['agent_sell_savings']:.1f} ticks")
        print(f"Optimized performance:    {results['optimized_sell_savings']:.1f} ticks")
        print(f"Improvement:             {results['improvement']:+.1f} ticks ({results['improvement_pct']:+.1f}%)")
        print(f"Total sell trades:       {results['num_sell_trades']}")
        print(f"Trades processed:        {results['num_trades_processed']}")
        print("="*70)