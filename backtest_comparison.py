"""
Backtest Comparison Module

Compares stochastic control strategy against baseline agents.

Usage:
    comparison = BacktestComparison()
    results = comparison.run(df)
    comparison.plot_results()
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import warnings

from inventory_tracker import InventoryTracker
from state_transition import StateTransitionEstimator
from dynamic_penalty import DynamicPenalty


@dataclass
class BacktestResult:
    """Results from a single backtest run."""
    name: str
    total_pnl: float
    n_trades: int
    win_rate: float
    avg_pnl_per_trade: float
    max_drawdown: float
    sharpe_ratio: float
    fill_rate: float


class BaselineAgent:
    """Baseline trading agent for comparison."""
    
    def __init__(self, target_quantity: float = 100, strategy: str = 'twap'):
        """
        Initialize baseline agent.
        
        Args:
            target_quantity: Target position
            strategy: Strategy type ('twap', 'vwap', 'aggressive')
        """
        self.target_quantity = target_quantity
        self.strategy = strategy
        self.inventory = 0.0
        self.total_pnl = 0.0
        self.trades = []
        
    def reset(self):
        """Reset agent state."""
        self.inventory = 0.0
        self.total_pnl = 0.0
        self.trades = []
        
    def get_order_quantity(self, t: int, T: int, price: float = 0) -> float:
        """Get order quantity based on strategy."""
        remaining = self.target_quantity - self.inventory
        
        if remaining <= 0:
            return 0
            
        if self.strategy == 'twap':
            # Time-weighted: equal amount each period
            periods_left = T - t
            if periods_left > 0:
                return min(remaining, remaining / periods_left)
            return remaining
            
        elif self.strategy == 'vwap':
            # Volume-weighted: more when volume is high
            # Simplified: use random volume proxy
            volume_factor = np.random.uniform(0.5, 1.5)
            base_qty = remaining / max(T - t, 1)
            return min(remaining, base_qty * volume_factor)
            
        elif self.strategy == 'aggressive':
            # Aggressive: fill quickly
            return min(remaining, remaining * 0.3)
            
        return min(remaining, 5)
        
    def execute(self, qty: float, price: float, ref_price: float) -> float:
        """Execute a trade."""
        pnl = (ref_price - price) * qty
        self.inventory += qty
        self.total_pnl += pnl
        self.trades.append({'qty': qty, 'price': price, 'pnl': pnl})
        return pnl


class StochasticControlAgent:
    """Agent using stochastic control modules."""
    
    def __init__(
        self,
        target_quantity: float = 100,
        base_penalty: float = 10.0
    ):
        """
        Initialize stochastic control agent.
        
        Args:
            target_quantity: Target position
            base_penalty: Base penalty for optimization
        """
        self.target_quantity = target_quantity
        self.tracker = InventoryTracker(target_quantity=target_quantity)
        self.penalty = DynamicPenalty(base_penalty=base_penalty)
        self.estimator = StateTransitionEstimator(n_states=3)
        self.is_fitted = False
        
    def reset(self):
        """Reset agent state."""
        self.tracker.reset()
        self.is_fitted = False
        
    def fit(self, returns: pd.Series):
        """Fit state estimator."""
        if len(returns) > 50:
            self.estimator.fit_from_returns(returns)
            self.is_fitted = True
            
    def get_order_quantity(self, t: int, T: int, price: float) -> float:
        """Get order quantity using stochastic control."""
        remaining = self.target_quantity - self.tracker.inventory
        
        if remaining <= 0:
            return 0
            
        # Calculate dynamic penalty
        lambda_t = self.penalty.calculate(
            t=t, T=T,
            current_inventory=self.tracker.inventory,
            target_inventory=self.target_quantity
        )
        
        # Adjust order size based on penalty and urgency
        urgency = self.tracker.get_urgency_factor(t, T)
        
        # Higher urgency = larger orders
        base_qty = remaining / max(T - t, 1)
        adjusted_qty = base_qty * urgency
        
        # Cap at remaining
        return min(remaining, max(1, adjusted_qty))
        
    def execute(self, qty: float, price: float, ref_price: float) -> float:
        """Execute a trade."""
        return self.tracker.update(
            filled_quantity=qty,
            exec_price=price,
            ref_price=ref_price,
            side='buy'
        )


class BacktestComparison:
    """
    Compare stochastic control vs baseline strategies.
    """
    
    def __init__(self, target_quantity: float = 100):
        """
        Initialize BacktestComparison.
        
        Args:
            target_quantity: Target position size
        """
        self.target_quantity = target_quantity
        self.results = {}
        
    def _run_single_backtest(
        self,
        df: pd.DataFrame,
        agent,
        price_col: str
    ) -> BacktestResult:
        """Run backtest for a single agent."""
        agent.reset()
        
        T = min(len(df), 60)
        ref_price = df[price_col].iloc[0]
        pnls = []
        
        # Fit if stochastic control agent
        if hasattr(agent, 'fit'):
            returns = df[price_col].pct_change().dropna()
            agent.fit(returns)
            
        for t in range(T):
            price = df[price_col].iloc[t]
            
            # Get order quantity
            qty = agent.get_order_quantity(t, T, price)
            
            if qty > 0:
                # Simulate fill with some randomness
                fill_prob = 0.7
                if np.random.random() < fill_prob:
                    # Execution price with slippage
                    exec_price = price * (1 + np.random.uniform(-0.0001, 0.0001))
                    pnl = agent.execute(qty, exec_price, ref_price)
                    pnls.append(pnl)
                    
        # Calculate metrics
        if hasattr(agent, 'tracker'):
            stats = agent.tracker.get_stats()
            total_pnl = stats['total_pnl']
            n_trades = stats['trade_count']
            fill_rate = stats['fill_rate']
        else:
            total_pnl = agent.total_pnl
            n_trades = len(agent.trades)
            fill_rate = agent.inventory / self.target_quantity
            
        win_rate = np.mean([p > 0 for p in pnls]) if pnls else 0
        avg_pnl = np.mean(pnls) if pnls else 0
        
        # Max drawdown
        if pnls:
            cumulative = np.cumsum(pnls)
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = running_max - cumulative
            max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        else:
            max_drawdown = 0
            
        # Sharpe ratio
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252)
        else:
            sharpe = 0
            
        return BacktestResult(
            name=agent.__class__.__name__,
            total_pnl=total_pnl,
            n_trades=n_trades,
            win_rate=win_rate,
            avg_pnl_per_trade=avg_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            fill_rate=fill_rate
        )
        
    def run(
        self,
        df: pd.DataFrame,
        price_col: str = 'close',
        n_runs: int = 5
    ) -> Dict:
        """
        Run comparison backtests.
        
        Args:
            df: Historical data
            price_col: Price column name
            n_runs: Number of runs for averaging
            
        Returns:
            Comparison results
        """
        if price_col not in df.columns:
            # Find price column
            for col in ['close', 'Close', 'price', 'Price']:
                if col in df.columns:
                    price_col = col
                    break
                    
        agents = {
            'TWAP': BaselineAgent(self.target_quantity, 'twap'),
            'VWAP': BaselineAgent(self.target_quantity, 'vwap'),
            'Aggressive': BaselineAgent(self.target_quantity, 'aggressive'),
            'StochasticControl': StochasticControlAgent(self.target_quantity)
        }
        
        results = {name: [] for name in agents}
        
        print(f"Running {n_runs} backtest iterations...")
        
        for run in range(n_runs):
            np.random.seed(42 + run)
            
            for name, agent in agents.items():
                result = self._run_single_backtest(df, agent, price_col)
                results[name].append(result)
                
        # Average results
        self.results = {}
        for name, runs in results.items():
            self.results[name] = {
                'total_pnl': np.mean([r.total_pnl for r in runs]),
                'n_trades': np.mean([r.n_trades for r in runs]),
                'win_rate': np.mean([r.win_rate for r in runs]),
                'avg_pnl_per_trade': np.mean([r.avg_pnl_per_trade for r in runs]),
                'max_drawdown': np.mean([r.max_drawdown for r in runs]),
                'sharpe_ratio': np.mean([r.sharpe_ratio for r in runs]),
                'fill_rate': np.mean([r.fill_rate for r in runs])
            }
            
        return self.results
        
    def get_summary(self) -> pd.DataFrame:
        """Get summary DataFrame."""
        return pd.DataFrame(self.results).T
        
    def generate_report(self) -> str:
        """Generate comparison report."""
        summary = self.get_summary()
        
        lines = []
        lines.append("=" * 70)
        lines.append("BACKTEST COMPARISON REPORT")
        lines.append("=" * 70)
        
        # Header
        lines.append(f"\n{'Strategy':<20} {'PnL':>12} {'Sharpe':>10} {'WinRate':>10} {'FillRate':>10}")
        lines.append("-" * 70)
        
        # Sort by PnL
        summary = summary.sort_values('total_pnl', ascending=False)
        
        for name, row in summary.iterrows():
            lines.append(
                f"{name:<20} {row['total_pnl']:>12.2f} {row['sharpe_ratio']:>10.2f} "
                f"{row['win_rate']:>10.1%} {row['fill_rate']:>10.1%}"
            )
            
        # Winner
        winner = summary.index[0]
        lines.append(f"\nWinner: {winner}")
        
        # Improvement
        baseline_pnl = summary.loc['TWAP', 'total_pnl']
        sc_pnl = summary.loc['StochasticControl', 'total_pnl']
        improvement = (sc_pnl - baseline_pnl) / abs(baseline_pnl) * 100 if baseline_pnl != 0 else 0
        lines.append(f"Improvement vs TWAP: {improvement:+.1f}%")
        
        return "\n".join(lines)


def run_quick_comparison(df: pd.DataFrame) -> Dict:
    """Quick comparison function."""
    comparison = BacktestComparison()
    return comparison.run(df)


if __name__ == '__main__':
    # Test with synthetic data
    np.random.seed(42)
    
    n = 500
    df = pd.DataFrame({
        'close': 8500 + np.cumsum(np.random.randn(n) * 2)
    })
    
    comparison = BacktestComparison()
    results = comparison.run(df, n_runs=3)
    print(comparison.generate_report())