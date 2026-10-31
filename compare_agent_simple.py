#!/usr/bin/env python3
"""
Simple Agent vs Market Comparison

Compare agent execution price vs open price (market order baseline)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob

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
    """Load agent data"""
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


def load_and_merge_contracts(asset_dir):
    """Load and merge all contracts"""
    contracts = {}
    contract_files = [f for f in glob.glob(os.path.join(asset_dir, '*.csv'))
                      if 'AIAgent' not in f]
    
    for file_path in sorted(contract_files):
        contract_name = os.path.basename(file_path).replace('.csv', '')
        df = pd.read_csv(file_path, header=None)
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y.%m.%d.%H:%M:%S')
        df = df.set_index('datetime').sort_index()
        contracts[contract_name] = df
    
    # Simple merge: use the contract with most data
    if not contracts:
        return None
    
    best_contract = max(contracts.keys(), key=lambda k: len(contracts[k]))
    return contracts[best_contract]


def compare_asset(asset_name, config):
    """Compare agent vs market for one asset"""
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
    
    # Load contract data
    print(f'  Loading contract data...')
    contract_df = load_and_merge_contracts(asset_dir)
    if contract_df is None:
        print(f'  SKIP: No contract data')
        return None
    print(f'    Contract bars: {len(contract_df):,}')
    
    # Match agent trades with OHLC data
    print(f'  Matching trades with OHLC...')
    matched = []
    for trade_time, trade_row in agent_trades.iterrows():
        if trade_time in contract_df.index:
            ohlc = contract_df.loc[trade_time]
            matched.append({
                'timestamp': trade_time,
                'agent_price': trade_row['price'],
                'open': ohlc['open'],
                'high': ohlc['high'],
                'low': ohlc['low'],
                'close': ohlc['close'],
            })
        else:
            # Try to find closest match
            idx = contract_df.index.get_indexer([trade_time], method='nearest')[0]
            if idx >= 0:
                ohlc = contract_df.iloc[idx]
                matched.append({
                    'timestamp': trade_time,
                    'agent_price': trade_row['price'],
                    'open': ohlc['open'],
                    'high': ohlc['high'],
                    'low': ohlc['low'],
                    'close': ohlc['close'],
                })
    
    df_matched = pd.DataFrame(matched)
    if len(df_matched) == 0:
        print(f'  SKIP: No matches found')
        return None
    
    print(f'    Matched: {len(df_matched):,} ({len(df_matched)/len(agent_trades)*100:.1f}%)')
    
    # Calculate savings
    tick_size = config['tick_size']
    df_matched['price_diff'] = df_matched['open'] - df_matched['agent_price']
    df_matched['savings_ticks'] = df_matched['price_diff'] / tick_size
    
    # Classify direction
    df_matched['direction'] = np.where(df_matched['price_diff'] >= 0, 'buy', 'sell')
    df_matched['abs_savings_ticks'] = df_matched['savings_ticks'].abs()
    
    # Calculate statistics
    total_trades = len(df_matched)
    buy_trades = (df_matched['direction'] == 'buy').sum()
    sell_trades = (df_matched['direction'] == 'sell').sum()
    
    total_savings = df_matched['savings_ticks'].sum()
    buy_savings = df_matched[df_matched['direction'] == 'buy']['savings_ticks'].sum()
    sell_savings = df_matched[df_matched['direction'] == 'sell']['savings_ticks'].sum()
    
    # Calculate win rate (positive savings)
    win_rate = (df_matched['savings_ticks'] > 0).mean()
    buy_win_rate = (df_matched[df_matched['direction'] == 'buy']['savings_ticks'] > 0).mean()
    sell_win_rate = (df_matched[df_matched['direction'] == 'sell']['savings_ticks'] > 0).mean()
    
    # Check if inside OHLC
    df_matched['inside_ohlc'] = (df_matched['agent_price'] >= df_matched['low']) & \
                                 (df_matched['agent_price'] <= df_matched['high'])
    inside_rate = df_matched['inside_ohlc'].mean()
    
    stats = {
        'asset': asset_name,
        'total_trades': total_trades,
        'buy_trades': buy_trades,
        'sell_trades': sell_trades,
        'total_savings_ticks': total_savings,
        'buy_savings_ticks': buy_savings,
        'sell_savings_ticks': sell_savings,
        'win_rate': win_rate,
        'buy_win_rate': buy_win_rate,
        'sell_win_rate': sell_win_rate,
        'inside_ohlc_rate': inside_rate,
        'avg_savings_ticks': df_matched['savings_ticks'].mean(),
        'std_savings_ticks': df_matched['savings_ticks'].std(),
    }
    
    print(f'\n  Results:')
    print(f'    Total Savings: {total_savings:,.1f} ticks (${total_savings * tick_size:,.2f})')
    print(f'    Buy Savings: {buy_savings:,.1f} ticks')
    print(f'    Sell Savings: {sell_savings:,.1f} ticks')
    print(f'    Win Rate: {win_rate*100:.1f}%')
    print(f'    Inside OHLC: {inside_rate*100:.1f}%')
    
    return stats


def main():
    print('='*70)
    print('AGENT vs MARKET (OPEN) COMPARISON')
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
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print(df_summary.to_string(index=False))
    
    # Save results
    output_file = 'results/agent_vs_market_summary.csv'
    df_summary.to_csv(output_file, index=False)
    print(f'\nSaved: {output_file}')
    
    # Overall totals
    total_trades = df_summary['total_trades'].sum()
    total_savings = (df_summary['total_savings_ticks'] * df_summary.apply(
        lambda r: ASSET_CONFIGS[r['asset']]['tick_size'], axis=1)).sum()
    
    print(f"\n{'='*70}")
    print('OVERALL RESULTS')
    print('='*70)
    print(f'Total Trades: {total_trades:,}')
    print(f'Total Savings: {total_savings:,.2f} (in USD equivalent)')
    print(f'Average Win Rate: {df_summary["win_rate"].mean()*100:.1f}%')
    print(f'Average Inside OHLC: {df_summary["inside_ohlc_rate"].mean()*100:.1f}%')
    
    return df_summary


if __name__ == '__main__':
    main()
