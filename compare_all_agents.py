#!/usr/bin/env python3
"""
Compare Agent vs Optimized Strategy across ALL assets

Run optimized strategy on same timestamps as agent trades and compare performance.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
from strategies_optimized_final import UtilityOptimizer
from state_detection import StateDetector
from tqdm import tqdm

# Asset configurations
ASSET_CONFIGS = {
    'Nasdaq': {'tick_size': 0.25, 'agent_pattern': 'AIAgent_Nasdaq'},
    'Gold': {'tick_size': 0.10, 'agent_pattern': 'AIAgent_Gold'},
    'German Bunds - German Government Bonds': {'tick_size': 0.01, 'agent_pattern': 'AIAgent_Bunds'},
    'GBP - British Pound': {'tick_size': 0.0001, 'agent_pattern': 'AIAgent_GBPUSD'},
    'JPY - Japanese Yen': {'tick_size': 0.005, 'agent_pattern': 'AIAgent_JPY'},
    'HeatingOil': {'tick_size': 0.01, 'agent_pattern': 'AIAgent_HeatingOil'},
    'EuroStoxx': {'tick_size': 0.50, 'agent_pattern': 'AIAgent_EuroStoxx'},
}


def load_agent_data(agent_file):
    """Load agent data and detect trades"""
    df = pd.read_csv(agent_file, header=None,
                    names=['date', 'hour', 'min', 'price', 'cum_vol'])
    
    start_date = datetime(1900, 1, 1)
    df['datetime'] = df.apply(
        lambda row: start_date + timedelta(days=int(row['date']) - 2,
                                          hours=int(row['hour']),
                                          minutes=int(row['min'])),
        axis=1
    )
    
    df = df.set_index('datetime').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    df['vol'] = df['cum_vol'].diff(-1).abs().fillna(0)
    df['is_trade'] = df['vol'] > 0
    
    return df


def load_contract_data(contract_dir, exclude_pattern='aiagent'):
    """Load all contracts from directory and merge"""
    contracts = {}
    contract_files = [f for f in glob.glob(os.path.join(contract_dir, '*.csv'))
                      if exclude_pattern.lower() not in f.lower()]
    
    for file_path in sorted(contract_files):
        contract_name = os.path.basename(file_path).replace('.csv', '')
        df = pd.read_csv(file_path, header=None)
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y.%m.%d.%H:%M:%S')
        df = df.dropna(subset=['datetime'])
        df = df.set_index('datetime').sort_index()
        contracts[contract_name] = df
    
    return contracts


def merge_contracts(contracts):
    """Merge multiple contracts by volume-based rollover"""
    if not contracts:
        return None
    
    # Sort contracts by name (assumes chronological order)
    contract_names = sorted(contracts.keys())
    
    # Find rollover points by volume
    merged = []
    active_contract = None
    active_volume = 0
    
    for name in contract_names:
        df = contracts[name]
        for idx, row in df.iterrows():
            if row['volume'] > active_volume:
                active_contract = name
                active_volume = row['volume']
            
            if active_contract == name:
                merged.append(row)
    
    return pd.DataFrame(merged)


def run_optimized_strategy(df_ohlc, agent_trades, tick_size):
    """Run optimized strategy on same timestamps as agent"""
    print(f'  Running optimized strategy...')
    
    # Calculate range metrics
    df_ohlc = df_ohlc.copy()
    df_ohlc['range_dn'] = (df_ohlc['open'] - df_ohlc['low']) / tick_size
    df_ohlc['range_up'] = (df_ohlc['high'] - df_ohlc['open']) / tick_size
    
    # Initialize state detector and optimizer
    detector = StateDetector(m=60, thresh=2.5)
    optimizer = UtilityOptimizer(window_size=60, price_levels=[1.0, 3.0, 5.0])
    
    # Build ePDF states using detector
    df_ohlc = detector.detect_states(df_ohlc)
    df_ohlc['state'] = df_ohlc['prev_state'].fillna('Low')
    
    # Run strategy on agent trade timestamps
    results = []
    for trade_idx, (trade_time, trade_row) in enumerate(agent_trades.iterrows()):
        if trade_time not in df_ohlc.index:
            # Find closest bar
            closest_idx = df_ohlc.index.get_indexer([trade_time], method='nearest')[0]
            if closest_idx < 0:
                continue
            trade_time = df_ohlc.index[closest_idx]
        
        bar_idx = df_ohlc.index.get_loc(trade_time)
        if bar_idx < 60:
            continue
        
        # Get OHLC data
        ohlc_row = df_ohlc.iloc[bar_idx]
        state = ohlc_row['state']
        
        # Update ePDF with historical data
        hist_df = df_ohlc.iloc[max(0, bar_idx-60):bar_idx]
        for _, row in hist_df.iterrows():
            optimizer.epdf.update(
                state='Low' if row['state'] == 'Low' else 'High',
                range_dn=row['range_dn'],
                range_up=row['range_up'],
                movement=0
            )
        
        # Get optimal levels
        cum_probs = optimizer._get_cumulative_probs(state)
        price_levels, weights = optimizer._optimize_weights(cum_probs)
        
        # Calculate fill and savings
        agent_price = trade_row['price']
        agent_direction = 'buy' if agent_price <= ohlc_row['open'] else 'sell'
        
        # Calculate optimized savings
        opt_savings = 0
        opt_filled = False
        
        if agent_direction == 'buy':
            # Buy: limit = open - level, fill if low <= limit
            for (level, weight), price_level in zip(weights.items(), price_levels):
                limit_price = ohlc_row['open'] - price_level * tick_size
                if ohlc_row['low'] <= limit_price:
                    opt_savings += weight * (ohlc_row['open'] - limit_price)
                    opt_filled = True
                else:
                    # Missed - penalty
                    opt_savings -= weight * 10 * tick_size  # 10 tick penalty
        else:
            # Sell: limit = open + level, fill if high >= limit
            for (level, weight), price_level in zip(weights.items(), price_levels):
                limit_price = ohlc_row['open'] + price_level * tick_size
                if ohlc_row['high'] >= limit_price:
                    opt_savings += weight * (limit_price - ohlc_row['open'])
                    opt_filled = True
                else:
                    opt_savings -= weight * 10 * tick_size
        
        # Agent savings
        if agent_direction == 'buy':
            agent_savings = ohlc_row['open'] - agent_price
        else:
            agent_savings = agent_price - ohlc_row['open']
        
        results.append({
            'timestamp': trade_time,
            'direction': agent_direction,
            'agent_price': agent_price,
            'open': ohlc_row['open'],
            'agent_savings_ticks': agent_savings / tick_size,
            'opt_savings_ticks': opt_savings / tick_size,
            'opt_filled': opt_filled,
            'state': state,
        })
    
    return pd.DataFrame(results)


def compare_asset(asset_name, config):
    """Compare agent vs optimized for one asset"""
    print(f"\n{'='*70}")
    print(f"Asset: {asset_name}")
    print(f"Tick size: {config['tick_size']}")
    print('='*70)
    
    asset_dir = os.path.join('data_export', asset_name)
    if not os.path.exists(asset_dir):
        print(f'  SKIP: Directory not found')
        return None
    
    # Find agent file
    agent_files = [f for f in os.listdir(asset_dir) if config['agent_pattern'] in f]
    if not agent_files:
        print(f'  SKIP: No agent file found')
        return None
    
    agent_file = os.path.join(asset_dir, agent_files[0])
    
    # Load data
    print(f'  Loading agent data...')
    agent_df = load_agent_data(agent_file)
    agent_trades = agent_df[agent_df['is_trade']].copy()
    print(f'    Total bars: {len(agent_df):,}')
    print(f'    Trades: {len(agent_trades):,}')
    
    print(f'  Loading contract data...')
    contracts = load_contract_data(asset_dir)
    print(f'    Contracts loaded: {len(contracts)}')
    
    # Merge contracts
    merged_df = merge_contracts(contracts)
    if merged_df is None:
        print(f'  SKIP: Failed to merge contracts')
        return None
    print(f'    Merged bars: {len(merged_df):,}')
    
    # Run comparison
    results_df = run_optimized_strategy(merged_df, agent_trades, config['tick_size'])
    
    if len(results_df) == 0:
        print(f'  SKIP: No results')
        return None
    
    # Calculate statistics
    agent_total = results_df['agent_savings_ticks'].sum()
    opt_total = results_df['opt_savings_ticks'].sum()
    improvement = opt_total - agent_total
    
    buy_mask = results_df['direction'] == 'buy'
    sell_mask = results_df['direction'] == 'sell'
    
    stats = {
        'asset': asset_name,
        'total_trades': len(results_df),
        'agent_total_ticks': agent_total,
        'opt_total_ticks': opt_total,
        'improvement_ticks': improvement,
        'improvement_pct': (improvement / abs(agent_total) * 100) if agent_total != 0 else 0,
        'buy_trades': buy_mask.sum(),
        'sell_trades': sell_mask.sum(),
        'agent_buy_ticks': results_df.loc[buy_mask, 'agent_savings_ticks'].sum(),
        'agent_sell_ticks': results_df.loc[sell_mask, 'agent_savings_ticks'].sum(),
        'opt_buy_ticks': results_df.loc[buy_mask, 'opt_savings_ticks'].sum(),
        'opt_sell_ticks': results_df.loc[sell_mask, 'opt_savings_ticks'].sum(),
        'opt_fill_rate': results_df['opt_filled'].mean(),
    }
    
    print(f'\n  Results:')
    print(f'    Agent Total: {agent_total:,.1f} ticks')
    print(f'    Optimized Total: {opt_total:,.1f} ticks')
    print(f'    Improvement: {improvement:,.1f} ticks ({stats["improvement_pct"]:+.1f}%)')
    print(f'    Opt Fill Rate: {stats["opt_fill_rate"]*100:.1f}%')
    
    return stats


def main():
    print('='*70)
    print('AGENT vs OPTIMIZED STRATEGY COMPARISON')
    print('All Assets')
    print('='*70)
    
    all_stats = []
    
    for asset_name, config in ASSET_CONFIGS.items():
        stats = compare_asset(asset_name, config)
        if stats:
            all_stats.append(stats)
    
    # Summary
    print(f"\n{'='*70}")
    print('SUMMARY')
    print('='*70)
    
    df_summary = pd.DataFrame(all_stats)
    print(df_summary.to_string(index=False))
    
    # Save results
    output_file = 'results/agent_vs_optimized_summary.csv'
    df_summary.to_csv(output_file, index=False)
    print(f'\nSaved: {output_file}')
    
    # Total improvement
    total_agent = df_summary['agent_total_ticks'].sum()
    total_opt = df_summary['opt_total_ticks'].sum()
    total_improvement = total_opt - total_agent
    
    print(f"\n{'='*70}")
    print('OVERALL RESULTS')
    print('='*70)
    print(f'Total Trades: {df_summary["total_trades"].sum():,}')
    print(f'Agent Total: {total_agent:,.1f} ticks')
    print(f'Optimized Total: {total_opt:,.1f} ticks')
    print(f'Total Improvement: {total_improvement:,.1f} ticks ({total_improvement/abs(total_agent)*100:+.1f}%)')
    
    return df_summary


if __name__ == '__main__':
    main()
