"""
Full Backtest Runner - Enhanced with Real Fill Model

Runs backtest comparison using real OHLC fill checking.
Integrates ConditionalFillModel and SimplePenaltyModel.

Usage:
    python run_full_backtest.py
"""

import numpy as np
import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Optional

# New fill model
from fill_model import ConditionalFillModel, SimplePenaltyModel, calculate_range_metrics

# Existing modules
from inventory_tracker import InventoryTracker
from state_transition import StateTransitionEstimator
from dynamic_penalty import DynamicPenalty


class EnhancedBacktestRunner:
    """Run backtests with real OHLC fill checking."""
    
    def __init__(self, target_quantity: float = 100, tick_size: float = 0.25):
        self.target_quantity = target_quantity
        self.tick_size = tick_size
        self.results = {}
        
        # Initialize fill model
        self.fill_model = ConditionalFillModel(tick_size=tick_size)
        self.penalty_model = SimplePenaltyModel(tick_size=tick_size)
        
    def _load_real_data(self, filepath: str) -> pd.DataFrame:
        """Load real data from CSV."""
        df = pd.read_csv(filepath, header=None, 
                         names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y.%m.%d.%H:%M:%S')
        df = df.sort_values('datetime').reset_index(drop=True)
        return df
        
    def _generate_synthetic_ohlc(self, n: int = 500, seed: int = 42) -> pd.DataFrame:
        """Generate synthetic OHLC data."""
        np.random.seed(seed)
        
        # Generate base prices
        base_price = 8500.0
        returns = np.random.randn(n) * 0.001  # 0.1% std
        
        closes = base_price * np.cumprod(1 + returns)
        
        # Generate OHLC from close
        data = []
        for i, close in enumerate(closes):
            # Random intraday range
            range_pct = np.random.uniform(0.0005, 0.002)  # 0.05% to 0.2% range
            high = close * (1 + range_pct * np.random.random())
            low = close * (1 - range_pct * np.random.random())
            open_price = low + (high - low) * np.random.random()
            
            data.append({
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': np.random.randint(100, 1000)
            })
            
        return pd.DataFrame(data)
        
    def _get_fill_levels(self, strategy: str, state: str = 'Low') -> List[tuple]:
        """
        Get limit order levels for each strategy.
        
        Returns:
            List of (level_ticks, weight) tuples
        """
        if strategy == 'Market':
            # Market order: level 0, 100%
            return [(0, 1.0)]
        elif strategy == 'TWAP':
            # TWAP: conservative, level 1-2
            return [(1, 0.5), (2, 0.5)]
        elif strategy == 'Aggressive':
            # Aggressive: level 3-5
            return [(3, 0.4), (4, 0.3), (5, 0.3)]
        elif strategy == 'StochasticControl':
            # Stochastic control: optimized levels
            # TODO: Get from optimizer based on state
            if state == 'Low':
                return [(0, 0.3), (1, 0.4), (2, 0.3)]
            else:
                return [(1, 0.3), (2, 0.4), (3, 0.3)]
        else:
            return [(0, 1.0)]
    
    def _run_single_backtest(self, df: pd.DataFrame, strategy: str, 
                            direction: str = 'buy') -> Dict:
        """
        Run backtest for a single strategy using real OHLC fill checking.
        
        Args:
            df: DataFrame with open, high, low, close columns
            strategy: Strategy name
            direction: 'buy' or 'sell'
        
        Returns:
            Dict with backtest results
        """
        T = min(len(df) - 1, 60)  # Leave one bar for penalty calculation
        ref_price = df['close'].iloc[0]
        
        # Track results
        pnls = []
        savings_list = []
        penalties_list = []
        inventory = 0.0
        filled_bars = 0
        total_bars = 0
        
        # Initialize modules for stochastic control
        if strategy == 'StochasticControl':
            tracker = InventoryTracker(target_quantity=self.target_quantity)
            penalty = DynamicPenalty(base_penalty=10.0)
            estimator = StateTransitionEstimator(n_states=3)
            
        for t in range(T):
            remaining = self.target_quantity - inventory
            
            if remaining <= 0:
                break
                
            total_bars += 1
            
            # Get OHLC for this bar
            open_price = df['open'].iloc[t]
            high = df['high'].iloc[t]
            low = df['low'].iloc[t]
            close = df['close'].iloc[t]
            
            # Get limit levels
            state = 'Low'  # TODO: Get from state detection
            levels = self._get_fill_levels(strategy, state)
            
            # Check fills for each level
            bar_filled_qty = 0.0
            bar_savings = 0.0
            
            for level_ticks, weight in levels:
                # Quantity for this level
                qty = remaining * weight
                
                # Check if filled using real OHLC
                is_filled = self.fill_model.check_fill(
                    open_price, high, low, level_ticks, direction
                )
                
                if is_filled:
                    # Calculate execution price
                    if direction == 'buy':
                        exec_price = open_price - level_ticks * self.tick_size
                        savings = (ref_price - exec_price) * qty
                    else:
                        exec_price = open_price + level_ticks * self.tick_size
                        savings = (exec_price - ref_price) * qty
                    
                    bar_filled_qty += qty
                    bar_savings += savings
                    
            # Update inventory
            if bar_filled_qty > 0:
                inventory += bar_filled_qty
                pnls.append(bar_savings)
                savings_list.append(bar_savings / self.tick_size)  # in ticks
                filled_bars += 1
                
                if strategy == 'StochasticControl':
                    tracker.update(bar_filled_qty, exec_price, ref_price, direction)
            else:
                # No fill - apply penalty at next open
                if t + 1 < len(df):
                    next_open = df['open'].iloc[t + 1]
                    penalty_price = self.penalty_model.calculate_penalty(
                        next_open, ref_price, direction
                    )
                    # Only apply penalty if we still need to fill
                    if remaining > 0:
                        penalties_list.append(penalty_price / self.tick_size)  # in ticks
                    
        # Calculate final metrics
        total_savings = sum(savings_list)
        total_penalties = sum(penalties_list)
        net_savings = total_savings - total_penalties
        
        total_pnl = sum(pnls) - sum(penalties_list) * self.tick_size
        n_trades = len(pnls)
        win_rate = np.mean([p > 0 for p in pnls]) if pnls else 0
        fill_rate = filled_bars / total_bars if total_bars > 0 else 0
        inventory_fill_rate = inventory / self.target_quantity
        
        # Sharpe ratio
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252)
        else:
            sharpe = 0
            
        return {
            'strategy': strategy,
            'direction': direction,
            'total_pnl': total_pnl,
            'total_savings_ticks': total_savings,
            'total_penalties_ticks': total_penalties,
            'net_savings_ticks': net_savings,
            'n_trades': n_trades,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe,
            'fill_rate': fill_rate,
            'inventory_fill_rate': inventory_fill_rate
        }
        
    def run_comparison(self, df: pd.DataFrame, data_name: str, 
                       direction: str = 'buy') -> pd.DataFrame:
        """Run comparison across all strategies."""
        strategies = ['Market', 'TWAP', 'Aggressive', 'StochasticControl']
        
        results = []
        
        print(f"\nRunning backtest on {data_name} ({direction})...")
        print(f"  Data shape: {df.shape}")
        print(f"  Price range: {df['close'].min():.2f} - {df['close'].max():.2f}")
        
        for strategy in strategies:
            result = self._run_single_backtest(df, strategy, direction)
            result['data'] = data_name
            results.append(result)
            
            print(f"  {strategy}: PnL={result['total_pnl']:.2f}, "
                  f"Savings={result['total_savings_ticks']:.1f} ticks, "
                  f"Penalties={result['total_penalties_ticks']:.1f} ticks, "
                  f"FillRate={result['fill_rate']:.1%}")
                
        return pd.DataFrame(results)
        
    def run_full_test(self) -> Dict:
        """Run full test on all data sources."""
        results = {}
        
        # 1. Synthetic data
        print("\n" + "=" * 70)
        print("TEST 1: SYNTHETIC OHLC DATA")
        print("=" * 70)
        synthetic_df = self._generate_synthetic_ohlc(n=500)
        results['synthetic_buy'] = self.run_comparison(synthetic_df, 'Synthetic', 'buy')
        results['synthetic_sell'] = self.run_comparison(synthetic_df, 'Synthetic', 'sell')
        
        # 2. Real NQ data
        print("\n" + "=" * 70)
        print("TEST 2: REAL NQH20 DATA")
        print("=" * 70)
        nq_path = 'data_export/Nasdaq/NQH20.csv'
        if os.path.exists(nq_path):
            real_df = self._load_real_data(nq_path)
            # Use first 500 rows for speed
            real_df = real_df.head(500)
            results['NQH20_buy'] = self.run_comparison(real_df, 'NQH20', 'buy')
            results['NQH20_sell'] = self.run_comparison(real_df, 'NQH20', 'sell')
        else:
            print(f"File not found: {nq_path}")
            results['NQH20_buy'] = None
            results['NQH20_sell'] = None
            
        self.results = results
        return results
        
    def save_results(self, output_dir: str = 'results'):
        """Save results to files."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Combine all results
        all_dfs = []
        for name, df in self.results.items():
            if df is not None:
                all_dfs.append(df)
                
        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            
            # Save CSV
            csv_path = f"{output_dir}/backtest_results_{timestamp}.csv"
            combined.to_csv(csv_path, index=False)
            print(f"\nSaved: {csv_path}")
            
            # Save Markdown report
            md_path = f"{output_dir}/backtest_report_{timestamp}.md"
            self._generate_markdown_report(md_path, combined)
            print(f"Saved: {md_path}")
            
            return csv_path, md_path
        return None, None
        
    def _generate_markdown_report(self, filepath: str, df: pd.DataFrame):
        """Generate Markdown report."""
        lines = []
        lines.append("# Backtest Comparison Report (Enhanced with Real Fill Model)")
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("## Fill Model")
        lines.append("- **ConditionalFillModel**: Real OHLC fill checking")
        lines.append("  - BUY: Fill if Low <= Open - level × tick")
        lines.append("  - SELL: Fill if High >= Open + level × tick")
        lines.append("- **SimplePenaltyModel**: Penalty = next_open - reference")
        lines.append("")
        
        for key in df['data'].unique():
            for direction in ['buy', 'sell']:
                subset = df[(df['data'] == key) & (df['direction'] == direction)]
                if len(subset) == 0:
                    continue
                    
                subset = subset.sort_values('net_savings_ticks', ascending=False)
                
                lines.append(f"## {key} Data - {direction.upper()}")
                lines.append("")
                lines.append("| Strategy | Net Savings (ticks) | PnL | Fill Rate | Win Rate |")
                lines.append("|----------|---------------------|-----|-----------|----------|")
                
                for _, row in subset.iterrows():
                    lines.append(
                        f"| {row['strategy']} | {row['net_savings_ticks']:.1f} | "
                        f"{row['total_pnl']:.2f} | {row['fill_rate']:.1%} | "
                        f"{row['win_rate']:.1%} |"
                    )
                    
                # Winner
                winner = subset.iloc[0]['strategy']
                winner_savings = subset.iloc[0]['net_savings_ticks']
                lines.append(f"\n**Winner**: {winner} ({winner_savings:.1f} ticks)")
                lines.append("")
                
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))


def main():
    """Main entry point."""
    print("=" * 70)
    print("ENHANCED BACKTEST COMPARISON")
    print("=" * 70)
    print("\nUsing:")
    print("  - ConditionalFillModel (real OHLC fill checking)")
    print("  - SimplePenaltyModel (next_open penalty)")
    print("\nStrategies: Market, TWAP, Aggressive, StochasticControl")
    print("Directions: BUY, SELL")
    
    runner = EnhancedBacktestRunner(target_quantity=100, tick_size=0.25)
    results = runner.run_full_test()
    
    # Save results
    csv_path, md_path = runner.save_results()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    # Print summary
    for name, df in results.items():
        if df is not None:
            winner = df.loc[df['net_savings_ticks'].idxmax()]
            print(f"\n{name}: Winner = {winner['strategy']} "
                  f"(Net Savings = {winner['net_savings_ticks']:.1f} ticks)")
            
    if csv_path:
        print(f"\nResults saved to: {csv_path}")
        print(f"Report saved to: {md_path}")
    
    return results


if __name__ == '__main__':
    main()