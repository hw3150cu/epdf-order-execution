"""
Optimized Utility-Based Strategy with scipy.optimize
2-regime approach: Low vs High
Optimizes price levels [p1,p2,p3] AND weights [w1,w2,w3]
"""

import warnings
# Suppress delta_grad warnings (normal for linear-like utility functions)
# This warning appears when the objective function is nearly linear, which is expected
# for utility-based optimization with step-based fill probabilities
warnings.filterwarnings('ignore', message='.*delta_grad.*', category=UserWarning)

import pandas as pd
import numpy as np
from scipy.optimize import minimize
from typing import List, Tuple


class ePDFBuilder:
    """Track range_dn and price_movement (close - open) per state
    
    OPTIMIZATION: Uses sorted numpy arrays for O(1) fill probability lookup
    instead of O(n) deque conversions.
    """
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        
        # Use circular buffers with numpy arrays for O(1) updates and O(log n) lookups
        self.range_dn_data = {
            "Low": np.zeros(window_size),
            "High": np.zeros(window_size)
        }
        self.range_up_data = {
            "Low": np.zeros(window_size),
            "High": np.zeros(window_size)
        }
        self.movement_data = {
            "Low": np.zeros(window_size),
            "High": np.zeros(window_size)
        }
        self.ptrs = {"Low": 0, "High": 0}  # Circular buffer pointers
        self.counts = {"Low": 0, "High": 0}  # Number of valid entries
        
        # Cache sorted arrays for fast probability lookup
        self.sorted_range_dn = {
            "Low": np.array([]),
            "High": np.array([])
        }
        self.sorted_range_up = {
            "Low": np.array([]),
            "High": np.array([])
        }
    
    def update(self, state: str, range_dn: float, range_up: float, movement: float):
        """Update ePDF with new data (O(1) operation)"""
        if state not in self.range_dn_data:
            return
        
        ptr = self.ptrs[state]
        self.range_dn_data[state][ptr] = range_dn
        self.range_up_data[state][ptr] = range_up
        self.movement_data[state][ptr] = movement
        
        # Update circular pointer
        self.ptrs[state] = (ptr + 1) % self.window_size
        
        # Update count (until buffer is full)
        if self.counts[state] < self.window_size:
            self.counts[state] += 1
        
        # Re-sort for fast lookup (only O(n log n) on update, not on query)
        if self.counts[state] >= 5:
            valid_dn = self.range_dn_data[state][:self.counts[state]]
            valid_up = self.range_up_data[state][:self.counts[state]]
            self.sorted_range_dn[state] = np.sort(valid_dn)
            self.sorted_range_up[state] = np.sort(valid_up)
    
    def get_expected_range_dn(self, state: str) -> float:
        """Get expected downward price movement (for buy order penalty)"""
        if state not in self.range_dn_data or self.counts[state] < 5:
            return 0.0
        valid_data = self.range_dn_data[state][:self.counts[state]]
        return np.mean(valid_data)
    
    def get_expected_range_up(self, state: str) -> float:
        """Get expected upward price movement (for sell order penalty)"""
        if state not in self.range_up_data or self.counts[state] < 5:
            return 0.0
        valid_data = self.range_up_data[state][:self.counts[state]]
        return np.mean(valid_data)
    
    def get_fill_prob(self, state: str, level: float, direction: str = 'buy') -> float:
        """Get fill probability for a limit order
        
        For buy orders: P(range_dn >= level) - probability price goes down enough
        For sell orders: P(range_up >= level) - probability price goes up enough
        
        O(log n) using sorted array and searchsorted
        """
        if direction == 'buy':
            if state not in self.sorted_range_dn or len(self.sorted_range_dn[state]) < 5:
                return 0.0
            
            sorted_data = self.sorted_range_dn[state]
        else:  # sell
            if state not in self.sorted_range_up or len(self.sorted_range_up[state]) < 5:
                return 0.0
            
            sorted_data = self.sorted_range_up[state]
        
        # Find first index where value >= level
        idx = np.searchsorted(sorted_data, level, side='left')
        count_ge = len(sorted_data) - idx
        return count_ge / len(sorted_data)
    
    def get_expected_close(self, state: str) -> float:
        """Expected close = mean(close_prices) - O(1) with cached data"""
        if state not in self.movement_data or self.counts[state] < 5:
            return 0.0
        
        valid_data = self.movement_data[state][:self.counts[state]]
        return np.mean(valid_data)


