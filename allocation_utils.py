"""
Allocation utilities for converting fractional weights to integer contracts.

Prioritizes best levels when allocating remaining contracts.
"""

import numpy as np
from typing import List, Tuple


def allocate_contracts(
    weights: List[float],
    volume: int,
    levels: List[float]
) -> Tuple[List[int], List[float]]:
    """
    Allocate contracts to limit levels with integer constraints.
    
    Prioritizes higher levels when distributing remaining contracts.
    
    Args:
        weights: List of weights (sum to 1.0)
        volume: Total number of contracts to allocate
        levels: List of limit levels (in ticks)
    
    Returns:
        (allocation, adjusted_levels): Tuple of:
        - allocation: Integer contracts allocated to each level
        - adjusted_levels: Levels with 0 allocation removed
    
    Example:
        weights = [0.4, 0.35, 0.25]
        volume = 8
        levels = [0.7, 2.3, 4.8]
        
        # Step 1: Floor allocation
        initial = [3, 2, 2]  # floor(0.4*8), floor(0.35*8), floor(0.25*8)
        sum_initial = 7
        
        # Step 2: Need 1 more contract
        # Give to highest level (4.8)
        allocation = [3, 2, 3]  # Sum = 8 ✓
        
        return [3, 2, 3], [0.7, 2.3, 4.8]
    
    Example 2:
        weights = [0.4, 0.35, 0.25]
        volume = 7
        levels = [0.7, 2.3, 4.8]
        
        # Step 1: Floor allocation
        initial = [2, 2, 1]  # floor(0.4*7), floor(0.35*7), floor(0.25*7)
        sum_initial = 5
        
        # Step 2: Need 2 more contracts
        # Give to highest levels first (4.8, then 2.3)
        allocation = [2, 3, 2]  # Sum = 7 ✓
        
        return [2, 3, 2], [2.3, 4.8]  # Level 0.7 removed (0 allocation)
    """
    # Normalize weights to sum to 1.0
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]
    
    # Step 1: Floor allocation
    allocation = [int(w * volume) for w in weights]
    sum_allocation = sum(allocation)
    
    # Step 2: Distribute remaining contracts to highest levels first
    remaining = volume - sum_allocation
    
    if remaining > 0:
        # Sort levels by value (descending) to prioritize highest levels
        # Create list of (level, index) pairs and sort
        level_indices = sorted(
            [(levels[i], i) for i in range(len(levels))],
            key=lambda x: x[0],
            reverse=True
        )
        
        # Allocate remaining contracts one by one to highest levels
        for level_idx in range(remaining):
            if level_idx < len(level_indices):
                idx = level_indices[level_idx][1]
                allocation[idx] += 1
    
    # Step 3: Remove levels with 0 allocation
    adjusted_allocation = []
    adjusted_levels = []
    for i in range(len(allocation)):
        if allocation[i] > 0:
            adjusted_allocation.append(allocation[i])
            adjusted_levels.append(levels[i])
    
    return adjusted_allocation, adjusted_levels


def round_levels_to_integer(levels: List[float]) -> List[int]:
    """
    Round limit levels to nearest integer ticks.
    
    Args:
        levels: List of fractional levels (e.g., [0.7, 2.3, 4.8])
    
    Returns:
        List of integer levels (e.g., [1, 2, 5])
    
    Example:
        round_levels_to_integer([0.7, 2.3, 4.8])
        # Returns: [1, 2, 5]
    """
    return [round(level) for level in levels]


def allocate_with_integer_levels(
    weights: List[float],
    volume: int,
    levels: List[float]
) -> Tuple[List[int], List[int]]:
    """
    Allocate contracts with integer level constraints.
    
    Rounds levels to integers, then allocates contracts prioritizing higher levels.
    
    Args:
        weights: List of weights (sum to 1.0)
        volume: Total number of contracts to allocate
        levels: List of limit levels (in ticks, can be fractional)
    
    Returns:
        (allocation, integer_levels): Tuple of:
        - allocation: Integer contracts allocated to each level
        - integer_levels: Rounded integer levels
    
    Example:
        weights = [0.4, 0.35, 0.25]
        volume = 8
        levels = [0.7, 2.3, 4.8]
        
        # Round levels
        integer_levels = [1, 2, 5]
        
        # Allocate
        allocation = [3, 2, 3]  # Sum = 8 ✓
        
        return [3, 2, 3], [1, 2, 5]
    """
    # Round levels to integers
    integer_levels = round_levels_to_integer(levels)
    
    # Allocate contracts
    allocation, adjusted_levels = allocate_contracts(weights, volume, integer_levels)
    
    # Adjust levels to match allocation
    adjusted_integer_levels = []
    for i in range(len(integer_levels)):
        if i < len(allocation):
            adjusted_integer_levels.append(integer_levels[i])
    
    return allocation, adjusted_integer_levels


