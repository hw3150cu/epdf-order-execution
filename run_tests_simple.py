"""
Simple test runner without pytest dependency.
Run: python run_tests_simple.py
"""

import numpy as np
import pandas as pd
import sys

# Import modules
from inventory_tracker import InventoryTracker, InventoryAwareAgent, create_tracker
from state_transition import StateTransitionEstimator, StatePredictor, estimate_transition_from_data
from dynamic_penalty import DynamicPenalty, AdaptivePenalty, PenaltySchedule, create_penalty_function

def test_inventory_tracker():
    """Test InventoryTracker."""
    print("\n=== Testing InventoryTracker ===")
    
    # Test init
    tracker = InventoryTracker()
    assert tracker.target_quantity == 100.0
    assert tracker.inventory == 0.0
    print("  ✓ Init")
    
    # Test buy update
    pnl = tracker.update(10, 8500.0, 8501.0, side='buy')
    assert tracker.inventory == 10
    assert abs(pnl - 10.0) < 0.01
    print("  ✓ Buy update")
    
    # Test sell update
    pnl = tracker.update(5, 8502.0, 8501.0, side='sell')
    assert tracker.inventory == 5
    print("  ✓ Sell update")
    
    # Test urgency
    tracker2 = InventoryTracker(target_quantity=100)
    u_early = tracker2.get_urgency_factor(t=10, T=60)
    u_late = tracker2.get_urgency_factor(t=50, T=60)
    assert u_late > u_early
    print("  ✓ Urgency increases with time")
    
    # Test stats
    stats = tracker2.get_stats()
    assert 'inventory' in stats
    assert 'total_pnl' in stats
    print("  ✓ Stats")
    
    print("  All InventoryTracker tests passed!")
    return True

def test_state_transition():
    """Test StateTransitionEstimator."""
    print("\n=== Testing StateTransitionEstimator ===")
    
    # Test init
    estimator = StateTransitionEstimator(n_states=3)
    assert estimator.n_states == 3
    print("  ✓ Init")
    
    # Test fit
    states = pd.Series([0, 0, 1, 1, 2, 2, 0, 1, 2, 0])
    P = estimator.fit(states)
    assert P.shape == (3, 3)
    assert np.allclose(P.sum(axis=1), 1.0)
    print("  ✓ Fit and row sums = 1")
    
    # Test predict
    dist = estimator.predict_next_state(0)
    assert len(dist) == 3
    assert abs(dist.sum() - 1.0) < 1e-6
    print("  ✓ Predict next state")
    
    # Test multi-step predict
    dist = estimator.predict_n_steps(0, 5)
    assert len(dist) == 3
    print("  ✓ Predict n steps")
    
    # Test stationary distribution
    stationary = estimator.get_stationary_distribution()
    assert abs(stationary.sum() - 1.0) < 1e-6
    print("  ✓ Stationary distribution")
    
    # Test fit from returns
    returns = pd.Series(np.random.randn(100) * 0.01)
    P = estimator.fit_from_returns(returns)
    assert np.allclose(P.sum(axis=1), 1.0)
    print("  ✓ Fit from returns")
    
    print("  All StateTransition tests passed!")
    return True

def test_dynamic_penalty():
    """Test DynamicPenalty."""
    print("\n=== Testing DynamicPenalty ===")
    
    # Test init
    penalty = DynamicPenalty(base_penalty=10.0)
    assert penalty.base_penalty == 10.0
    print("  ✓ Init")
    
    # Test base penalty
    p = penalty.calculate(t=0, T=60)
    assert p >= penalty.base_penalty
    print("  ✓ Base penalty")
    
    # Test time factor
    p_early = penalty.calculate(t=10, T=60)
    p_late = penalty.calculate(t=50, T=60)
    assert p_late > p_early
    print("  ✓ Time factor increases penalty")
    
    # Test inventory factor
    penalty2 = DynamicPenalty(time_weight=0.0, inventory_weight=0.5)
    p_none = penalty2.calculate(t=30, T=60, current_inventory=0, target_inventory=100)
    p_full = penalty2.calculate(t=30, T=60, current_inventory=100, target_inventory=100)
    assert p_none > p_full
    print("  ✓ Inventory factor")
    
    # Test max cap
    p = penalty.calculate(t=60, T=60, current_inventory=0, target_inventory=100)
    assert p <= penalty.max_penalty
    print("  ✓ Max cap")
    
    # Test schedules
    p_quad = DynamicPenalty(schedule=PenaltySchedule.QUADRATIC)
    schedule = p_quad.get_penalty_schedule(60)
    assert len(schedule) == 60
    print("  ✓ Penalty schedule")
    
    print("  All DynamicPenalty tests passed!")
    return True

def test_integration():
    """Test integration of all modules."""
    print("\n=== Testing Integration ===")
    
    # Setup
    tracker = InventoryTracker(target_quantity=100)
    penalty = DynamicPenalty(base_penalty=10.0)
    estimator = StateTransitionEstimator(n_states=3)
    
    # Fit states
    states = pd.Series(np.random.randint(0, 3, 100))
    estimator.fit(states)
    
    # Simulate trading
    T = 60
    for t in range(T):
        lambda_t = penalty.calculate(
            t=t, T=T,
            current_inventory=tracker.inventory,
            target_inventory=100
        )
        
        if np.random.random() > 0.5:
            tracker.update(2, 8500 - np.random.randn(), 8500, side='buy')
    
    stats = tracker.get_stats()
    assert stats['trade_count'] > 0
    print(f"  ✓ Full pipeline: {stats['trade_count']} trades, inventory={stats['inventory']}")
    
    print("  All Integration tests passed!")
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("Running Stochastic Control Module Tests")
    print("=" * 60)
    
    np.random.seed(42)
    
    results = []
    
    try:
        results.append(("InventoryTracker", test_inventory_tracker()))
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        results.append(("InventoryTracker", False))
    
    try:
        results.append(("StateTransition", test_state_transition()))
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        results.append(("StateTransition", False))
    
    try:
        results.append(("DynamicPenalty", test_dynamic_penalty()))
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        results.append(("DynamicPenalty", False))
    
    try:
        results.append(("Integration", test_integration()))
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        results.append(("Integration", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"  {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)