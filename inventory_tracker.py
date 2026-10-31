"""
Inventory Tracker Module

Tracks cumulative inventory and calculates urgency factors for order execution.
Based on stochastic control framework from Zhou's book.

Usage:
    tracker = InventoryTracker(target_quantity=100)
    tracker.update(filled_qty=10, exec_price=8500.0, ref_price=8501.0)
    urgency = tracker.get_urgency_factor(t=30, T=60)
"""

import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class TradeRecord:
    """Record of a single trade."""
    timestamp: object
    quantity: float
    price: float
    ref_price: float
    pnl: float
    side: str  # 'buy' or 'sell'


class InventoryTracker:
    """
    Track inventory and calculate urgency factors for execution.
    
    Features:
    - Cumulative inventory tracking
    - PnL tracking per trade and total
    - Urgency factor based on inventory and time
    - Max inventory constraint
    """
    
    def __init__(
        self,
        target_quantity: float = 100.0,
        max_inventory: float = 150.0,
        urgency_base: float = 1.0,
        urgency_time_weight: float = 0.5,
        urgency_inventory_weight: float = 0.5
    ):
        """
        Initialize InventoryTracker.
        
        Args:
            target_quantity: Target position to achieve
            max_inventory: Maximum allowed inventory
            urgency_base: Base urgency multiplier
            urgency_time_weight: Weight for time pressure in urgency
            urgency_inventory_weight: Weight for inventory in urgency
        """
        self.target_quantity = target_quantity
        self.max_inventory = max_inventory
        self.urgency_base = urgency_base
        self.urgency_time_weight = urgency_time_weight
        self.urgency_inventory_weight = urgency_inventory_weight
        
        # State variables
        self.inventory = 0.0
        self.total_pnl = 0.0
        self.total_cost = 0.0
        self.trade_count = 0
        self.trades: List[TradeRecord] = []
        
    def update(
        self,
        filled_quantity: float,
        exec_price: float,
        ref_price: float,
        timestamp: Optional[object] = None,
        side: str = 'buy'
    ) -> float:
        """
        Update inventory and PnL after a trade.
        
        Args:
            filled_quantity: Quantity filled in this trade
            exec_price: Execution price
            ref_price: Reference price (e.g., previous close)
            timestamp: Trade timestamp
            side: 'buy' or 'sell'
            
        Returns:
            PnL for this trade
        """
        # Update inventory
        if side == 'buy':
            self.inventory += filled_quantity
        else:
            self.inventory -= filled_quantity
            
        # Calculate PnL
        # For buy: savings = ref_price - exec_price (positive if bought below ref)
        # For sell: savings = exec_price - ref_price (positive if sold above ref)
        if side == 'buy':
            bar_pnl = (ref_price - exec_price) * filled_quantity
        else:
            bar_pnl = (exec_price - ref_price) * filled_quantity
            
        self.total_pnl += bar_pnl
        self.total_cost += exec_price * filled_quantity
        self.trade_count += 1
        
        # Record trade
        trade = TradeRecord(
            timestamp=timestamp,
            quantity=filled_quantity,
            price=exec_price,
            ref_price=ref_price,
            pnl=bar_pnl,
            side=side
        )
        self.trades.append(trade)
        
        return bar_pnl
    
    def get_urgency_factor(self, t: int, T: int) -> float:
        """
        Calculate urgency factor based on inventory and time.
        
        Urgency increases when:
        - Inventory is far from target
        - Time is running out
        
        Args:
            t: Current time step
            T: Total time steps
            
        Returns:
            Urgency factor (higher = more urgent)
        """
        if T <= 0:
            return self.urgency_base
            
        # Time pressure: increases as we approach end
        time_elapsed = t / T
        time_pressure = time_elapsed ** 2  # Quadratic increase
        
        # Inventory ratio: how much of target is filled
        if self.target_quantity != 0:
            inventory_ratio = abs(self.inventory) / abs(self.target_quantity)
        else:
            inventory_ratio = 0.0
            
        # Combined urgency
        urgency = self.urgency_base * (
            1 + 
            self.urgency_time_weight * time_pressure +
            self.urgency_inventory_weight * (1 - inventory_ratio)
        )
        
        return urgency
    
    def get_remaining_quantity(self) -> float:
        """Get remaining quantity to reach target."""
        return self.target_quantity - self.inventory
    
    def get_fill_rate(self) -> float:
        """Get percentage of target filled."""
        if self.target_quantity == 0:
            return 1.0
        return self.inventory / self.target_quantity
    
    def is_complete(self) -> bool:
        """Check if target quantity is reached."""
        return abs(self.inventory - self.target_quantity) < 1e-6
    
    def is_max_exceeded(self) -> bool:
        """Check if max inventory is exceeded."""
        return abs(self.inventory) > self.max_inventory
    
    def get_stats(self) -> Dict:
        """Get summary statistics."""
        return {
            'inventory': self.inventory,
            'target_quantity': self.target_quantity,
            'remaining': self.get_remaining_quantity(),
            'fill_rate': self.get_fill_rate(),
            'total_pnl': self.total_pnl,
            'total_cost': self.total_cost,
            'trade_count': self.trade_count,
            'avg_pnl_per_trade': self.total_pnl / self.trade_count if self.trade_count > 0 else 0,
            'is_complete': self.is_complete(),
            'is_max_exceeded': self.is_max_exceeded()
        }
    
    def reset(self):
        """Reset tracker to initial state."""
        self.inventory = 0.0
        self.total_pnl = 0.0
        self.total_cost = 0.0
        self.trade_count = 0
        self.trades = []
        
    def get_trade_history(self) -> List[Dict]:
        """Get list of all trades as dictionaries."""
        return [
            {
                'timestamp': t.timestamp,
                'quantity': t.quantity,
                'price': t.price,
                'ref_price': t.ref_price,
                'pnl': t.pnl,
                'side': t.side
            }
            for t in self.trades
        ]


