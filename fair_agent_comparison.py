#!/usr/bin/env python3
"""
Fair Agent vs Optimized Strategy Comparison

Compare execution quality over SAME time window with SAME total volume.

Key insight:
- Agent executes a total volume over a time window [T0, T0+τ]
- Our strategy must execute SAME total volume in SAME window
- But we can optimize: order slicing, limit prices, timing within window

Metric: Volume-Weighted Average Price (VWAP)
- Lower VWAP for buys = better execution
- Higher VWAP for sells = better execution
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
    df['vol_change'] = df['cum_vol'].diff()
    df['is_trade'] = df['vol_change'].abs() > 0
    df['volume'] = df['vol_change'].abs()
    df['direction'] = np.where(df['vol_change'] > 0, 'buy', np.where(df['vol_change'] < 0, 'sell', 'flat'))
    
    return df


def load_contract_data(asset_dir):
    """Load and merge contracts"""
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
    
    # Use the largest contract
    best = max(contracts.keys(), key=lambda k: len(contracts[k]))
    return contracts[best]


def find_execution_windows(agent_df, window_minutes=30):
    """
    Find continuous execution windows.
    
    A window is a period where agent is actively trading (net position change).
    """
    # Group trades by direction and proximity
    trades = agent_df[agent_df['is_trade']].copy()
    
    if len(trades) == 0:
        return []
    
    windows = []
    
    # Find gaps in trading
    trades['time_gap'] = trades.index.to_series().diff().dt.total_seconds() / 60
    
    # New window starts after a gap > window_minutes
    trades['new_window'] = trades['time_gap'] > window_minutes
    
    # Assign window IDs
    trades['window_id'] = trades['new_window'].cumsum()
    
    # Group by window
    for window_id, group in trades.groupby('window_id'):
        if len(group) < 2:  # Skip single-trade windows
            continue
        
        net_volume = group['vol_change'].sum()
        if abs(net_volume) < 1:  # Skip if net volume is zero
            continue
        
        windows.append({
            'window_id': window_id,
            'start_time': group.index.min(),
            'end_time': group.index.max(),
            'trades': group,
            'net_volume': abs(net_volume),
            'direction': 'buy' if net_volume > 0 else 'sell',
            'num_trades': len(group),
        })
    
    return windows


def calculate_agent_vwap(window):
    """Calculate agent's VWAP for this window"""
    trades = window['trades']
    total_volume = trades['volume'].sum()
    vwap = (trades['price'] * trades['volume']).sum() / total_volume
    return vwap, total_volume


