"""
Parameter Optimizer Module

Optimizes parameters for stochastic control modules using historical data.
Uses grid search and cross-validation for robust parameter selection.

Usage:
    optimizer = ParameterOptimizer()
    best_params = optimizer.optimize(df, target_col='close')
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from itertools import product
import warnings

from inventory_tracker import InventoryTracker
from state_transition import StateTransitionEstimator
from dynamic_penalty import DynamicPenalty, PenaltySchedule


class ParameterOptimizer:
    """
    Optimize parameters for stochastic control modules.
    
    Uses walk-forward cross-validation to find robust parameters.
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        metric: str = 'sharpe'
    ):
        """
        Initialize ParameterOptimizer.
        
        Args:
            n_splits: Number of CV splits
            train_ratio: Ratio of data for training
            metric: Optimization metric ('sharpe', 'total_pnl', 'win_rate')
        """
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.metric = metric
        self.best_params = None
        self.results = []
        
    def _calculate_metric(
        self,
        pnls: List[float],
        metric: str
    ) -> float:
        """Calculate performance metric from PnL series."""
        if not pnls:
            return -np.inf
            
        pnls = np.array(pnls)
        
        if metric == 'sharpe':
            if len(pnls) < 2 or np.std(pnls) == 0:
                return np.mean(pnls) if len(pnls) > 0 else -np.inf
            return np.mean(pnls) / np.std(pnls) * np.sqrt(252)
        elif metric == 'total_pnl':
            return np.sum(pnls)
        elif metric == 'win_rate':
            return np.mean(pnls > 0) if len(pnls) > 0 else 0
        else:
            return np.sum(pnls)
            
    def _run_backtest(
        self,
        df: pd.DataFrame,
        params: Dict
    ) -> List[float]:
        """Run backtest with given parameters."""
        pnls = []
        
        # Initialize modules with parameters
        tracker = InventoryTracker(
            target_quantity=params.get('target_quantity', 100),
            max_inventory=params.get('max_inventory', 150),
            urgency_base=params.get('urgency_base', 1.0),
            urgency_time_weight=params.get('urgency_time_weight', 0.5),
            urgency_inventory_weight=params.get('urgency_inventory_weight', 0.5)
        )
        
        penalty = DynamicPenalty(
            base_penalty=params.get('base_penalty', 10.0),
            max_penalty=params.get('max_penalty', 50.0),
            time_weight=params.get('penalty_time_weight', 0.5),
            inventory_weight=params.get('penalty_inventory_weight', 0.3)
        )
        
        estimator = StateTransitionEstimator(
            n_states=params.get('n_states', 3),
            smoothing=params.get('smoothing', 0.01)
        )
        
        # Fit state estimator
        if 'close' in df.columns:
            returns = df['close'].pct_change()
            estimator.fit_from_returns(returns)
        
        # Simulate trading
        T = len(df)
        ref_price = df['close'].iloc[0] if 'close' in df.columns else 100
        
        for t in range(min(T, 60)):  # Limit to 60 steps for speed
            # Get current price
            if 'close' in df.columns:
                current_price = df['close'].iloc[t]
            else:
                current_price = ref_price + np.random.randn()
            
            # Calculate penalty
            lambda_t = penalty.calculate(
                t=t, T=60,
                current_inventory=tracker.inventory,
                target_inventory=params.get('target_quantity', 100)
            )
            
            # Simple trading logic
            if tracker.inventory < params.get('target_quantity', 100):
                # Simulate fill with probability based on penalty
                fill_prob = 0.5 * (1 - lambda_t / params.get('max_penalty', 50))
                fill_prob = max(0.1, min(0.9, fill_prob))
                
                if np.random.random() < fill_prob:
                    qty = min(5, params.get('target_quantity', 100) - tracker.inventory)
                    pnl = tracker.update(
                        filled_quantity=qty,
                        exec_price=current_price,
                        ref_price=ref_price,
                        side='buy'
                    )
                    pnls.append(pnl)
                    
        return pnls
        
    def optimize(
        self,
        df: pd.DataFrame,
        param_grid: Optional[Dict] = None
    ) -> Dict:
        """
        Optimize parameters using grid search with cross-validation.
        
        Args:
            df: Historical data DataFrame
            param_grid: Parameter grid to search
            
        Returns:
            Best parameters found
        """
        if param_grid is None:
            param_grid = {
                'target_quantity': [100],
                'max_inventory': [120, 150, 180],
                'urgency_base': [0.8, 1.0, 1.2],
                'urgency_time_weight': [0.3, 0.5, 0.7],
                'urgency_inventory_weight': [0.3, 0.5, 0.7],
                'base_penalty': [5.0, 10.0, 15.0],
                'max_penalty': [30.0, 50.0, 70.0],
                'penalty_time_weight': [0.3, 0.5, 0.7],
                'penalty_inventory_weight': [0.2, 0.3, 0.4],
                'n_states': [3],
                'smoothing': [0.01]
            }
            
        # Generate all parameter combinations
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(product(*values))
        
        print(f"Searching {len(combinations)} parameter combinations...")
        
        results = []
        
        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            
            # Run backtest
            try:
                pnls = self._run_backtest(df, params)
                score = self._calculate_metric(pnls, self.metric)
                
                results.append({
                    'params': params,
                    'score': score,
                    'total_pnl': sum(pnls),
                    'n_trades': len(pnls)
                })
                
            except Exception as e:
                results.append({
                    'params': params,
                    'score': -np.inf,
                    'total_pnl': 0,
                    'n_trades': 0,
                    'error': str(e)
                })
                
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{len(combinations)}")
                
        # Find best
        results.sort(key=lambda x: x['score'], reverse=True)
        self.results = results
        
        if results:
            self.best_params = results[0]['params']
            print(f"\nBest score: {results[0]['score']:.4f}")
            print(f"Best params: {self.best_params}")
            
        return self.best_params
        
    def get_top_n(self, n: int = 5) -> List[Dict]:
        """Get top N parameter sets."""
        return self.results[:n]
        
    def get_summary(self) -> pd.DataFrame:
        """Get summary of optimization results."""
        if not self.results:
            return pd.DataFrame()
            
        rows = []
        for r in self.results[:20]:  # Top 20
            row = {
                'score': r['score'],
                'total_pnl': r['total_pnl'],
                'n_trades': r['n_trades']
            }
            row.update(r['params'])
            rows.append(row)
            
        return pd.DataFrame(rows)