def calculate_savings(
    allocation: List[int],
    levels: List[float],
    tick_size: float,
    buy_gap: float,
    sell_gap: float
) -> Tuple[float, float, float]:
    """
    Calculate savings from filled limit orders.
    
    Args:
        allocation: Number of contracts at each level
        levels: Limit levels in ticks
        tick_size: Tick size in dollars
        buy_gap: Available downward range (open - low) in dollars
        sell_gap: Available upward range (high - open) in dollars
    
    Returns:
        (buy_savings, sell_savings, total_savings): Savings in ticks
    
    Example:
        allocation = [3, 2, 3]
        levels = [0, 1, 2]  # in ticks
        tick_size = 0.25
        buy_gap = 2.0  # dollars
        
        # Convert buy_gap to ticks
        buy_gap_ticks = 2.0 / 0.25 = 8.0 ticks
        
        # Check fills:
        # Level 0: 0 ticks <= 8 ticks ✓ fills 3 contracts
        # Level 1: 1 tick <= 8 ticks ✓ fills 2 contracts
        # Level 2: 2 ticks <= 8 ticks ✓ fills 3 contracts
        
        # Savings:
        # buy_savings = (3*0 + 2*1 + 3*2) / 8 = 8/8 = 1.0 tick per contract
        # Total buy savings = 1.0 * 8 = 8.0 ticks
    """
    # Convert gaps to ticks
    buy_gap_ticks = buy_gap / tick_size
    sell_gap_ticks = sell_gap / tick_size
    
    # Calculate buy savings
    buy_savings = 0.0
    buy_filled = 0
    for i, (alloc, level) in enumerate(zip(allocation, levels)):
        if level <= buy_gap_ticks:
            buy_savings += alloc * level
            buy_filled += alloc
    
    # Calculate sell savings
    sell_savings = 0.0
    sell_filled = 0
    for i, (alloc, level) in enumerate(zip(allocation, levels)):
        if level <= sell_gap_ticks:
            sell_savings += alloc * level
            sell_filled += alloc
    
    # Normalize by total filled contracts
    total_buy_contracts = sum(allocation)
    total_sell_contracts = sum(allocation)
    
    if total_buy_contracts > 0:
        buy_savings_normalized = buy_savings / total_buy_contracts
    else:
        buy_savings_normalized = 0.0
    
    if total_sell_contracts > 0:
        sell_savings_normalized = sell_savings / total_sell_contracts
    else:
        sell_savings_normalized = 0.0
    
    return buy_savings_normalized, sell_savings_normalized, buy_savings_normalized + sell_savings_normalized


if __name__ == '__main__':
    # Test examples from user
    print("="*70)
    print("ALLOCATION UTILITY TESTS")
    print("="*70)
    
    # Example 1: Volume = 8
    print("\nExample 1: Volume = 8")
    weights = [0.4, 0.35, 0.25]
    volume = 8
    levels = [0.7, 2.3, 4.8]
    
    allocation, adjusted_levels = allocate_contracts(weights, volume, levels)
    print(f"  Weights: {weights}")
    print(f"  Volume: {volume}")
    print(f"  Levels: {levels}")
    print(f"  Allocation: {allocation} (sum = {sum(allocation)})")
    print(f"  Adjusted levels: {adjusted_levels}")
    
    # With integer levels
    allocation_int, levels_int = allocate_with_integer_levels(weights, volume, levels)
    print(f"  With integer levels:")
    print(f"    Allocation: {allocation_int} (sum = {sum(allocation_int)})")
    print(f"    Integer levels: {levels_int}")
    
    # Example 2: Volume = 7
    print("\nExample 2: Volume = 7")
    weights = [0.4, 0.35, 0.25]
    volume = 7
    levels = [0.7, 2.3, 4.8]
    
    allocation, adjusted_levels = allocate_contracts(weights, volume, levels)
    print(f"  Weights: {weights}")
    print(f"  Volume: {volume}")
    print(f"  Levels: {levels}")
    print(f"  Allocation: {allocation} (sum = {sum(allocation)})")
    print(f"  Adjusted levels: {adjusted_levels}")
    
    # With integer levels
    allocation_int, levels_int = allocate_with_integer_levels(weights, volume, levels)
    print(f"  With integer levels:")
    print(f"    Allocation: {allocation_int} (sum = {sum(allocation_int)})")
    print(f"    Integer levels: {levels_int}")
    
    # Test savings calculation
    print("\n" + "="*70)
    print("SAVINGS CALCULATION TEST")
    print("="*70)
    
    allocation = [3, 2, 3]
    levels = [0, 1, 2]
    tick_size = 0.25
    buy_gap = 2.0
    sell_gap = 1.0
    
    buy_save, sell_save, total_save = calculate_savings(
        allocation, levels, tick_size, buy_gap, sell_gap
    )
    
    print(f"  Allocation: {allocation}")
    print(f"  Levels: {levels}")
    print(f"  Tick size: ${tick_size}")
    print(f"  Buy gap: ${buy_gap} ({buy_gap/tick_size:.1f} ticks)")
    print(f"  Sell gap: ${sell_gap} ({sell_gap/tick_size:.1f} ticks)")
    print(f"  Buy savings: {buy_save:.2f} ticks per contract")
    print(f"  Sell savings: {sell_save:.2f} ticks per contract")
    print(f"  Total savings: {total_save:.2f} ticks per contract")