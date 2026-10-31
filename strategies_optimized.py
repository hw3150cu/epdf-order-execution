"""
Optimized Utility-Based Strategy with scipy.optimize
Optimizes BOTH price levels AND weights simultaneously
Uses 2-regime approach: Low vs High
"""

import pandas as pd
import numpy as np
from collections import deque
from scipy.optimize import minimize
from typing import List, Tuple


class ePDFBuilder:
    """
    Enhanced ePDF builder tracking:
    - range_dn: For fill probability
    - close_prices: For expected close prediction
    """
    
    def __init__(self, window_size: int = 60):
        """Initialize ePDF builder (2-regime)"""
        self.window_size = window_size
        
        # Track range_dn for fill probabilities
        self.epdfs_range_dn = {
            "Low": deque(maxlen=window_size),
            "High": deque(maxlen=window_size)
        }
        
        # Track close prices for expected close prediction
        self.epdfs_close_prices = {
            "Low": deque(maxlen=window_size),
            "High": deque(maxlen=60)
        }
    
    def update(self, state: str, range_dn: float, close_price: float):
        """Update ePDF with new observations"""
        if state in self.epdfs_range_dn:
            self.epdfs_range_dn[state].append(range_dn)
            self.epdfs_close_prices[state].append(close_price)
    
    def get_fill_probability(self, state: str, price_level: float) -> float:
        """
        Get fill probability: P(range_dn >= price_level)
        
        Args:
            state: Volatility state
            price_level: Price level in ticks from open
        
        Returns:
            Probability that price drops enough to fill
        """
        if state not in self.epdfs_range_dn or len(self.epdfs_range_dn[state]) < 5:
            return 0.0
        
        data = np.array(list(self.epdfs_range_dn[state]))
        # P(range_dn >= level) = fraction where range drops at least this much
        return np.mean(data >= price_level)
    
    def get_expected_close(self, state: str) -> float:
        """
        Get expected close price for a state.
        
        Args:
            state: Volatility state
        
        Returns:
            Expected close price (mean of historical closes)
        """
        if state not in self.epdfs_close_prices or len(self.epdfs_close_prices[state]) < 5:
            return 0.0
        
        data = np.array(list(self.epdfs_close_prices[state]))
        return np.mean(data)


class UtilityOptimizerStrategy:
    """
    Utility-based strategy optimizing BOTH price levels AND weights simultaneously.
    
    Optimizes:
    - p1, p2, p3: Price levels (ticks from open)
    - w1, w2, w3: Weights (allocation, sum to 1)
    
    Using scipy.optimize.minimize with SLSQP method.
    """
    
    def __init__(
        self,
        window_size: int = 60,
        min_penalty_ticks: float = 5.0,
        max_price_level: float = 10.0
    ):
        """
        Initialize strategy.
        
        Args:
            window_size: ePDF window size
            min_penalty_ticks: Conservative floor for penalty (ticks)
            max_price_level: Maximum price level to optimize (ticks)
        """
        self.window_size = window_size
        self.min_penalty_ticks = min_penalty_ticks
        self.max_price_level = max_price_level
        
        # Initialize ePDF builder
        self.epdf_builder = ePDFBuilder(window_size=window_size)
    
    def get_limit_prices(
        self,
        df: pd.DataFrame,
        current_bar: int,
        tick_size: float
    ) -> List[Tuple[float, float]]:
        """
        Get optimized limit orderszek orders with optimal price levels AND weights.
        
        Args:
            df: DataFrame with OHLC and state
           : current_bar: Current bar index
            tick_size: Contract tick size
        
        Returns:
            List of (price_level_ticks, weight) tuples
        """
        # Default: levels [0, 1, 2], equal weights
        if current_bar < 1:
            return [(0.0, 1.0/3), (1.0, 1.0/3), (2.0, 1.0/3)]
        
        row = df.iloc[current_bar]
        prev_state = row['prev_state']
        
        # Update ePDF with previous bar
        prev_bar = df.iloc[current_bar - 1]
        self.epdf_builder.update(
            prev_state,
            prev_bar['range_dn_ticks'],
            prev_bar['close']
        )
        
        # Need enough history
        if len(self.epdf_builder.epdfs_range_dn[prev_state]) < 10:
            return [(0.0, 1.0/3), (1.0, 1.0/3), (2.0, 1.0/3)]
        
        # Calculate expected close
        expected_close = self.epdf_builder.get_expected_close(prev_state)
        expected_penalty_ticks = (expected_close - row['open']) / tick_size
        penalty_ticks = max(self.min_penalty_ticks, expected_penalty_ticks)
        
        # Define objective function for optimization
        def objective_function(x):
            """
            Negative utility to minimize.
            x = [p1, p2, p3, w1, w2, w3]
            """
            p1, p2, p3, w1, w2, w3 = x
            price_levels = [p1, p2, p3]
            weights = [w1, w2, w3]
            
            # Get fill probabilities for each level
            fill_probs = [
                self.epdf_builder.get_fill_probability(prev_state, level)
                for level in price_levels
            ]
            
            # Weighted fill probability
            weighted_fill_prob = 0.0
            for i in range(3):
                weighted_fill_prob += weights[i] * fill_probs[i]
            
            # Calculate utility
            # Reward: Σ(w_i × P_i × level_i)
            reward = 0.0
            for i in range(3):
                reward += weights[i] * fill_probs[i] * price_levels[i]
            
            # Penalty: (1 - Σ(w_i × P_i)) × penalty_ticks
            penalty = (1.0 - weighted_fill_prob) * penalty_ticks
            
            # Utility = Reward - Penalty
            utility = reward - penalty
            
            # Return negative utility for minimization
            return -utility
        
        # Constraints: w1 + w2 + w3 = 1.0
        constraints = ({
            'type': 'eq',
            'fun': lambda x: x[3] + x[4] + x[5] - 1.0
        })
        
        # Bounds: p1, p2, p3 >= 0, p1, p2, p3 <= max_level
        #         w1, w2, w3 >= 0, w1, w2, w3 <= 1
        bounds = [
            (0.0, self.max_price_level),  # p1
            (0.0, self.max_price_level),  # p2
            (0.0, self.max_price_level),  # p3
            (0.0, 1.0),  # w1
            (0.0, 1.0),  # w2
            (0.0, 1.0),  # w3
        ]
        
        # Initial guess: [p1=0, p2=1, p3=2, w1=1/3, w2=1/3, w3=1/3]
        x0 = [0.0, 1.0, 2.0, 1.0/3, 1.0/3, 1.0/3]
        
        # Optimize using scipy with trust-constr method
        result = minimize(
            objective_function,
            x0,
            method='trust-constr',
            bounds=bounds,
            constraints=constraints,
            options={'disp': False, 'maxiter': 1000}
        )
        
        if result.success:
            p1, p2, p3, w1, w2, w3 = result.x
            # Normalize weights
            total_w = w1 + w2 + w3
            if total_w > 0:
                w1, w2, w3 = w1/total_w, w2/total_w, w3/total_w
            return [(p1, w1), (p2, w2), (p3, w3)]
        else:
            # Fallback to default
            return [(0.0, 1.0/3), (1.0, 1.0/3), (2.0, 1.0/3)]