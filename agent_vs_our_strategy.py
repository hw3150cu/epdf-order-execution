#!/usr/bin/env python3
"""
Agent vs Our Optimized Strategy - Fair Comparison

Compare agent execution vs our ePDF-based optimization on SAME trades.

Fair comparison:
- Same timestamps
- Same direction (buy/sell)
- Same volume
- Different execution prices
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
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
    """Load agent data with volume"""
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
    df['vol_change'] = df['cum_vol'].diff().abs()
    df['is_trade'] = df['vol_change'] > 0
    df['volume'] = df['vol_change']
    
    return df


def load_and_merge_contracts(asset_dir):
    """Load and merge contracts by volume rollover"""
    contracts = {}
    contract_files = [f for f in glob.glob(os.path.join(asset_dir, '*.csv'))
                      if 'AIAgent' not in f]
    
    for file_path in sorted(contract_files):
        df = pd.read_csv(file_path, header=None)
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y.%m.%d.%H:%M:%S')
        df = df.set_index('datetime').sort_index()
        contracts[os.path.basename(file_path).replace('.csv', '')] = df
    
    if not contracts:
        return None
    
    # Merge by picking best contract at each time
    best_contract = max(contracts.keys(), key=lambda k: len(contracts[k]))
    return contracts[best_contract]


def simple_limit_strategy(open_price, high, low, tick_size, direction, level_ticks=2):
    """
    Simple limit order strategy.
    
    Buy: place limit at open - level_ticks, fill if low <= limit
    Sell: place limit at open + level_ticks, fill if high >= limit
    
    Returns: (execution_price, filled)
    """
    if direction == 'buy':
        limit_price = open_price - level_ticks * tick_size
        if low <= limit_price:
            return limit_price, True  # Filled at limit
        else:
            return open_price, False  # Missed, execute at open
    else:  # sell
        limit_price = open_price + level_ticks * tick_size
        if high >= limit_price:
            return limit_price, True  # Filled at limit
        else:
            return open_price, False  # Missed, execute at open


def compare_asset(asset_name, config):
    """Compare agent vs our strategy for one asset"""
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
    
    # Load agent data
    print(f'  Loading agent data...')
    agent_df = load_agent_data(agent_file)
    agent_trades = agent_df[agent_df['is_trade']].copy()
    print(f'    Total bars: {len(agent_df):,}')
    print(f'    Trades: {len(agent_trades):,}')
    print(f'    Avg volume: {agent_trades["volume"].mean():.1f}')
    
    # Load contract data
    print(f'  Loading contract data...')
    contract_df = load_and_merge_contracts(asset_dir)
    if contract_df is None:
        print(f'  SKIP: No contract data')
        return None
    print(f'    Contract bars: {len(contract_df):,}')
    
    # Match and compare
    print(f'  Running comparison...')
    tick_size = config['tick_size']
    
    results = []
    for trade_time, trade_row in tqdm(agent_trades.iterrows(), total=len(agent_trades), desc='  Matching'):
        # Find OHLC
        if trade_time in contract_df.index:
            ohlc = contract_df.loc[trade_time]
        else:
            idx = contract_df.index.get_indexer([trade_time], method='nearest')[0]
            if idx < 0:
                continue
            ohlc = contract_df.iloc[idx]
        
        # Determine direction from agent price vs open
        agent_price = trade_row['price']
        direction = 'buy' if agent_price <= ohlc['open'] else 'sell'
        volume = trade_row['volume']
        
        # Agent performance
        if direction == 'buy':
            agent_savings_ticks = (ohlc['open'] - agent_price) / tick_size
        else:
            agent_savings_ticks = (agent_price - ohlc['open']) / tick_size
        
        # Our strategy: try 1, 2, 3 tick limit levels
        our_results = {}
        for level in [1, 2, 3]:
            exec_price, filled = simple_limit_strategy(
                ohlc['open'], ohlc['high'], ohlc['low'], tick_size, direction, level
            )
            if direction == 'buy':
                our_savings = (ohlc['open'] - exec_price) / tick_size
            else:
                our_savings = (exec_price - ohlc['open']) / tick_size
            our_results[level] = {'savings': our_savings, 'filled': filled}
        
        results.append({
            'timestamp': trade_time,
            'direction': direction,
            'volume': volume,
            'agent_price': agent_price,
            'open': ohlc['open'],
            'agent_savings_ticks': agent_savings_ticks,
            'our_savings_1tick': our_results[1]['savings'],
            'our_filled_1tick': our_results[1]['filled'],
            'our_savings_2tick': our_results[2]['savings'],
            'our_filled_2tick': our_results[2]['filled'],
            'our_savings_3tick': our_results[3]['savings'],
            'our_filled_3tick': our_results[3]['filled'],
        })
    
    df_results = pd.DataFrame(results)
    if len(df_results) == 0:
        print(f'  SKIP: No matches')
        return None
    
    print(f'    Matched: {len(df_results):,} ({len(df_results)/len(agent_trades)*100:.1f}%)')
    
    # Calculate statistics for each strategy
    def calc_stats(df, savings_col, filled_col, prefix):
        return {
            f'{prefix}_total_savings': df[savings_col].sum(),
            f'{prefix}_avg_savings': df[savings_col].mean(),
            f'{prefix}_fill_rate': df[filled_col].mean() if filled_col else 1.0,
            f'{prefix}_win_rate': (df[savings_col] > 0).mean(),
        }
    
    stats = {
        'asset': asset_name,
        'total_trades': len(df_results),
        'volume_total': df_results['volume'].sum(),
    }
    
    # Agent stats
    agent_stats = calc_stats(df_results, 'agent_savings_ticks', None, 'agent')
    stats.update(agent_stats)
    
    # Our strategy stats (1, 2, 3 tick)
    for level in [1, 2, 3]:
        level_stats = calc_stats(df_results, f'our_savings_{level}tick', f'our_filled_{level}tick', f'our_{level}tick')
        stats.update(level_stats)
    
    # Calculate improvement vs agent
    for level in [1, 2, 3]:
        stats[f'our_{level}tick_improvement'] = stats[f'our_{level}tick_total_savings'] - stats['agent_total_savings']
    
    print(f'\n  Results (Total Savings in ticks):')
    print(f'    Agent:        {stats["agent_total_savings"]:>12,.1f} ticks (win rate: {stats["agent_win_rate"]*100:.1f}%)')
    for level in [1, 2, 3]:
        improvement = stats[f'our_{level}tick_improvement']
        fill_rate = stats[f'our_{level}tick_fill_rate']
        print(f'    Our ({level} tick):   {stats[f"our_{level}tick_total_savings"]:>12,.1f} ticks (fill: {fill_rate*100:.1f}%, improvement: {improvement:+,.1f})')
    
    return stats


def main():
    print('='*70)
    print('AGENT vs OUR OPTIMIZED STRATEGY')
    print('Fair Comparison: Same trades, same timestamps, different execution')
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
    
    # Select key columns
    key_cols = ['asset', 'total_trades', 'agent_total_savings', 
                'our_1tick_total_savings', 'our_1tick_fill_rate', 'our_1tick_improvement',
                'our_2tick_total_savings', 'our_2tick_fill_rate', 'our_2tick_improvement']
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 300)
    print(df_summary[key_cols].to_string(index=False))
    
    # Save results
    df_summary.to_csv('results/agent_vs_our_strategy_summary.csv', index=False)
    print(f'\nSaved: results/agent_vs_our_strategy_summary.csv')
    
    # Overall totals
    total_agent = df_summary['agent_total_savings'].sum()
    total_our_1tick = df_summary['our_1tick_total_savings'].sum()
    total_our_2tick = df_summary['our_2tick_total_savings'].sum()
    
    print(f"\n{'='*70}")
    print('OVERALL COMPARISON')
    print('='*70)
    print(f'Total Trades: {df_summary["total_trades"].sum():,}')
    print(f'Agent Total Savings: {total_agent:,.1f} ticks')
    print(f'Our Strategy (1 tick): {total_our_1tick:,.1f} ticks (improvement: {total_our_1tick - total_agent:+,.1f})')
    print(f'Our Strategy (2 tick): {total_our_2tick:,.1f} ticks (improvement: {total_our_2tick - total_agent:+,.1f})')
    
    return df_summary


if __name__ == '__main__':
    main()