def optimized_execution(contract_df, window, tick_size):
    """
    Our optimized execution strategy.
    
    Strategy:
    1. Split total volume into N equal slices
    2. For each slice, place limit order at:
       - Buy: open - 1 tick (adjust based on fill)
       - Sell: open + 1 tick (adjust based on fill)
    3. Track fills and remaining volume
    4. At end of window, execute remaining at market (close)
    
    Returns: (vwap, total_volume, fill_rate)
    """
    start_time = window['start_time']
    end_time = window['end_time']
    total_volume = window['net_volume']
    direction = window['direction']
    
    # Get OHLC data for the window
    mask = (contract_df.index >= start_time) & (contract_df.index <= end_time)
    ohlc = contract_df[mask]
    
    if len(ohlc) == 0:
        return None, 0, 0
    
    # Split into equal slices (one per bar)
    num_slices = len(ohlc)
    slice_volume = total_volume / num_slices
    
    executed_volume = 0
    total_cost = 0
    filled_volume = 0
    
    for idx, (time, row) in enumerate(ohlc.iterrows()):
        remaining_volume = total_volume - executed_volume
        current_slice = min(slice_volume, remaining_volume)
        
        if current_slice <= 0:
            break
        
        # Place limit order
        if direction == 'buy':
            limit_price = row['open'] - 1 * tick_size  # 1 tick limit
            if row['low'] <= limit_price:
                # Filled at limit
                executed_volume += current_slice
                total_cost += limit_price * current_slice
                filled_volume += current_slice
            else:
                # Not filled, execute at close (must complete by end of window)
                if idx == len(ohlc) - 1:  # Last bar, must execute
                    executed_volume += current_slice
                    total_cost += row['close'] * current_slice
        else:  # sell
            limit_price = row['open'] + 1 * tick_size
            if row['high'] >= limit_price:
                executed_volume += current_slice
                total_cost += limit_price * current_slice
                filled_volume += current_slice
            else:
                if idx == len(ohlc) - 1:
                    executed_volume += current_slice
                    total_cost += row['close'] * current_slice
    
    if executed_volume == 0:
        return None, 0, 0
    
    vwap = total_cost / executed_volume
    fill_rate = filled_volume / executed_volume
    
    return vwap, executed_volume, fill_rate


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
    
    agent_files = [f for f in os.listdir(asset_dir) if config['agent_pattern'] in f]
    if not agent_files:
        print(f'  SKIP: No agent file found')
        return None
    
    agent_file = os.path.join(asset_dir, agent_files[0])
    
    print(f'  Loading agent data...')
    agent_df = load_agent_data(agent_file)
    print(f'    Total bars: {len(agent_df):,}')
    print(f'    Trades: {agent_df["is_trade"].sum():,}')
    
    print(f'  Loading contract data...')
    contract_df = load_contract_data(asset_dir)
    if contract_df is None:
        print(f'  SKIP: No contract data')
        return None
    print(f'    Contract bars: {len(contract_df):,}')
    
    print(f'  Finding execution windows...')
    windows = find_execution_windows(agent_df, window_minutes=30)
    print(f'    Found {len(windows)} windows')
    
    if len(windows) == 0:
        return None
    
    # Compare each window
    results = []
    tick_size = config['tick_size']
    
    for window in tqdm(windows, desc='  Comparing'):
        # Agent VWAP
        agent_vwap, agent_volume = calculate_agent_vwap(window)
        
        # Our optimized VWAP
        our_vwap, our_volume, our_fill_rate = optimized_execution(contract_df, window, tick_size)
        
        if our_vwap is None:
            continue
        
        # Calculate savings (positive = we did better)
        if window['direction'] == 'buy':
            # Lower VWAP is better for buys
            savings_per_unit = agent_vwap - our_vwap
        else:
            # Higher VWAP is better for sells
            savings_per_unit = our_vwap - agent_vwap
        
        total_savings_ticks = (savings_per_unit / tick_size) * our_volume
        
        results.append({
            'window_id': window['window_id'],
            'start_time': window['start_time'],
            'end_time': window['end_time'],
            'direction': window['direction'],
            'volume': our_volume,
            'agent_vwap': agent_vwap,
            'our_vwap': our_vwap,
            'savings_per_unit': savings_per_unit,
            'total_savings_ticks': total_savings_ticks,
            'our_fill_rate': our_fill_rate,
            'num_trades': window['num_trades'],
        })
    
    df_results = pd.DataFrame(results)
    
    if len(df_results) == 0:
        print(f'  SKIP: No valid comparisons')
        return None
    
    print(f'    Valid windows: {len(df_results)}')
    
    # Calculate statistics
    total_volume = df_results['volume'].sum()
    agent_total_savings = df_results['total_savings_ticks'].sum()
    avg_fill_rate = df_results['our_fill_rate'].mean()
    
    # Win rate: how often we beat agent
    win_rate = (df_results['savings_per_unit'] > 0).mean()
    
    # By direction
    buy_df = df_results[df_results['direction'] == 'buy']
    sell_df = df_results[df_results['direction'] == 'sell']
    
    stats = {
        'asset': asset_name,
        'num_windows': len(df_results),
        'total_volume': total_volume,
        'agent_total_savings_ticks': agent_total_savings,
        'our_avg_fill_rate': avg_fill_rate,
        'win_rate': win_rate,
        'buy_windows': len(buy_df),
        'sell_windows': len(sell_df),
        'buy_win_rate': (buy_df['savings_per_unit'] > 0).mean() if len(buy_df) > 0 else 0,
        'sell_win_rate': (sell_df['savings_per_unit'] > 0).mean() if len(sell_df) > 0 else 0,
    }
    
    print(f'\n  Results:')
    print(f'    Windows: {len(df_results)}')
    print(f'    Total Volume: {total_volume:,.0f}')
    print(f'    Our Fill Rate: {avg_fill_rate*100:.1f}%')
    print(f'    Win Rate (vs Agent): {win_rate*100:.1f}%')
    print(f'    Total Savings: {agent_total_savings:,.1f} ticks')
    
    return stats


def main():
    print('='*70)
    print('FAIR AGENT vs OPTIMIZED STRATEGY COMPARISON')
    print('Same time window, same total volume, different execution')
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
    
    # Save
    df_summary.to_csv('results/fair_agent_comparison_summary.csv', index=False)
    print(f'\nSaved: results/fair_agent_comparison_summary.csv')
    
    # Overall
    total_windows = df_summary['num_windows'].sum()
    overall_win_rate = (df_summary['win_rate'] * df_summary['num_windows']).sum() / total_windows
    
    print(f"\n{'='*70}")
    print('OVERALL')
    print('='*70)
    print(f'Total Windows: {total_windows}')
    print(f'Overall Win Rate: {overall_win_rate*100:.1f}%')
    
    return df_summary


if __name__ == '__main__':
    main()
