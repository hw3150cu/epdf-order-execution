"""
ePDF Module
Empirical Probability Density Functions for Limit Order Pricing
"""

import pandas as pd
import numpy as np
from collections import deque
from typing import Dict


class ePDFBuilder:
    """Build and manage empirical PDFs for each volatility state"""
    
    def __init__(self, window_size: int = 60):
        """Initialize ePDF builder"""
        self.window_size = window_size
        self.epdfs = {
            "Low": deque(maxlen=window_size),
            "Med": deque(maxlen=window_size),
            "High": deque(maxlen=window_size)
        }
    
    def update(self, state: str, value: float):
        """Update ePDF with new observation"""
        if state in self.epdfs:
            self.epdfs[state].append(value)
    
    def get_percentile(self, state: str, percentile: float) -> float:
        """Get percentile value from ePDF"""
        if state not in self.epdfs or len(self.epdfs[state]) == 0:
            return 0.0
        return np.percentile(list(self.epdfs[state]), percentile)
    
    def get_distribution(self, state: str) -> np.ndarray:
        """Get full distribution for a state"""
        if state not in self.epdfs or len(self.epdfs[state]) == 0:
            return np.array([])
        return np.array(self.epdfs[state])
    
    def get_top_modes(self, state: str, n_modes: int = 2) -> list:
        """
        Get top N modes (highest probability points) from ePDF.
        
        Args:
            state: Volatility state
            n_modes: Number of modes to return
        
        Returns:
            List of mode values (prices in ticks)
        """
        if state not in self.epdfs or len(self.epdfs[state]) < 5:
            return []
        
        data = np.array(list(self.epdfs[state]))
        
        # Create histogram to find peaks
        n_bins = max(10, len(data) // 5)  # Adaptive binning
        counts, bin_edges = np.histogram(data, bins=n_bins)
        
        # Find bin centers
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        
        # Get top N bins by count
        top_indices = np.argsort(counts)[-n_modes:][::-1]
        modes = [bin_centers[idx] for idx in top_indices]
        
        return modes
    
    def get_cumulative_probabilities(
        self,
        state: str,
        price_levels: list
    ) -> list:
        """
        Get cumulative probability of reaching each price level.
        P(low <= level) = fraction of historical bars where low <= level
        
        Args:
            state: Volatility state
            price_levels: List of price levels in ticks from close
        
        Returns:
            List of cumulative probabilities [P(reach level_1), P(reach level_2), ...]
        """
        if state not in self.epdfs or len(self.epdfs[state]) < 5:
            return [0.0] * len(price_levels)
        
        data = np.array(list(self.epdfs[state]))
        cum_probs = []
        
        for level in price_levels:
            # Probability that low is at or below this level (i.e., we reach it)
            prob = np.mean(data <= level)
            cum_probs.append(prob)
        
        return cum_probs


def build_epdfs(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """
    Build ePDFs from full dataset.
    
    Args:
        df: DataFrame with 'prev_state' and 'range_dn_ticks' columns
    
    Returns:
        Dictionary of ePDF arrays per state
    """
    epdfs = {}
    for state in ["Low", "Med", "High"]:
        epdfs[state] = df[df['prev_state'] == state]['range_dn_ticks'].to_numpy()
    return epdfs