class UtilityOptimizer:
    """
    Optimize: U = sum(w_i * P_i * p_i) - (1 - sum(w_i * P_i)) * penalty
    Variables: [p1, p2, p3, w1, w2, w3]
    """
    
    def __init__(self, window_size: int = 60, 
                 min_penalty: float = 5.0,
                 max_level: float = 10.0):
        self.window_size = window_size
        self.min_penalty = min_penalty
        self.max_level = max_level
        self.epdf = ePDFBuilder(window_size)
        
        # Cache for direction-aware penalty
        self._cached_direction = None
        self._cached_penalty = None
    
    def _objective(self, x, state, direction, penalty):
        """
        Objective function for optimization (outside get_limits for better performance)
        
        Args:
            x: [p1, p2, p3, w1, w2, w3] - levels and weights
            state: Current market state
            direction: 'buy' or 'sell'
            penalty: Penalty for missing fills
        
        Returns:
            Negative utility (to minimize)
        """
        p1, p2, p3, w1, w2, w3 = x
        levels = [p1, p2, p3]
        weights = [w1, w2, w3]
        
        # Fill probs - use direction to determine which side to optimize
        probs = [self.epdf.get_fill_prob(state, l, direction) for l in levels]
        
        # Utility
        fill_prob = sum(w*pr for w, pr in zip(weights, probs))
        reward = sum(w*pr*l for w, pr, l in zip(weights, probs, levels))
        miss_penalty = (1. - fill_prob) * penalty
        return -(reward - miss_penalty)
    
    def get_limits(self, df: pd.DataFrame, i: int, 
                   tick: float, direction: str = 'buy') -> List[Tuple[float, float]]:
        """Get optimal (level, weight) tuples for a specific direction
        
        Args:
            df: Dataframe with price data
            i: Current index
            tick: Tick size
            direction: 'buy' or 'sell' - determines which side to optimize
        
        Returns:
            List of (level, weight) tuples for limit orders
        """
        if i < 1:
            return [(0., 1./3.), (1., 1./3.), (2., 1./3.)]
        
        row = df.iloc[i]
        state = row['prev_state']
        
        # Update ePDF
        prev = df.iloc[i-1]
        self.epdf.update(state, prev['range_dn_ticks'], prev['range_up_ticks'], prev['close'])
        
        # Need history
        if self.epdf.counts.get(state, 0) < 10:
            return [(0., 1./3.), (1., 1./3.), (2., 1./3.)]
        
        # Calculate direction-aware penalty
        # For buy orders: penalty = expected upward movement (if price goes up, we miss)
        # For sell orders: penalty = expected downward movement (if price goes down, we miss)
        if direction == 'buy':
            expected_movement = self.epdf.get_expected_range_up(state)
        else:  # sell
            expected_movement = self.epdf.get_expected_range_dn(state)
        
        penalty = max(self.min_penalty, expected_movement)
        
        # Multi-start SLSQP for global optimum
        bounds = [(0., self.max_level)]*3 + [(0., 1.)]*3
        cons = {'type': 'eq', 'fun': lambda x: sum(x[3:6]) - 1.}
        
        # Pre-defined starting points (spread across parameter space)
        starting_points = [
            [0., 1., 2., 1./3., 1./3., 1./3.],      # Default
            [0., 0.5, 1., 1./3., 1./3., 1./3.],      # Tight levels
            [0., 2., 4., 1./3., 1./3., 1./3.],      # Spread out
            [1., 3., 5., 1./3., 1./3., 1./3.],      # Wider spread
            [0., 1., 2., 0.5, 0.5, 0.0],            # Biased weights
            [2., 4., 6., 1./3., 1./3., 1./3.],      # High levels
        ]
        
        best_result = None
        best_obj = float('inf')
        
        # Run SLSQP from each starting point
        for x0 in starting_points:
            result = minimize(
                self._objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=cons,
                options={'disp': False, 'ftol': 1e-6, 'maxiter': 200},
                args=(state, direction, penalty)
            )
            
            if result.success and result.fun < best_obj:
                best_obj = result.fun
                best_result = result
        
        if best_result is not None:
            p = best_result.x[:3]
            w = best_result.x[3:]
            w = w / w.sum()
            return [(p[0], w[0]), (p[1], w[1]), (p[2], w[2])]
        else:
            return [(0., 1./3.), (1., 1./3.), (2., 1./3.)]