"""
Dynamic Penalty Module

Calculates time-varying penalty λ(t) for limit order optimization.
Based on stochastic control framework from Zhou's book.

Usage:
    penalty = DynamicPenalty(base_penalty=10.0)
    lambda_t = penalty.calculate(t=30, T=60, inventory_ratio=0.5)
"""

import numpy as np
from typing import Optional, Dict, Callable
from enum import Enum


class PenaltySchedule(Enum):
    """Predefined penalty schedules."""
    CONSTANT = "constant"
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    EXPONENTIAL = "exponential"
    SIGMOID = "sigmoid"


class DynamicPenalty:
    """
    Calculate dynamic penalty λ(t) for order execution optimization.
    
    The penalty increases as:
    - Time approaches end of trading horizon
    - Inventory deviates from target
    - Market conditions become unfavorable
    """
    
    def __init__(
        self,
        base_penalty: float = 10.0,
        max_penalty: float = 50.0,
        time_weight: float = 0.5,
        inventory_weight: float = 0.3,
        volatility_weight: float = 0.2,
        schedule: PenaltySchedule = PenaltySchedule.QUADRATIC
    ):
        """
        Initialize DynamicPenalty.
        
        Args:
            base_penalty: Minimum penalty value
            max_penalty: Maximum penalty value (cap)
            time_weight: Weight for time pressure factor
            inventory_weight: Weight for inventory deviation factor
            volatility_weight: Weight for volatility factor
            schedule: Time schedule type
        """
        self.base_penalty = base_penalty
        self.max_penalty = max_penalty
        self.time_weight = time_weight
        self.inventory_weight = inventory_weight
        self.volatility_weight = volatility_weight
        self.schedule = schedule
        
    def _time_factor(self, t: int, T: int) -> float:
        """
        Calculate time pressure factor.
        
        Args:
            t: Current time step
            T: Total time steps
            
        Returns:
            Time factor in [0, 1]
        """
        if T <= 0:
            return 1.0
            
        progress = t / T
        
        if self.schedule == PenaltySchedule.CONSTANT:
            return 0.0
        elif self.schedule == PenaltySchedule.LINEAR:
            return progress
        elif self.schedule == PenaltySchedule.QUADRATIC:
            return progress ** 2
        elif self.schedule == PenaltySchedule.EXPONENTIAL:
            return (np.exp(progress * 2) - 1) / (np.e ** 2 - 1)
        elif self.schedule == PenaltySchedule.SIGMOID:
            # Sigmoid that increases sharply near the end
            return 1 / (1 + np.exp(-10 * (progress - 0.7)))
        else:
            return progress ** 2
            
    def _inventory_factor(
        self,
        current_inventory: float,
        target_inventory: float,
        max_inventory: float
    ) -> float:
        """
        Calculate inventory deviation factor.
        
        Args:
            current_inventory: Current position
            target_inventory: Target position
            max_inventory: Maximum allowed position
            
        Returns:
            Inventory factor in [0, 1]
        """
        if max_inventory <= 0:
            return 0.0
            
        # Remaining to fill
        remaining = abs(target_inventory - current_inventory)
        
        # Normalize by max
        if abs(target_inventory) > 0:
            ratio = remaining / abs(target_inventory)
        else:
            ratio = 0.0
            
        return min(ratio, 1.0)
        
    def _volatility_factor(
        self,
        current_volatility: float,
        baseline_volatility: float
    ) -> float:
        """
        Calculate volatility factor.
        
        Higher volatility = higher penalty (more risk)
        
        Args:
            current_volatility: Current market volatility
            baseline_volatility: Normal/baseline volatility
            
        Returns:
            Volatility factor in [0, 1]
        """
        if baseline_volatility <= 0:
            return 0.0
            
        vol_ratio = current_volatility / baseline_volatility
        
        # Cap at 2x baseline
        return min(vol_ratio - 1, 1.0) if vol_ratio > 1 else 0.0
        
    def calculate(
        self,
        t: int,
        T: int,
        current_inventory: float = 0.0,
        target_inventory: float = 100.0,
        max_inventory: float = 150.0,
        current_volatility: Optional[float] = None,
        baseline_volatility: Optional[float] = None
    ) -> float:
        """
        Calculate dynamic penalty λ(t).
        
        Args:
            t: Current time step
            T: Total time steps
            current_inventory: Current position
            target_inventory: Target position
            max_inventory: Maximum allowed position
            current_volatility: Current volatility (optional)
            baseline_volatility: Baseline volatility (optional)
            
        Returns:
            Dynamic penalty value
        """
        # Calculate factors
        time_f = self._time_factor(t, T)
        inv_f = self._inventory_factor(current_inventory, target_inventory, max_inventory)
        
        # Volatility factor (optional)
        vol_f = 0.0
        if current_volatility is not None and baseline_volatility is not None:
            vol_f = self._volatility_factor(current_volatility, baseline_volatility)
            
        # Combined factor
        combined = (
            self.time_weight * time_f +
            self.inventory_weight * inv_f +
            self.volatility_weight * vol_f
        )
        
        # Calculate penalty
        penalty = self.base_penalty * (1 + combined)
        
        # Cap at max
        return min(penalty, self.max_penalty)
        
    def get_penalty_schedule(self, T: int) -> np.ndarray:
        """
        Get penalty schedule for entire trading horizon.
        
        Args:
            T: Total time steps
            
        Returns:
            Array of penalty values for each time step
        """
        penalties = np.zeros(T)
        for t in range(T):
            penalties[t] = self.calculate(t, T)
        return penalties
        
    def get_summary(self) -> Dict:
        """Get configuration summary."""
        return {
            'base_penalty': self.base_penalty,
            'max_penalty': self.max_penalty,
            'time_weight': self.time_weight,
            'inventory_weight': self.inventory_weight,
            'volatility_weight': self.volatility_weight,
            'schedule': self.schedule.value
        }