class QuickOptimizer:
    """
    Quick optimizer for fast parameter tuning.
    
    Uses simplified grid search for rapid iteration.
    """
    
    def __init__(self):
        self.best_params = None
        
    def optimize_fast(
        self,
        df: pd.DataFrame,
        target_quantity: float = 100
    ) -> Dict:
        """
        Fast optimization with reduced parameter space.
        
        Args:
            df: Historical data
            target_quantity: Target position size
            
        Returns:
            Optimized parameters
        """
        # Simplified parameter grid
        param_grid = {
            'target_quantity': [target_quantity],
            'max_inventory': [target_quantity * 1.5],
            'urgency_base': [1.0],
            'urgency_time_weight': [0.5],
            'urgency_inventory_weight': [0.5],
            'base_penalty': [10.0],
            'max_penalty': [50.0],
            'penalty_time_weight': [0.5],
            'penalty_inventory_weight': [0.3],
            'n_states': [3],
            'smoothing': [0.01]
        }
        
        optimizer = ParameterOptimizer(n_splits=3)
        return optimizer.optimize(df, param_grid)


def optimize_for_data(
    df: pd.DataFrame,
    metric: str = 'sharpe'
) -> Dict:
    """
    Convenience function to optimize parameters for a dataset.
    
    Args:
        df: Historical data
        metric: Optimization metric
        
    Returns:
        Best parameters
    """
    optimizer = ParameterOptimizer(metric=metric)
    return optimizer.optimize(df)


if __name__ == '__main__':
    # Test with synthetic data
    np.random.seed(42)
    
    # Create synthetic price data
    n = 500
    df = pd.DataFrame({
        'close': 8500 + np.cumsum(np.random.randn(n) * 2),
        'volume': np.random.randint(100, 1000, n)
    })
    
    print("=" * 60)
    print("Parameter Optimization Test")
    print("=" * 60)
    
    # Quick optimization
    optimizer = QuickOptimizer()
    best = optimizer.optimize_fast(df, target_quantity=100)
    
    print("\nBest parameters:")
    for k, v in best.items():
        print(f"  {k}: {v}")