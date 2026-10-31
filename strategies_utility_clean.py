"""
Utility-Based Optimization Strategy
Maximizes utility function across 3 price levels
"""

import pandas as pd
import numpy as np
from collections import deque
from epdf import ePDFBuilder


class UtilityOptimizerStrategy:
    """
    Utility-based limit order strategy optimizing weight allocation.
    
    Optimizes weights across 3 price levels to maximize:
    Utility = Σ(weight_i × P(reach level_i) × savings_i) - P(no fills) × penalty
    
    Penalty: 10 ticks for NQ futures
    """
    
    def __init__(
        self,
        window_size: int = 60,
        penalty_ticks: float = 10.0,
        price_levels: list = [0.0, 1.0, 2.0]  # ticks from close: close, close-1, close-2
    ):
        """
        Initialize strategy.
        
        Args:
            window_size: ePDF window size
            penalty_ticks: Penalty for missing all fills
            price_levels: 3 price levels in ticks from close
        """
        self.window_size = window_size
        self.penalty_ticks = penalty_ticks
        self.price_levels = price_levels
        
        # Initialize ePDF builder
        self.epdf_builder = ePDFBuilder(window_size=window_size)
    
    def get_limit_prices(
        self,
        df: pd.DataFrame,
        current_bar: int
    ) -> list:
        """
        Get limit orders with optimized weights using utility function.
        
        Args:
            df: DataFrame with OHLC and state
            current_bar: Current bar index
        
        Returns:
            List of (price_level_ticks, weight) tuples for optimized allocation
        """
        if current_bar < 1:
            # Default: equal weights
            return [(level, 1.0/len(self.price_levels)) for level in self.price_levels]
        
        row = df.iloc[current_bar]
        prev_state = row['prev_state']
        
        # Update ePDF with previous bar
        prev_bar = df.iloc[current_bar - 1]
        self.epdf_builder.update(prev_state, prev_bar['range_dn_ticks'])
        
        # Need enough history
        if len(self.epdf_builder.epdfs[prev_state]) < 10:
            return [(level, 1.0/len(self.price_levels)) for level in self.price_levels]
        
        # Get cumulative probabilities for each price level
        cum_probs = self.epdf_builder.get_cumulative_probabilities(
            prev_state,
            self.price_levels
        )
        
        # Optimize weights using utility function
        optimal_weights = self._optimize_weights(cum_probs, self.price_levels)
        
        return [(level, weight) for level, weight in zip(self.price_levels, optimal_weights)]
    
    def _optimize_weights(self, cum_probs: list, price_levels: list) -> list:
        """
        Optimize weights to maximize utility.
        
        Utility = Σ(weight_i × P_i × savings_i) - (1 - max(P_i)) × penalty
        
        Where:
        - P_i = P(reach level_i) = cum_probs[i]
        - savings_i = price_levels[i] (ticks saved if filled at level_i)
        - max(P_i) = probability of filling at least one order
        
        Args:
            cum_probs: Cumulative probabilities for each level
            price_levels: Price levels in ticks
        
        Returns:
            Optimal weights [w1, w2, w3] that sum to 1.0
        """
        n_levels = len(price_levels)
        best_utility = -float('inf')
        best_weights = [1.0/n_levels] * n_levels
        
        # Grid search for speed (step size = 0.1)
        step = 0.1
        weight_values = [round(i * step, 1) for i in range(0, int(1.0/step) + 1)]
        
        # Generate weight combinations that sum to 1.0
        for w1 in weight_values:
            for w2 in weight_values:
                w3 = 1.0 - w1 - w2
                if w3 < 0:
                    continue
                
                weights = [w1, w2, w3]
                
                # Calculate utility
                utility = 0.0
                for i in range(n_levels):
                    utility += weights[i] * cum_probs[i] * price_levels[i]
                
                # Penalty for missing all fills
                max_fill_prob = max(cum_probs)
                penalty = (1.0 - max_fill_prob) * self.penalty_ticks
                
                utility -= penalty
                
                # Track best
                if utility > best_utility:
                    best_utility = utility
                    best_weights = weights.copy()
        
        return best_weights