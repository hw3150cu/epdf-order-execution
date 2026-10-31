"""
Comprehensive tests for stochastic control modules.

Tests:
- inventory_tracker.py
- state_transition.py
- dynamic_penalty.py

Run: python -m pytest test_stochastic_modules.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Import modules to test
from inventory_tracker import (
    InventoryTracker, InventoryAwareAgent, TradeRecord, create_tracker
)
from state_transition import (
    StateTransitionEstimator, StatePredictor, estimate_transition_from_data
)
from dynamic_penalty import (
    DynamicPenalty, AdaptivePenalty, PenaltySchedule, create_penalty_function
)


# ============================================================================
# Inventory Tracker Tests
# ============================================================================

class TestInventoryTracker:
    """Tests for InventoryTracker class."""
    
    def test_init(self):
        """Test initialization with default parameters."""
        tracker = InventoryTracker()
        assert tracker.target_quantity == 100.0
        assert tracker.max_inventory == 150.0
        assert tracker.inventory == 0.0
        assert tracker.total_pnl == 0.0
        
    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        tracker = InventoryTracker(
            target_quantity=200.0,
            max_inventory=300.0,
            urgency_base=2.0
        )
        assert tracker.target_quantity == 200.0
        assert tracker.max_inventory == 300.0
        assert tracker.urgency_base == 2.0
        
    def test_update_buy(self):
        """Test inventory update for buy orders."""
        tracker = InventoryTracker(target_quantity=100)
        
        pnl = tracker.update(
            filled_quantity=10,
            exec_price=8500.0,
            ref_price=8501.0,
            side='buy'
        )
        
        assert tracker.inventory == 10
        assert tracker.trade_count == 1
        # Buy savings = ref - exec = 8501 - 8500 = 1 per unit
        assert pnl == pytest.approx(10.0, rel=0.01)
        
    def test_update_sell(self):
        """Test inventory update for sell orders."""
        tracker = InventoryTracker(target_quantity=100)
        
        # First buy some
        tracker.update(10, 8500.0, 8501.0, side='buy')
        
        # Then sell
        pnl = tracker.update(
            filled_quantity=5,
            exec_price=8502.0,
            ref_price=8501.0,
            side='sell'
        )
        
        assert tracker.inventory == 5  # 10 - 5
        # Sell savings = exec - ref = 8502 - 8501 = 1 per unit
        assert pnl == pytest.approx(5.0, rel=0.01)
        
    def test_urgency_low_inventory(self):
        """Test urgency factor when inventory is low."""
        tracker = InventoryTracker(
            target_quantity=100,
            urgency_inventory_weight=0.5
        )
        
        # At start (0 inventory)
        urgency_start = tracker.get_urgency_factor(t=0, T=60)
        
        # Halfway
        tracker.update(50, 8500.0, 8500.0, side='buy')
        urgency_half = tracker.get_urgency_factor(t=30, T=60)
        
        # Urgency should decrease as inventory fills
        assert urgency_start > urgency_half
        
    def test_urgency_high_inventory(self):
        """Test urgency factor when inventory is high."""
        tracker = InventoryTracker(
            target_quantity=100,
            urgency_inventory_weight=0.5
        )
        
        # Fill all
        tracker.update(100, 8500.0, 8500.0, side='buy')
        urgency_full = tracker.get_urgency_factor(t=50, T=60)
        
        # Should be lower when full
        assert urgency_full < tracker.urgency_base * 2
        
    def test_urgency_time_pressure(self):
        """Test urgency factor increases with time pressure."""
        tracker = InventoryTracker(target_quantity=100)
        
        urgency_early = tracker.get_urgency_factor(t=10, T=60)
        urgency_late = tracker.get_urgency_factor(t=50, T=60)
        
        # Urgency should increase with time
        assert urgency_late > urgency_early
        
    def test_max_inventory_constraint(self):
        """Test max inventory constraint detection."""
        tracker = InventoryTracker(target_quantity=100, max_inventory=150)
        
        # Fill within limit
        tracker.update(100, 8500.0, 8500.0, side='buy')
        assert not tracker.is_max_exceeded()
        
        # Exceed limit
        tracker.update(100, 8500.0, 8500.0, side='buy')
        assert tracker.is_max_exceeded()
        
    def test_pnl_tracking(self):
        """Test PnL accumulation tracking."""
        tracker = InventoryTracker(target_quantity=100)
        
        # Multiple trades
        tracker.update(10, 8500.0, 8501.0, side='buy')  # +10
        tracker.update(10, 8499.0, 8500.0, side='buy')  # +10
        tracker.update(10, 8498.0, 8499.0, side='buy')  # +10
        
        assert tracker.total_pnl == pytest.approx(30.0, rel=0.01)
        assert tracker.trade_count == 3
        
    def test_get_stats(self):
        """Test statistics summary."""
        tracker = InventoryTracker(target_quantity=100)
        tracker.update(50, 8500.0, 8501.0, side='buy')
        
        stats = tracker.get_stats()
        
        assert stats['inventory'] == 50
        assert stats['target_quantity'] == 100
        assert stats['remaining'] == 50
        assert stats['fill_rate'] == 0.5
        assert not stats['is_complete']
        
    def test_reset(self):
        """Test reset functionality."""
        tracker = InventoryTracker(target_quantity=100)
        tracker.update(50, 8500.0, 8500.0, side='buy')
        
        tracker.reset()
        
        assert tracker.inventory == 0.0
        assert tracker.total_pnl == 0.0
        assert tracker.trade_count == 0
        assert len(tracker.trades) == 0
        
    def test_trade_history(self):
        """Test trade history retrieval."""
        tracker = InventoryTracker(target_quantity=100)
        
        tracker.update(10, 8500.0, 8501.0, timestamp=0, side='buy')
        tracker.update(10, 8501.0, 8502.0, timestamp=1, side='sell')
        
        history = tracker.get_trade_history()
        
        assert len(history) == 2
        assert history[0]['side'] == 'buy'
        assert history[1]['side'] == 'sell'


class TestInventoryAwareAgent:
    """Tests for InventoryAwareAgent class."""
    
    def test_calculate_utility(self):
        """Test utility calculation."""
        agent = InventoryAwareAgent(target_quantity=100, base_penalty=10.0)
        
        utility = agent.calculate_utility(
            expected_savings=5.0,
            fill_probability=0.8,
            t=30,
            T=60
        )
        
        # Utility = savings - (1 - prob) * penalty * urgency
        assert utility > 0  # Should be positive with 80% fill prob
        
    def test_execute_and_report(self):
        """Test execution and performance report."""
        agent = InventoryAwareAgent(target_quantity=100)
        
        # Execute some trades
        agent.execute(50, 8500.0, 8501.0, side='buy')
        agent.execute(50, 8499.0, 8500.0, side='buy')
        
        report = agent.get_performance_report()
        
        assert report['inventory'] == 100
        assert report['is_complete']
        assert report['win_rate'] == 1.0  # Both trades profitable


class TestCreateTracker:
    """Tests for create_tracker convenience function."""
    
    def test_create_tracker_default(self):
        """Test creating tracker with default max."""
        tracker = create_tracker(target=100)
        
        assert tracker.target_quantity == 100
        assert tracker.max_inventory == 150  # 1.5x target
        
    def test_create_tracker_custom_max(self):
        """Test creating tracker with custom max."""
        tracker = create_tracker(target=100, max_inv=200)
        
        assert tracker.max_inventory == 200


# ============================================================================
# State Transition Tests
# ============================================================================

class TestStateTransitionEstimator:
    """Tests for StateTransitionEstimator class."""
    
    def test_init(self):
        """Test initialization."""
        estimator = StateTransitionEstimator(n_states=3)
        
        assert estimator.n_states == 3
        assert estimator.smoothing == 0.01
        assert estimator.transition_matrix is None
        
    def test_fit(self):
        """Test fitting on state sequence."""
        estimator = StateTransitionEstimator(n_states=3)
        
        # Create simple sequence
        states = pd.Series([0, 0, 1, 1, 2, 2, 0, 1, 2, 0])
        
        P = estimator.fit(states)
        
        assert P.shape == (3, 3)
        # Each row should sum to 1
        assert np.allclose(P.sum(axis=1), 1.0)
        
    def test_matrix_row_sums_to_one(self):
        """Test that each row of transition matrix sums to 1."""
        estimator = StateTransitionEstimator(n_states=3)
        
        # Random sequence
        np.random.seed(42)
        states = pd.Series(np.random.randint(0, 3, 100))
        
        P = estimator.fit(states)
        
        row_sums = P.sum(axis=1)
        assert np.allclose(row_sums, 1.0)
        
    def test_predict_next_state(self):
        """Test next state prediction."""
        estimator = StateTransitionEstimator(n_states=3)
        
        states = pd.Series([0, 0, 0, 1, 1, 1, 2, 2, 2, 0])
        estimator.fit(states)
        
        dist = estimator.predict_next_state(0)
        
        assert len(dist) == 3
        assert abs(dist.sum() - 1.0) < 1e-6
        
    def test_predict_n_steps(self):
        """Test multi-step prediction."""
        estimator = StateTransitionEstimator(n_states=3)
        
        states = pd.Series(np.random.randint(0, 3, 200))
        estimator.fit(states)
        
        dist = estimator.predict_n_steps(current_state=0, n_steps=5)
        
        assert len(dist) == 3
        assert abs(dist.sum() - 1.0) < 1e-6
        
    def test_stationary_distribution(self):
        """Test stationary distribution calculation."""
        estimator = StateTransitionEstimator(n_states=3)
        
        states = pd.Series(np.random.randint(0, 3, 500))
        estimator.fit(states)
        
        stationary = estimator.get_stationary_distribution()
        
        assert len(stationary) == 3
        assert abs(stationary.sum() - 1.0) < 1e-6
        assert all(s >= 0 for s in stationary)
        
    def test_fit_from_returns(self):
        """Test fitting from return series."""
        estimator = StateTransitionEstimator(n_states=3)
        
        # Create returns
        np.random.seed(42)
        returns = pd.Series(np.random.randn(100) * 0.01)
        
        P = estimator.fit_from_returns(returns)
        
        assert P.shape == (3, 3)
        assert np.allclose(P.sum(axis=1), 1.0)
        
    def test_with_nan_values(self):
        """Test handling of NaN values."""
        estimator = StateTransitionEstimator(n_states=3)
        
        states = pd.Series([0, np.nan, 1, 1, np.nan, 2, 0])
        
        P = estimator.fit(states)
        
        assert P.shape == (3, 3)
        assert not np.any(np.isnan(P))


class TestStatePredictor:
    """Tests for StatePredictor class."""
    
    def test_update_and_predict(self):
        """Test updating and predicting."""
        predictor = StatePredictor(lookback=50, n_states=3)
        
        # Feed states
        np.random.seed(42)
        for _ in range(30):
            state = np.random.randint(0, 3)
            predictor.update(state)
            
        # Should be fitted now
        assert predictor.is_fitted
        
        # Predict
        dist = predictor.predict(current_state=0, steps=3)
        assert dist is not None
        assert len(dist) == 3


class TestEstimateTransitionFromData:
    """Tests for convenience function."""
    
    def test_with_state_column(self):
        """Test with existing state column."""
        df = pd.DataFrame({
            'prev_state': np.random.randint(0, 3, 100)
        })
        
        P, summary = estimate_transition_from_data(df, state_col='prev_state')
        
        assert P.shape == (3, 3)
        assert 'n_states' in summary
        
    def test_with_close_column(self):
        """Test deriving states from close prices."""
        df = pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(100) * 0.5)
        })
        
        P, summary = estimate_transition_from_data(df)
        
        assert P.shape == (3, 3)


# ============================================================================
# Dynamic Penalty Tests
# ============================================================================

class TestDynamicPenalty:
    """Tests for DynamicPenalty class."""
    
    def test_init(self):
        """Test initialization."""
        penalty = DynamicPenalty(base_penalty=10.0)
        
        assert penalty.base_penalty == 10.0
        assert penalty.max_penalty == 50.0
        assert penalty.schedule == PenaltySchedule.QUADRATIC
        
    def test_base_penalty(self):
        """Test base penalty at t=0."""
        penalty = DynamicPenalty(base_penalty=10.0)
        
        p = penalty.calculate(t=0, T=60)
        
        # At t=0, should be close to base
        assert p >= penalty.base_penalty
        
    def test_time_factor(self):
        """Test time factor increases penalty."""
        penalty = DynamicPenalty(
            base_penalty=10.0,
            time_weight=0.5,
            inventory_weight=0.0,
            volatility_weight=0.0
        )
        
        p_early = penalty.calculate(t=10, T=60)
        p_late = penalty.calculate(t=50, T=60)
        
        # Later = higher penalty
        assert p_late > p_early
        
    def test_inventory_factor(self):
        """Test inventory factor."""
        penalty = DynamicPenalty(
            base_penalty=10.0,
            time_weight=0.0,
            inventory_weight=0.5,
            volatility_weight=0.0
        )
        
        # No inventory filled
        p_none = penalty.calculate(t=30, T=60, current_inventory=0, target_inventory=100)
        
        # Half filled
        p_half = penalty.calculate(t=30, T=60, current_inventory=50, target_inventory=100)
        
        # Full
        p_full = penalty.calculate(t=30, T=60, current_inventory=100, target_inventory=100)
        
        # More filled = lower penalty
        assert p_none > p_half > p_full
        
    def test_combined_factors(self):
        """Test combined time and inventory factors."""
        penalty = DynamicPenalty(
            base_penalty=10.0,
            time_weight=0.5,
            inventory_weight=0.5
        )
        
        # Early, no inventory
        p1 = penalty.calculate(t=10, T=60, current_inventory=0, target_inventory=100)
        
        # Late, full inventory
        p2 = penalty.calculate(t=50, T=60, current_inventory=100, target_inventory=100)
        
        # Both should be different from base
        assert p1 != penalty.base_penalty
        assert p2 != penalty.base_penalty
        
    def test_boundary_conditions(self):
        """Test boundary conditions."""
        penalty = DynamicPenalty(base_penalty=10.0, max_penalty=50.0)
        
        # t=0
        p0 = penalty.calculate(t=0, T=60)
        
        # t=T
        pT = penalty.calculate(t=60, T=60)
        
        # t=0 should be lower
        assert p0 < pT
        
        # Should not exceed max
        assert pT <= penalty.max_penalty
        
    def test_penalty_schedules(self):
        """Test different penalty schedules."""
        T = 60
        
        schedules = {
            'constant': PenaltySchedule.CONSTANT,
            'linear': PenaltySchedule.LINEAR,
            'quadratic': PenaltySchedule.QUADRATIC
        }
        
        penalties = {}
        for name, schedule in schedules.items():
            p = DynamicPenalty(schedule=schedule)
            penalties[name] = p.get_penalty_schedule(T)
            
        # Constant should be flat
        assert np.allclose(penalties['constant'], penalties['constant'][0])
        
        # Linear should increase linearly
        linear_diff = np.diff(penalties['linear'])
        assert np.allclose(linear_diff, linear_diff[0], rtol=0.1)
        
        # Quadratic should accelerate
        quadratic_diff = np.diff(penalties['quadratic'])
        assert quadratic_diff[-1] > quadratic_diff[0]
        
    def test_max_cap(self):
        """Test that penalty is capped at max."""
        penalty = DynamicPenalty(base_penalty=10.0, max_penalty=20.0)
        
        # Even at end with no inventory
        p = penalty.calculate(t=60, T=60, current_inventory=0, target_inventory=100)
        
        assert p <= penalty.max_penalty


class TestAdaptivePenalty:
    """Tests for AdaptivePenalty class."""
    
    def test_adaptation(self):
        """Test penalty adaptation from fills."""
        penalty = AdaptivePenalty(
            base_penalty=10.0,
            adaptation_rate=0.2
        )
        
        # Simulate better than expected fills
        for _ in range(15):
            penalty.update_from_fill(
                filled=True,
                expected_fill_prob=0.5,
                penalty_used=15.0
            )
            
        # Adapted base should be lower (more aggressive)
        summary = penalty.get_adaptation_summary()
        assert summary['adaptation_ratio'] < 1.0
        
    def test_inherits_from_dynamic(self):
        """Test that AdaptivePenalty inherits from DynamicPenalty."""
        penalty = AdaptivePenalty()
        
        # Should have all DynamicPenalty methods
        assert hasattr(penalty, 'calculate')
        assert hasattr(penalty, 'get_penalty_schedule')
        assert hasattr(penalty, '_time_factor')


class TestCreatePenaltyFunction:
    """Tests for create_penalty_function convenience function."""
    
    def test_create_function(self):
        """Test creating penalty function."""
        func = create_penalty_function(schedule='quadratic', base=10.0)
        
        # Should be callable
        assert callable(func)
        
        # Should return penalty
        p = func(t=30, T=60)
        assert isinstance(p, float)
        assert p > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple modules."""
    
    def test_full_pipeline(self):
        """Test full pipeline with all modules."""
        # Setup
        tracker = InventoryTracker(target_quantity=100)
        penalty = DynamicPenalty(base_penalty=10.0)
        estimator = StateTransitionEstimator(n_states=3)
        
        # Simulate state sequence
        np.random.seed(42)
        states = pd.Series(np.random.randint(0, 3, 100))
        estimator.fit(states)
        
        # Simulate trading
        T = 60
        for t in range(T):
            # Get current penalty
            lambda_t = penalty.calculate(
                t=t, T=T,
                current_inventory=tracker.inventory,
                target_inventory=100
            )
            
            # Simulate trade
            if np.random.random() > 0.5:
                tracker.update(
                    filled_quantity=2,
                    exec_price=8500 - np.random.randn(),
                    ref_price=8500,
                    side='buy'
                )
                
        # Check final state
        stats = tracker.get_stats()
        assert stats['trade_count'] > 0
        assert stats['inventory'] > 0
        
    def test_with_synthetic_data(self):
        """Test with synthetic market data."""
        # Create synthetic data
        np.random.seed(42)
        n = 1000
        
        df = pd.DataFrame({
            'close': 8500 + np.cumsum(np.random.randn(n) * 1),
            'vol': np.abs(np.random.randn(n)) + 1
        })
        
        # Estimate states from returns
        estimator = StateTransitionEstimator(n_states=3)
        returns = df['close'].pct_change()
        P = estimator.fit_from_returns(returns)
        
        # Verify matrix is valid
        assert np.allclose(P.sum(axis=1), 1.0)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])