class AdaptivePenalty(DynamicPenalty):
    """
    Adaptive penalty that learns from execution performance.
    
    Adjusts penalty based on:
    - Historical fill rates
    - Market regime changes
    - Execution quality feedback
    """
    
    def __init__(
        self,
        base_penalty: float = 10.0,
        max_penalty: float = 50.0,
        adaptation_rate: float = 0.1,
        **kwargs
    ):
        """
        Initialize AdaptivePenalty.
        
        Args:
            base_penalty: Base penalty value
            max_penalty: Maximum penalty
            adaptation_rate: Rate of adaptation (0-1)
            **kwargs: Additional arguments for DynamicPenalty
        """
        super().__init__(base_penalty=base_penalty, max_penalty=max_penalty, **kwargs)
        self.adaptation_rate = adaptation_rate
        
        # Tracking
        self.fill_history = []
        self.penalty_history = []
        self.adapted_base = base_penalty
        
    def update_from_fill(
        self,
        filled: bool,
        expected_fill_prob: float,
        penalty_used: float
    ):
        """
        Update penalty based on fill outcome.
        
        Args:
            filled: Whether order was filled
            expected_fill_prob: Expected fill probability
            penalty_used: Penalty used for this order
        """
        self.fill_history.append({
            'filled': filled,
            'expected_prob': expected_fill_prob,
            'penalty': penalty_used
        })
        
        # Adapt base penalty
        if len(self.fill_history) >= 10:
            recent = self.fill_history[-10:]
            actual_fill_rate = sum(f['filled'] for f in recent) / len(recent)
            avg_expected = sum(f['expected_prob'] for f in recent) / len(recent)
            
            # If filling more than expected, can reduce penalty (be more aggressive)
            # If filling less, increase penalty (be more conservative)
            if avg_expected > 0:
                ratio = actual_fill_rate / avg_expected
                adjustment = (ratio - 1) * self.adaptation_rate
                self.adapted_base = self.base_penalty * (1 - adjustment)
                self.adapted_base = max(self.base_penalty * 0.5, 
                                       min(self.adapted_base, self.base_penalty * 2))
                                       
    def calculate(self, t: int, T: int, **kwargs) -> float:
        """Calculate adaptive penalty."""
        # Use adapted base penalty
        original_base = self.base_penalty
        self.base_penalty = self.adapted_base
        
        penalty = super().calculate(t, T, **kwargs)
        self.penalty_history.append(penalty)
        
        self.base_penalty = original_base
        return penalty
        
    def get_adaptation_summary(self) -> Dict:
        """Get adaptation statistics."""
        return {
            'original_base': self.base_penalty,
            'adapted_base': self.adapted_base,
            'adaptation_ratio': self.adapted_base / self.base_penalty,
            'n_observations': len(self.fill_history)
        }


def create_penalty_function(
    schedule: str = "quadratic",
    base: float = 10.0,
    max_val: float = 50.0
) -> Callable[[int, int], float]:
    """
    Create a simple penalty function.
    
    Args:
        schedule: Schedule type name
        base: Base penalty
        max_val: Maximum penalty
        
    Returns:
        Function f(t, T) -> penalty
    """
    schedule_enum = PenaltySchedule(schedule)
    penalty = DynamicPenalty(
        base_penalty=base,
        max_penalty=max_val,
        schedule=schedule_enum
    )
    
    def penalty_func(t: int, T: int) -> float:
        return penalty.calculate(t, T)
        
    return penalty_func


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    
    # Compare different schedules
    T = 60
    schedules = ['constant', 'linear', 'quadratic', 'exponential', 'sigmoid']
    
    plt.figure(figsize=(10, 6))
    
    for schedule in schedules:
        penalty = DynamicPenalty(
            base_penalty=10.0,
            max_penalty=50.0,
            schedule=PenaltySchedule(schedule)
        )
        penalties = penalty.get_penalty_schedule(T)
        plt.plot(range(T), penalties, label=schedule, linewidth=2)
        
    plt.xlabel('Time Step')
    plt.ylabel('Penalty λ(t)')
    plt.title('Dynamic Penalty Schedules')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig('dynamic_penalty_comparison.png', dpi=150)
    plt.close()
    
    print("Saved: dynamic_penalty_comparison.png")
    
    # Test with inventory
    print("\nPenalty with inventory factor:")
    penalty = DynamicPenalty(base_penalty=10.0)
    for t in [0, 15, 30, 45, 59]:
        for inv in [0, 50, 100]:
            p = penalty.calculate(t=t, T=60, current_inventory=inv, target_inventory=100)
            print(f"  t={t:2d}, inv={inv:3d}: λ={p:.2f}")