"""
Strategies Module
Strategy implementations for order execution
"""

import pandas as pd
import numpy as np
from collections import deque


class LimitOrderStrategy:
    """
    Mode-based limit order strategy using ePDF peaks.
    Places 50/50 orders at the two highest probability points (modes).
    """
    
    def __init__(
        self,
        m: int = 20,
        low_thresh: float = 1.5,
        high_thresh: float = 3.0,
        window_size: int = 60
    ):
        """
        Initialize strategy.
        
        Args:
            m: EWMA half-life
            low_thresh: Low volatility threshold
            high_thresh: High volatility threshold
            window_size: ePDF window size
        """
        self.m = m
        self.low_thresh = low_thresh
        self.high_thresh = high_thresh
        self.window_size = window_size
        
        # Initialize ePDFs
        self.epdfs = {
            "Low": deque(maxlen=window_size),
            "Med": deque(maxlen=window_size),
            "High": deque(maxlen=window_size)
        }
    
    def get_limit_prices(
        self,
        df: pd.DataFrame,
        current_bar: int
    ) -> list:
        """
        Get two limit order prices at distribution modes (50/50 split).
        
        Args:
            df: DataFrame with OHLC and state
            current_bar: Current bar index
        
        Returns:
            List of tuples (limit_price_ticks, weight) for top 2 modes
        """
        if current_bar < 1:
            return [(0.0, 0.5), (0.0, 0.5)]
        
        row = df.iloc[current_bar]
        prev_state = row['prev_state']
        
        # Update ePDF with previous bar
        prev_bar = df.iloc[current_bar - 1]
        if prev_bar['vol_state'] in self.epdfs:
            self.epdfs[prev_bar['vol_state']].append(prev_bar['range_dn_ticks'])
        
        # Need enough history
        if len(self.epdfs[prev_state]) < 10:
            return [(0.0, 0.5), (0.0, 0.5)]
        
        # Get top 2 modes from distribution
        modes = self._get_top_modes(prev_state, n_modes=2)
        
        if len(modes) < 2:
            # Fallback to 0 if not enough data
            return [(0.0, 0.5), (0.0, 0.5)]
        
        # Return modes with 50/50 weight
        return [(modes[0], 0.5), (modes[1], 0.5)]
    
    def _get_top_modes(self, state: str, n_modes: int = 2) -> list:
        """Get top N modes from current ePDF"""
        if state not in self.epdfs or len(self.epdfs[state]) < 5:
            return []
        
        data = np.array(list(self.epdfs[state]))
        
        # Create histogram to find peaks
        n_bins = max(10, len(data) // 5)
        counts, bin_edges = np.histogram(data, bins=n_bins)
        
        # Find bin centers
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        
        # Get top N bins by count
        top_indices = np.argsort(counts)[-n_modes:][::-1]
        modes = [bin_centers[idx] for idx in top_indices]
        
        return modes


class TWAPStrategy:
    """Time-Weighted Average Price baseline"""
    
    def get_limit_price(self, df: pd.DataFrame, current_bar: int) -> float:
        """TWAP: slice equally over time"""
        # Simple: place at open (market order equivalent)
        return 0.0


class VWAPStrategy:
    """Volume-Weighted Average Price baseline"""
    
    def get_limit_price(self, df: pd.DataFrame, current_bar: int) -> float:
        """VWAP: weight by volume"""
        # Simple: place at open
        return 0.0


class UtilityOptimizerStrategy:
    """
    Utility-based limit order strategy optimizing weight allocation.
    
    Optimizes weights across 3 price levels to maximize:
    Utility = Σ(weight_i × P(reach level_i) × savings_i) - P(no fills) × penalty
    
    Penalty: 10 ticks for NQ futures
    """
    
    def __init__(
        self,
        m: int = 20,
        low_thresh: float = 1.5,
        high_thresh: float = 3.0,
        window_size: int = 60,
        penalty_ticks: float = 10.0,
        price_levels: list = [0.0, 1.0, 2.0]  # ticks from close: close, close-1, close-2
    ):
        """
        Initialize strategy.
        
        Args:
            m: EWMA half-life
            low_thresh: Low volatility threshold
            high_thresh: High volatility threshold
            window_size: ePDF window size
            penalty_ticks: Penalty for missing all fills
            price_levels: 3 price levels in ticks from close
        """
        self.m = m
        self.low_thresh = low_thresh
        self.high_thresh = high_thresh
        self.window_size = window_size
        self.penalty_ticks = penalty_ticks
        self.price_levels = price_levels
        
        # Initialize ePDFs
        from epdf import ePDFBuilder
        self.epdf_builder = ePDFBuilder(window_size=window_size)
    
    def get_limit_orders(
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