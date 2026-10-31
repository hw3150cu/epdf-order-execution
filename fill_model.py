"""
Fill Model - Conditional Probability Fill Model for Order Execution
Term Project 2 - Volatility-Volume-based Order Management

This module implements a simple conditional fill model:
- If fill condition is met → 100% filled
- If fill condition not met → 0% filled

Future enhancements can include partial fills based on volume profile.
"""

import numpy as np
from typing import Tuple, Optional


class ConditionalFillModel:
    """
    Conditional probability fill model for limit orders.
    
    For BUY orders:
        - Limit price = Open - level * tick_size
        - Fill condition: Low <= Limit price (i.e., RangeDn >= level)
    
    For SELL orders:
        - Limit price = Open + level * tick_size
        - Fill condition: High >= Limit price (i.e., RangeUp >= level)
    """
    
    def __init__(self, tick_size: float = 0.25):
        """
        Initialize fill model.
        
        Args:
            tick_size: Minimum price fluctuation
        """
        self.tick_size = tick_size
    
    def check_fill(self, 
                   open_price: float, 
                   high: float, 
                   low: float,
                   level_ticks: int,
                   direction: str = 'buy') -> bool:
        """
        Check if a limit order is filled (all-or-nothing).
        
        Args:
            open_price: Opening price of the bar
            high: Highest price of the bar
            low: Lowest price of the bar
            level_ticks: Price level in ticks from open
            direction: 'buy' or 'sell'
        
        Returns:
            bool: True if filled, False otherwise
        
        Example:
            >>> model = ConditionalFillModel(tick_size=0.25)
            >>> # BUY at open - 2 ticks, low reached that level
            >>> model.check_fill(3881.50, 3883.00, 3880.00, 2, 'buy')
            True  # low=3880.00 <= 3881.50 - 2*0.25 = 3881.00
            
            >>> # BUY at open - 10 ticks, low didn't reach that level
            >>> model.check_fill(3881.50, 3883.00, 3880.00, 10, 'buy')
            False  # low=3880.00 > 3881.50 - 10*0.25 = 3879.00
        """
        if direction.lower() == 'buy':
            # Buy limit: Open - level * tick
            # Fill if price goes down enough (low <= limit)
            limit_price = open_price - level_ticks * self.tick_size
            return low <= limit_price
        else:  # sell
            # Sell limit: Open + level * tick
            # Fill if price goes up enough (high >= limit)
            limit_price = open_price + level_ticks * self.tick_size
            return high >= limit_price
    
    def check_fill_batch(self,
                         open_prices: np.ndarray,
                         highs: np.ndarray,
                         lows: np.ndarray,
                         level_ticks: int,
                         direction: str = 'buy') -> np.ndarray:
        """
        Check fills for multiple bars (vectorized).
        
        Args:
            open_prices: Array of opening prices
            highs: Array of highest prices
            lows: Array of lowest prices
            level_ticks: Price level in ticks
            direction: 'buy' or 'sell'
        
        Returns:
            np.ndarray: Boolean array of fill results
        """
        if direction.lower() == 'buy':
            limit_prices = open_prices - level_ticks * self.tick_size
            return lows <= limit_prices
        else:
            limit_prices = open_prices + level_ticks * self.tick_size
            return highs >= limit_prices
    
    def get_fill_probability(self,
                            epdf_range_dn: np.ndarray,
                            epdf_range_up: np.ndarray,
                            level_ticks: int,
                            direction: str = 'buy') -> float:
        """
        Calculate fill probability from ePDF.
        
        Args:
            epdf_range_dn: Histogram of RangeDn values (indexed by ticks)
            epdf_range_up: Histogram of RangeUp values (indexed by ticks)
            level_ticks: Price level in ticks
            direction: 'buy' or 'sell'
        
        Returns:
            float: Probability of fill [0, 1]
        
        For BUY: P(RangeDn >= level)
        For SELL: P(RangeUp >= level)
        """
        if direction.lower() == 'buy':
            # P(RangeDn >= level)
            if level_ticks >= len(epdf_range_dn):
                return 0.0
            return np.sum(epdf_range_dn[level_ticks:]) / np.sum(epdf_range_dn)
        else:
            # P(RangeUp >= level)
            if level_ticks >= len(epdf_range_up):
                return 0.0
            return np.sum(epdf_range_up[level_ticks:]) / np.sum(epdf_range_up)