class InventoryAwareAgent:
    """
    Agent with inventory tracking and urgency-aware execution.
    
    Extends the basic optimization with:
    - Inventory constraints
    - Dynamic urgency adjustment
    - PnL tracking
    """
    
    def __init__(
        self,
        target_quantity: float = 100.0,
        max_inventory: float = 150.0,
        base_penalty: float = 10.0
    ):
        """
        Initialize InventoryAwareAgent.
        
        Args:
            target_quantity: Target position to achieve
            max_inventory: Maximum allowed inventory
            base_penalty: Base penalty for unfilled orders
        """
        self.tracker = InventoryTracker(
            target_quantity=target_quantity,
            max_inventory=max_inventory
        )
        self.base_penalty = base_penalty
        
    def calculate_utility(
        self,
        expected_savings: float,
        fill_probability: float,
        t: int,
        T: int
    ) -> float:
        """
        Calculate utility with inventory awareness.
        
        Args:
            expected_savings: Expected savings from limit orders
            fill_probability: Probability of filling
            t: Current time step
            T: Total time steps
            
        Returns:
            Adjusted utility
        """
        urgency = self.tracker.get_urgency_factor(t, T)
        
        # Adjust penalty based on urgency
        adjusted_penalty = self.base_penalty * urgency
        
        # Utility = expected savings - penalty for missing
        utility = expected_savings - (1 - fill_probability) * adjusted_penalty
        
        return utility
    
    def execute(
        self,
        filled_quantity: float,
        exec_price: float,
        ref_price: float,
        timestamp: Optional[object] = None,
        side: str = 'buy'
    ) -> float:
        """
        Execute a trade and update tracking.
        
        Args:
            filled_quantity: Quantity filled
            exec_price: Execution price
            ref_price: Reference price
            timestamp: Trade timestamp
            side: 'buy' or 'sell'
            
        Returns:
            PnL for this trade
        """
        return self.tracker.update(
            filled_quantity=filled_quantity,
            exec_price=exec_price,
            ref_price=ref_price,
            timestamp=timestamp,
            side=side
        )
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report."""
        stats = self.tracker.get_stats()
        
        # Calculate additional metrics
        trades = self.tracker.trades
        if trades:
            pnls = [t.pnl for t in trades]
            winning_trades = [p for p in pnls if p > 0]
            losing_trades = [p for p in pnls if p < 0]
            
            stats['win_rate'] = len(winning_trades) / len(trades) if trades else 0
            stats['avg_win'] = np.mean(winning_trades) if winning_trades else 0
            stats['avg_loss'] = np.mean(losing_trades) if losing_trades else 0
            stats['max_win'] = max(pnls) if pnls else 0
            stats['max_loss'] = min(pnls) if pnls else 0
        else:
            stats['win_rate'] = 0
            stats['avg_win'] = 0
            stats['avg_loss'] = 0
            stats['max_win'] = 0
            stats['max_loss'] = 0
            
        return stats


# Convenience function
def create_tracker(target: float, max_inv: Optional[float] = None) -> InventoryTracker:
    """Create an InventoryTracker with sensible defaults."""
    if max_inv is None:
        max_inv = target * 1.5
    return InventoryTracker(target_quantity=target, max_inventory=max_inv)


if __name__ == '__main__':
    # Quick test
    tracker = InventoryTracker(target_quantity=100)
    
    # Simulate some trades
    for i in range(10):
        pnl = tracker.update(
            filled_quantity=10,
            exec_price=8500 - i * 0.5,
            ref_price=8500,
            timestamp=i,
            side='buy'
        )
        urgency = tracker.get_urgency_factor(t=i, T=10)
        print(f"Trade {i}: qty=10, pnl={pnl:.2f}, urgency={urgency:.2f}")
        
    print("\nFinal stats:")
    print(tracker.get_stats())