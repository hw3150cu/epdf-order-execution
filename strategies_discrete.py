"""
Discrete Optimization Strategy - Integer levels, 0.1 weight increments
Uses trust-constr optimizer with post-processing to enforce constraints
"""

import pandas as pd
import numpy as np
from collections import deque
from scipy.optimize import minimize
from typing import List, Tuple


class ePDFBuilder:
    """Track range_dn and price_movement per state"""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        
        self.epdfs_range_dn = {
            "Low": deque(maxlen=window_size),
            "High": deque(maxlen=window_size)
        }
        
        self.epdfs_movement = {
            "Low": deque(maxlen=window_size),
            "High": deque(maxlen=window_size)
        }
    
    def update(self, state: str, range_dn: float, movement: float):
        """Update ePDF with new data"""
        if state in self.epdfs_range_dn:
            self.epdfs_range_dn[state].append(range_dn)
            self.epdfs_movement[state].append(movement)
    
    def get_fill_prob(self, state: str, level: float) -> float:
        """P(range_dn >= level)"""
        if state not in self.epdfs_range_dn or len(self.epdfs_range_dn[state]) < 5:
            return 0.0
        data = list(self.epdfs_range_dn[state])
        return np.mean(np.array(data) >= level)
    
    def get_expected_close(self, state: str) -> float:
        """Expected close = mean(close - open)"""
        if state not in self.epdfs_movement or len(self.epdfs_movement[state]) < 5:
            return 0.0
        return np.mean(list(self.epdfs_movement[state]))


class DiscreteOptimizer:
    """
    Optimize with constraints:
    - Levels: integers (0, 1, 2, ..., max_level)
    - Weights: multiples of 0.1, sum to 1.0
    
    Uses trust-constr for continuous optimization, then rounds to discrete values.
    """
    
    def __init__(self, window_size: int = 60, 
                 min_penalty: float = 5.0,
                 max_level: float = 10.0):
        self.window_size = window_size
        self.min_penalty = min_penalty
        self.max_level = max_level
        self.epdf = ePDFBuilder(window_size)
    
    def get_limits(self, df: pd.DataFrame, i: int, 
                   tick: float) -> List[Tuple[float, float]]:
        """Get optimal (level, weight) tuples with discrete constraints"""
        if i < 1:
            return [(0., 0.33), (1., 0.33), (2., 0.34)]
        
        row = df.iloc[i]
        state = row['prev_state']
        
        # Update ePDF
        prev = df.iloc[i-1]
        self.epdf.update(state, prev['range_dn_ticks'], prev['close'] - prev['open'])
        
        # Need history
        if len(self.epdf.epdfs_range_dn[state]) < 10:
            return [(0., 0.33), (1., 0.33), (2., 0.34)]
        
        # Calculate penalty
        expected_close = self.epdf.get_expected_close(state)
        penalty_ticks = (expected_close - row['open']) / tick
        penalty = max(self.min_penalty, penalty_ticks)
        
        def objective(x):
            p1, p2, p3, w1, w2, w3 = x
            levels = [p1, p2, p3]
            weights = [w1, w2, w3]
            
            # Fill probs
            probs = [self.epdf.get_fill_prob(state, l) for l in levels]
            
            # Utility
            fill_prob = sum(w*pr for w, pr in zip(weights, probs))
            reward = sum(w*pr*l for w, pr, l in zip(weights, probs, levels))
            miss_penalty = (1. - fill_prob) * penalty
            return -(reward - miss_penalty)
        
        # Optimize with trust-constr (more robust than SLSQP)
        bounds = [(0., self.max_level)]*3 + [(0., 1.)]*3
        
        # Constraint: weights sum to 1.0
        cons = {'type': 'eq', 'fun': lambda x: sum(x[3:6]) - 1.}
        
        result = minimize(
            objective,
            [0., 1., 2., 1./3., 1./3., 1./3.],
            method='trust-constr',
            bounds=bounds,
            constraints=cons,
            options={'gtol': 1e-6, 'maxiter': 100, 'verbose': 0}
        )
        
        if result.success and result.x is not None:
            # Apply DISCRETE constraints
            # 1. Round levels to integers
            levels_cont = result.x[:3]
            levels_int = [int(np.round(l)) for l in levels_cont]
            levels_int = [max(0, min(l, int(self.max_level))) for l in levels_int]
            
            # Sort levels ascending
            levels_int.sort()
            
# 2. Round weights to 0.1 increments
            weights = result.x[3:]
            
            # First normalize to sum to 1
            if weights.sum() > 0:
                weights = weights / weights.sum()
            
            # Round to 0.1
            weights = np.round(weights, 1)
            
            # Adjust to ensure exactly 1.0
            total = weights.sum()
            if total != 1.0:
                idx = np.argmax(weights)
                weights[idx] += (1.0 - total)
                weights = np.round(weights, 1)
            
            return [(float(levels_int[0]), float(weights[0])), 
                   (float(levels_int[1]), float(weights[1])), 
                   (float(levels_int[2]), float(weights[2]))]
        else:
            print(f"Optimization failed at bar {i}, state={state}")
            return [(0., 0.33), (1., 0.33), (2., 0.34)]