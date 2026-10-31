"""
Backtest Engine (CORRECTED)
- Fixed: Uses open[t] as reference price
- Configurable: Tick size passed in
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BacktestResult:
    """Results from backtest"""
    fill_rate: float
    avg_savings: float
    total_savings: float
    trades: List[dict]
    baseline_returns: List[float]
    strategy_returns: List[float]


class BacktestEngine:
    """Backtest engine with limit order fill logic - CORRECTED"""
    
    def __init__(self, tick_size: float = 0.25, warmup_bars: int = 50):
        """
        Initialize backtest engine.
        
        Args:
            tick_size: Minimum price fluctuation (configurable)
            warmup_bars: Bars to skip for warmup
        """
        self.tick_size = tick_size
        self.warmup_bars = warmup_bars
    
    def simulate_multi_fill(
        self,
        row: pd.Series,
        limit_orders: list
    ) -> Tuple[float, float]:
        """
        Simulate multiple limit orders with mode-based robustness.
        
        Fill logic:
        - If best mode is NOT better than close, use open (market order)
        - Otherwise, place limit orders with unfilled going to close
        
        Args:
            row: OHLC bar
            limit_orders: List of (limit_price, weight) tuples
        
        Returns:
            (weighted_exec_price: float, fill_rate: float)
        """
        if not limit_orders:
            return row['open'], 0.0
        
        # Get the best (lowest) limit price from the modes
        best_limit = min([price for price, _ in limit_orders])
        
        # Robustness check: if best limit is NOT better than close, use open (market order)
        if best_limit >= row['close']:
            return row['open'], 0.0
        
        # Otherwise, proceed with limit orders
        weighted_price = 0.0
        total_filled_weight = 0.0
        
        for limit_price, weight in limit_orders:
            # Check if order fills (price drops to limit)
            if row['low'] <= limit_price:
                weighted_price += limit_price * weight
                total_filled_weight += weight
        
        # Unfilled portion goes to close
        unfilled_weight = 1.0 - total_filled_weight
        if unfilled_weight > 0:
            weighted_price += row['close'] * unfilled_weight
        
        return weighted_price, total_filled_weight
    
    def backtest(
        self,
        df: pd.DataFrame,
        strategy
    ) -> BacktestResult:
        """
        Run backtest with CORRECTED reference price (open[t]).
        
        Args:
            df: DataFrame with OHLC and state columns
            strategy: Strategy object with get_limit_prices() method
        
        Returns:
            BacktestResult with metrics
        """
        trades = []
        baseline_returns = []
        strategy_returns = []
        total_order_size = 1000  # ticks
        filled = 0
        total_savings = 0.0
        
        for i in range(self.warmup_bars, len(df)):
            row = df.iloc[i]
            
            # Baseline: market order at open
            baseline_return = row['open'] - row['close']
            baseline_returns.append(baseline_return)
            
            # Strategy: limit orders at optimized levels
            # REFERENCE PRICE IS open[t], NOT close[t-1]
            limit_orders = strategy.get_limit_prices(df, i)
            
            # Convert to prices (offset from OPEN)
            # price_levels are in ticks FROM open: open, open-1tick, open-2ticks
            # So actual limit prices = row['open'] - (level * tick_size)
            limit_prices = [
                row['open'] - (level_ticks * self.tick_size)
                for level_ticks, weight in limit_orders
            ]
            
            # Extract weights for visualization
            weights = [weight for _, weight in limit_orders]
            
            # Simulate fills with weights
            exec_price, fill_rate = self.simulate_multi_fill(
                row,
                [(price, weight) for price, weight in zip(limit_prices, weights)]
            )
            
            # Calculate savings (difference from buying at OPEN)
            # This is CORRECT: We're comparing execution price to current market price
            savings = row['open'] - exec_price
            strategy_returns.append(savings)
            total_savings += savings
            
            if fill_rate > 0:
                filled += 1
            
            trades.append({
                'bar': i,
                'open': row['open'],
                'close': row['close'],
                'limit_prices': limit_prices,
                'limit_weights': weights,
                'exec_price': exec_price,
                'fill_rate': fill_rate,
                'savings': savings
            })
        
        n_trades = len(df) - self.warmup_bars
        fill_rate = filled / n_trades if n_trades > 0 else 0
        avg_savings = total_savings / n_trades if n_trades > 0 else 0
        
        return BacktestResult(
            fill_rate=fill_rate,
            avg_savings=avg_savings,
            total_savings=total_savings,
            trades=trades,
            baseline_returns=baseline_returns,
            strategy_returns=strategy_returns
        )