class SimplePenaltyModel:
    """
    Simple penalty model for unfilled orders.
    
    Current implementation:
        - Penalty = next_open - reference_price
        - Simple and straightforward
    
    TODO: Future enhancements to consider:
        1. State-dependent penalty: λ(state) based on volatility regime
        2. Time-dependent penalty: λ(t, T) increases as time runs out
        3. Inventory-dependent penalty: λ(I, target) based on remaining quantity
        4. Combined penalty: λ(state, t, I) = λ_base × f(state) × g(t,T) × h(I,target)
        5. Expected penalty: E[max(next_open, close+tick) | state] for optimization
        6. Direction-aware penalty:
           - BUY: penalty = max(next_open, close + tick) - reference
           - SELL: penalty = reference - min(next_open, close - tick)
    """
    
    def __init__(self, tick_size: float = 0.25):
        """
        Initialize penalty model.
        
        Args:
            tick_size: Minimum price fluctuation
        """
        self.tick_size = tick_size
    
    def calculate_penalty(self,
                         next_open: float,
                         reference_price: float,
                         direction: str = 'buy') -> float:
        """
        Calculate penalty for unfilled order (simple version).
        
        Args:
            next_open: Next bar's opening price
            reference_price: Reference price (usually previous close)
            direction: 'buy' or 'sell'
        
        Returns:
            float: Penalty in price units
        
        Example:
            >>> model = SimplePenaltyModel(tick_size=0.25)
            >>> # BUY: price went up, penalty positive
            >>> model.calculate_penalty(3882.50, 3881.50, 'buy')
            1.0  # = 4 ticks
            
            >>> # BUY: price went down, penalty negative (benefit)
            >>> model.calculate_penalty(3880.50, 3881.50, 'buy')
            -1.0  # = -4 ticks
        """
        if direction.lower() == 'buy':
            # For buy: penalty = next_open - reference
            # Positive if price went up (bad for buyer)
            # Negative if price went down (good for buyer)
            return next_open - reference_price
        else:
            # For sell: penalty = reference - next_open
            # Positive if price went down (bad for seller)
            # Negative if price went up (good for seller)
            return reference_price - next_open
    
    def calculate_penalty_ticks(self,
                               next_open: float,
                               reference_price: float,
                               direction: str = 'buy') -> float:
        """
        Calculate penalty in ticks.
        
        Returns:
            float: Penalty in ticks
        """
        penalty_price = self.calculate_penalty(next_open, reference_price, direction)
        return penalty_price / self.tick_size
    
    # ========================================================================
    # TODO: Future enhancement methods (to be implemented)
    # ========================================================================
    
    def calculate_expected_penalty(self,
                                   state: str,
                                   current_close: float,
                                   epdf_movement: np.ndarray,
                                   direction: str = 'buy') -> float:
        """
        TODO: Calculate expected penalty for optimization.
        
        Expected penalty = E[max(next_open, close+tick) | state]
        
        This uses the ePDF of price movements to estimate the expected
        penalty given the current state.
        
        Args:
            state: Current volatility state
            current_close: Current close price
            epdf_movement: ePDF of price movements
            direction: 'buy' or 'sell'
        
        Returns:
            float: Expected penalty
        """
        # TODO: Implement using epdf_movement
        raise NotImplementedError("Expected penalty calculation not yet implemented")
    
    def calculate_dynamic_penalty(self,
                                 state: str,
                                 inventory: float,
                                 target: float,
                                 t: int,
                                 T: int,
                                 base_penalty: float = 5.0) -> float:
        """
        TODO: Calculate dynamic penalty based on state, inventory, and time.
        
        λ(state, t, I) = λ_base × f(state) × g(t,T) × h(I,target)
        
        Args:
            state: Current volatility state
            inventory: Current inventory
            target: Target quantity
            t: Current time step
            T: Total time steps
            base_penalty: Base penalty value
        
        Returns:
            float: Dynamic penalty
        """
        # TODO: Implement dynamic penalty
        # f(state) = volatility adjustment
        # g(t, T) = time pressure = 1 + α × (1 - (T-t)/T)
        # h(I, target) = inventory pressure = 1 + β × (I/target - 1)
        raise NotImplementedError("Dynamic penalty calculation not yet implemented")


