"""
Live Trading Framework

Framework for paper trading and live trading validation.
Provides safety checks, position limits, and real-time monitoring.

Usage:
    framework = LiveTradingFramework(config)
    framework.start_paper_trading()
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import warnings

from inventory_tracker import InventoryTracker
from state_transition import StateTransitionEstimator
from dynamic_penalty import DynamicPenalty


class TradingMode(Enum):
    """Trading mode enumeration."""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Order data structure."""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: Optional[float]
    order_type: str  # 'market', 'limit'
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'order_type': self.order_type,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class Position:
    """Position data structure."""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    def update_price(self, price: float):
        """Update current price and unrealized PnL."""
        self.current_price = price
        self.unrealized_pnl = (price - self.avg_price) * self.quantity


@dataclass
class RiskLimits:
    """Risk limits configuration."""
    max_position_size: float = 1000.0
    max_order_size: float = 100.0
    max_daily_trades: int = 50
    max_daily_loss: float = 10000.0
    max_drawdown: float = 0.1  # 10%
    position_limit_pct: float = 0.2  # 20% of portfolio


class RiskManager:
    """Risk management for live trading."""
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        """
        Initialize RiskManager.
        
        Args:
            limits: Risk limits configuration
        """
        self.limits = limits or RiskLimits()
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.peak_pnl = 0.0
        self.order_history = []
        
    def check_order(self, order: Order, current_position: float) -> Tuple[bool, str]:
        """
        Check if order passes risk limits.
        
        Args:
            order: Order to check
            current_position: Current position size
            
        Returns:
            Tuple of (is_approved, reason)
        """
        # Check order size
        if order.quantity > self.limits.max_order_size:
            return False, f"Order size {order.quantity} exceeds max {self.limits.max_order_size}"
            
        # Check position limit
        new_position = current_position + order.quantity if order.side == 'buy' else current_position - order.quantity
        if abs(new_position) > self.limits.max_position_size:
            return False, f"Position {new_position} would exceed max {self.limits.max_position_size}"
            
        # Check daily trades
        if self.daily_trades >= self.limits.max_daily_trades:
            return False, f"Daily trade limit {self.limits.max_daily_trades} reached"
            
        # Check daily loss
        if self.daily_pnl < -self.limits.max_daily_loss:
            return False, f"Daily loss limit {self.limits.max_daily_loss} exceeded"
            
        return True, "Approved"
        
    def record_trade(self, pnl: float):
        """Record a trade for risk tracking."""
        self.daily_trades += 1
        self.daily_pnl += pnl
        self.peak_pnl = max(self.peak_pnl, self.daily_pnl)
        
    def reset_daily(self):
        """Reset daily counters."""
        self.daily_trades = 0
        self.daily_pnl = 0.0
        
    def get_drawdown(self) -> float:
        """Get current drawdown from peak."""
        if self.peak_pnl <= 0:
            return 0
        return (self.peak_pnl - self.daily_pnl) / self.peak_pnl


