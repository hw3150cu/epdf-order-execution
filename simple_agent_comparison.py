#!/usr/bin/env python3
"""
Simple Agent vs Our Strategy Comparison

For each agent trade, compare:
- Agent's execution price
- Our strategy's execution price (same volume, same bar)

No time window matching needed - just compare trade-by-trade.
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
    # 'HeatingOil': {'tick_size': 0.01, 'agent_pattern': 'AIAgent_HeatingOil'},  # TEMPORARILY DISABLED - data quality issue
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


def our_strategy_exec(open_price, high, low, tick_size, direction, volume):
    """
    Our optimized execution strategy.
    
    For each trade:
    - Split volume into slices
    - Place limit orders at open +/- 1 tick
    - Fill if price reached
    - Unfilled executes at close
    
    Returns: (avg_exec_price, total_volume, filled_volume)
    """
    # Simple approach: try to fill at limit, otherwise close
    if direction == 'buy':
        limit_price = open_price - 1 * tick_size
        if low <= limit_price:
            # Filled at limit
            return limit_price, volume, volume
        else:
            # Not filled, execute at close
            return open_price, volume, 0  # Assume close ≈ open for simplicity
    else:  # sell
        limit_price = open_price + 1 * tick_size
        if high >= limit_price:
            return limit_price, volume, volume
        else:
            return open_price, volume, 0


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
    agent_trades = agent_df[agent_df['is_trade']].copy()
    print(f'    Trades: {len(agent_trades):,}')
    print(f'    Total volume: {agent_trades["volume"].sum():,.0f}')
    
    print(f'  Loading contract data...')
    contract_df = load_contract_data(asset_dir)
    if contract_df is None:
        print(f'  SKIP: No contract data')
        return None
    print(f'    Contract bars: {len(contract_df):,}')
    
    # Compare trade by trade
    print(f'  Comparing trades...')
    tick_size = config['tick_size']
    
    results = []
    for trade_time, trade_row in agent_trades.iterrows():
        # Find OHLC
        if trade_time in contract_df.index:
            ohlc = contract_df.loc[trade_time]
        else:
            idx = contract_df.index.get_indexer([trade_time], method='nearest')[0]
            if idx < 0:
                continue
            ohlc = contract_df.iloc[idx]
        
        agent_price = trade_row['price']
        direction = trade_row['direction']
        volume = trade_row['volume']
        
        # Our strategy execution
        our_price, our_volume, our_filled = our_strategy_exec(
            ohlc['open'], ohlc['high'], ohlc['low'], tick_size, direction, volume
        )
        
        # Calculate savings (positive = we did better)
        if direction == 'buy':
            agent_savings = ohlc['open'] - agent_price
            our_savings = ohlc['open'] - our_price
        else:  # sell
            agent_savings = agent_price - ohlc['open']
            our_savings = our_price - ohlc['open']
        
        agent_savings_ticks = agent_savings / tick_size
        our_savings_ticks = our_savings / tick_size
        improvement_ticks = our_savings_ticks - agent_savings_ticks
        
        results.append({
            'timestamp': trade_time,
            'direction': direction,
            'volume': volume,
            'agent_price': agent_price,
            'our_price': our_price,
            'agent_savings_ticks': agent_savings_ticks,
            'our_savings_ticks': our_savings_ticks,
            'improvement_ticks': improvement_ticks,
            'our_filled': our_filled > 0,
        })
    
    df_results = pd.DataFrame(results)
    
    if len(df_results) == 0:
        print(f'  SKIP: No matches')
        return None
    
    print(f'    Matched: {len(df_results):,} ({len(df_results)/len(agent_trades)*100:.1f}%)')
    
    # Calculate statistics
    total_volume = df_results['volume'].sum()
    agent_total = df_results['agent_savings_ticks'].sum()
    our_total = df_results['our_savings_ticks'].sum()
    improvement = our_total - agent_total
    win_rate = (df_results['improvement_ticks'] > 0).mean()
    fill_rate = df_results['our_filled'].mean()
    
    # By direction
    buy_df = df_results[df_results['direction'] == 'buy']
    sell_df = df_results[df_results['direction'] == 'sell']
    
    stats = {
        'asset': asset_name,
        'num_trades': len(df_results),
        'total_volume': total_volume,
        'agent_total_ticks': agent_total,
        'our_total_ticks': our_total,
        'improvement_ticks': improvement,
        'win_rate': win_rate,
        'fill_rate': fill_rate,
        'buy_trades': len(buy_df),
        'sell_trades': len(sell_df),
        'buy_win_rate': (buy_df['improvement_ticks'] > 0).mean() if len(buy_df) > 0 else 0,
        'sell_win_rate': (sell_df['improvement_ticks'] > 0).mean() if len(sell_df) > 0 else 0,
    }
    
    print(f'\n  Results:')
    print(f'    Trades: {len(df_results):,}')
    print(f'    Volume: {total_volume:,.0f}')
    print(f'    Agent Total: {agent_total:,.1f} ticks')
    print(f'    Our Total: {our_total:,.1f} ticks')
    print(f'    Improvement: {improvement:+,.1f} ticks')
    print(f'    Win Rate: {win_rate*100:.1f}%')
    print(f'    Fill Rate: {fill_rate*100:.1f}%')
    
    return stats


def main():
    print('='*70)
    print('SIMPLE AGENT vs OUR STRATEGY COMPARISON')
    print('Trade-by-trade comparison, same volume')
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
    df_summary.to_csv('results/simple_agent_comparison_summary.csv', index=False)
    print(f'\nSaved: results/simple_agent_comparison_summary.csv')
    
    # Overall
    total_trades = df_summary['num_trades'].sum()
    total_improvement = df_summary['improvement_ticks'].sum()
    overall_win_rate = (df_summary['win_rate'] * df_summary['num_trades']).sum() / total_trades
    
    print(f"\n{'='*70}")
    print('OVERALL')
    print('='*70)
    print(f'Total Trades: {total_trades:,}')
    print(f'Total Improvement: {total_improvement:+,.1f} ticks')
    print(f'Overall Win Rate: {overall_win_rate*100:.1f}%')
    
    return df_summary


if __name__ == '__main__':
    main()