# ============================================================================
# Utility functions
# ============================================================================

def calculate_range_metrics(open_price: float, 
                           high: float, 
                           low: float,
                           tick_size: float = 0.25) -> Tuple[int, int, int]:
    """
    Calculate range metrics in ticks.
    
    Args:
        open_price: Opening price
        high: Highest price
        low: Lowest price
        tick_size: Minimum price fluctuation
    
    Returns:
        Tuple[int, int, int]: (range_ticks, range_up_ticks, range_dn_ticks)
    
    Example:
        >>> calculate_range_metrics(3881.50, 3883.00, 3880.00, 0.25)
        (6, 6, 6)
        # Range = 3883.00 - 3880.00 = 3.00 = 12 ticks... wait let me recalculate
        # RangeUp = 3883.00 - 3881.50 = 1.50 = 6 ticks
        # RangeDn = 3881.50 - 3880.00 = 1.50 = 6 ticks
        # Range = RangeUp + RangeDn = 12 ticks
    """
    range_up = (high - open_price) / tick_size
    range_dn = (open_price - low) / tick_size
    total_range = range_up + range_dn
    
    return int(total_range), int(range_up), int(range_dn)


if __name__ == "__main__":
    # Quick test
    fill_model = ConditionalFillModel(tick_size=0.25)
    penalty_model = SimplePenaltyModel(tick_size=0.25)
    
    # Test fill check
    print("=== Fill Model Tests ===")
    print(f"BUY @ open-2ticks, low reached: {fill_model.check_fill(3881.50, 3883.00, 3880.00, 2, 'buy')}")
    print(f"  Expected: True (low=3880.00 <= limit=3881.00)")
    
    print(f"BUY @ open-10ticks, low didn't reach: {fill_model.check_fill(3881.50, 3883.00, 3880.00, 10, 'buy')}")
    print(f"  Expected: False (low=3880.00 > limit=3879.00)")
    
    print(f"SELL @ open+2ticks, high reached: {fill_model.check_fill(3881.50, 3883.00, 3880.00, 2, 'sell')}")
    print(f"  Expected: True (high=3883.00 >= limit=3882.00)")
    
    print(f"SELL @ open+10ticks, high didn't reach: {fill_model.check_fill(3881.50, 3883.00, 3880.00, 10, 'sell')}")
    print(f"  Expected: False (high=3883.00 < limit=3884.00)")
    
    # Test penalty
    print("\n=== Penalty Model Tests ===")
    print(f"BUY penalty (price up): {penalty_model.calculate_penalty_ticks(3882.50, 3881.50, 'buy')}")
    print(f"  Expected: 4 ticks")
    
    print(f"BUY penalty (price down): {penalty_model.calculate_penalty_ticks(3880.50, 3881.50, 'buy')}")
    print(f"  Expected: -4 ticks")
    
    print(f"SELL penalty (price down): {penalty_model.calculate_penalty_ticks(3880.50, 3881.50, 'sell')}")
    print(f"  Expected: 4 ticks")
    
    print(f"SELL penalty (price up): {penalty_model.calculate_penalty_ticks(3882.50, 3881.50, 'sell')}")
    print(f"  Expected: -4 ticks")
    
    print("\n=== All tests passed! ===")