class LiveTradingFramework:
    """
    Framework for paper and live trading.
    
    Features:
    - Paper trading simulation
    - Risk management
    - Order tracking
    - Performance monitoring
    """
    
    def __init__(
        self,
        symbol: str = 'NQ',
        mode: TradingMode = TradingMode.PAPER,
        config: Optional[Dict] = None
    ):
        """
        Initialize LiveTradingFramework.
        
        Args:
            symbol: Trading symbol
            mode: Trading mode
            config: Configuration dictionary
        """
        self.symbol = symbol
        self.mode = mode
        self.config = config or {}
        
        # Initialize modules
        self.tracker = InventoryTracker(
            target_quantity=self.config.get('target_quantity', 100)
        )
        self.penalty = DynamicPenalty(
            base_penalty=self.config.get('base_penalty', 10.0)
        )
        self.estimator = StateTransitionEstimator(n_states=3)
        self.risk_manager = RiskManager()
        
        # State
        self.position = Position(
            symbol=symbol,
            quantity=0.0,
            avg_price=0.0,
            current_price=0.0
        )
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self.is_running = False
        self.logs = []
        
    def _log(self, message: str, level: str = 'INFO'):
        """Log a message."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(log_entry)
        print(log_entry)
        
    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self.order_counter += 1
        return f"{self.symbol}_{datetime.now().strftime('%Y%m%d')}_{self.order_counter:04d}"
        
    def create_order(
        self,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = 'limit'
    ) -> Optional[Order]:
        """
        Create a new order.
        
        Args:
            side: 'buy' or 'sell'
            quantity: Order quantity
            price: Limit price (None for market)
            order_type: 'limit' or 'market'
            
        Returns:
            Order object or None if rejected
        """
        order = Order(
            order_id=self._generate_order_id(),
            symbol=self.symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type
        )
        
        # Risk check
        approved, reason = self.risk_manager.check_order(order, self.position.quantity)
        
        if not approved:
            order.status = OrderStatus.REJECTED
            self._log(f"Order rejected: {reason}", level='WARNING')
            return None
            
        self.orders[order.order_id] = order
        self._log(f"Created order: {order.order_id} {side} {quantity}@{price}")
        
        return order
        
    def simulate_fill(
        self,
        order: Order,
        market_price: float
    ) -> bool:
        """
        Simulate order fill (for paper trading).
        
        Args:
            order: Order to fill
            market_price: Current market price
            
        Returns:
            True if filled
        """
        if order.status != OrderStatus.PENDING:
            return False
            
        # Check if limit price is satisfied
        if order.order_type == 'limit' and order.price is not None:
            if order.side == 'buy' and market_price > order.price:
                return False
            if order.side == 'sell' and market_price < order.price:
                return False
                
        # Simulate partial fill
        fill_qty = order.quantity * np.random.uniform(0.8, 1.0)
        fill_price = market_price * (1 + np.random.uniform(-0.0001, 0.0001))
        
        order.filled_quantity = fill_qty
        order.filled_price = fill_price
        order.status = OrderStatus.FILLED
        
        # Update position
        if order.side == 'buy':
            new_qty = self.position.quantity + fill_qty
            self.position.avg_price = (
                self.position.avg_price * self.position.quantity + fill_price * fill_qty
            ) / new_qty if new_qty > 0 else 0
            self.position.quantity = new_qty
        else:
            self.position.quantity -= fill_qty
            
        # Update tracker
        pnl = self.tracker.update(
            filled_quantity=fill_qty,
            exec_price=fill_price,
            ref_price=self.config.get('ref_price', market_price),
            side=order.side
        )
        
        self.risk_manager.record_trade(pnl)
        self._log(f"Filled: {order.order_id} {fill_qty}@{fill_price:.2f} PnL={pnl:.2f}")
        
        return True
        
    def get_signal(
        self,
        t: int,
        T: int,
        current_price: float
    ) -> Dict:
        """
        Get trading signal from stochastic control model.
        
        Args:
            t: Current time step
            T: Total time steps
            current_price: Current market price
            
        Returns:
            Signal dictionary with action recommendation
        """
        # Calculate penalty
        lambda_t = self.penalty.calculate(
            t=t, T=T,
            current_inventory=self.tracker.inventory,
            target_inventory=self.tracker.target_quantity
        )
        
        # Calculate urgency
        urgency = self.tracker.get_urgency_factor(t, T)
        
        # Determine action
        remaining = self.tracker.target_quantity - self.tracker.inventory
        
        if remaining <= 0:
            action = 'hold'
            quantity = 0
        else:
            action = 'buy'
            # Adjust quantity based on urgency
            base_qty = remaining / max(T - t, 1)
            quantity = min(remaining, base_qty * urgency)
            
        return {
            'action': action,
            'quantity': quantity,
            'urgency': urgency,
            'penalty': lambda_t,
            'remaining': remaining,
            'fill_rate': self.tracker.get_fill_rate()
        }
        
    def start_paper_trading(
        self,
        price_data: Optional[pd.DataFrame] = None,
        n_steps: int = 60
    ):
        """
        Start paper trading session.
        
        Args:
            price_data: Historical price data for simulation
            n_steps: Number of steps to simulate
        """
        self._log(f"Starting paper trading for {self.symbol}")
        self.is_running = True
        
        # Reset state
        self.tracker.reset()
        self.risk_manager.reset_daily()
        
        # Generate synthetic data if not provided
        if price_data is None:
            np.random.seed(42)
            prices = 8500 + np.cumsum(np.random.randn(n_steps) * 2)
            price_data = pd.DataFrame({'close': prices})
            
        # Fit state estimator
        if 'close' in price_data.columns and len(price_data) > 50:
            returns = price_data['close'].pct_change().dropna()
            self.estimator.fit_from_returns(returns)
            
        T = min(len(price_data), n_steps)
        ref_price = price_data['close'].iloc[0]
        self.config['ref_price'] = ref_price
        
        for t in range(T):
            if not self.is_running:
                break
                
            current_price = price_data['close'].iloc[t]
            self.position.update_price(current_price)
            
            # Get signal
            signal = self.get_signal(t, T, current_price)
            
            # Create order if needed
            if signal['action'] == 'buy' and signal['quantity'] > 0:
                order = self.create_order(
                    side='buy',
                    quantity=signal['quantity'],
                    price=current_price * 0.9999,  # Slightly below market
                    order_type='limit'
                )
                
                if order:
                    self.simulate_fill(order, current_price)
                    
            # Check risk limits
            drawdown = self.risk_manager.get_drawdown()
            if drawdown > self.risk_manager.limits.max_drawdown:
                self._log(f"Max drawdown exceeded: {drawdown:.1%}", level='WARNING')
                break
                
        self.is_running = False
        self._log("Paper trading completed")
        
    def stop(self):
        """Stop trading."""
        self.is_running = False
        self._log("Trading stopped")
        
    def get_performance_report(self) -> Dict:
        """Get performance report."""
        stats = self.tracker.get_stats()
        
        return {
            'symbol': self.symbol,
            'mode': self.mode.value,
            'position': self.position.quantity,
            'avg_price': self.position.avg_price,
            'current_price': self.position.current_price,
            'unrealized_pnl': self.position.unrealized_pnl,
            'realized_pnl': self.position.realized_pnl,
            'total_pnl': stats['total_pnl'],
            'n_trades': stats['trade_count'],
            'fill_rate': stats['fill_rate'],
            'daily_trades': self.risk_manager.daily_trades,
            'daily_pnl': self.risk_manager.daily_pnl,
            'drawdown': self.risk_manager.get_drawdown()
        }
        
    def export_logs(self, filepath: str):
        """Export logs to file."""
        with open(filepath, 'w') as f:
            f.write('\n'.join(self.logs))
        self._log(f"Logs exported to {filepath}")


# Type hint fix
from typing import Tuple


def run_paper_trading_demo():
    """Run paper trading demonstration."""
    print("=" * 60)
    print("Paper Trading Demo")
    print("=" * 60)
    
    # Create framework
    framework = LiveTradingFramework(
        symbol='NQ',
        mode=TradingMode.PAPER,
        config={
            'target_quantity': 100,
            'base_penalty': 10.0
        }
    )
    
    # Run paper trading
    framework.start_paper_trading(n_steps=60)
    
    # Get report
    report = framework.get_performance_report()
    
    print("\n" + "=" * 60)
    print("Performance Report")
    print("=" * 60)
    for key, value in report.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
            
    return framework


if __name__ == '__main__':
    run_paper_trading_demo()