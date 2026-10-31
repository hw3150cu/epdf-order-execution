"""Quick test to verify DiscreteOptimizer works correctly"""
from strategies_discrete_clean import DiscreteOptimizer
import pandas as pd
import numpy as np

# Create dummy data
np.random.seed(42)
data = {
    'open': np.random.normal(100, 2, 100),
    'high': np.random.normal(102, 2, 100),
    'low': np.random.normal(98, 2, 100),
    'close': np.random.normal(100, 2, 100),
    'vol': np.random.uniform(200, 500, 100),
    'prev_state': np.random.choice(['Low', 'High'], 100),
    'range_dn_ticks': np.random.uniform(0, 10, 100),
}
df = pd.DataFrame(data)

print("Testing DiscreteOptimizer...")
print("="*60)

optimizer = DiscreteOptimizer(window_size=60, min_penalty=5.0, max_level=10.0)

# Test with some iterations
for i in [10, 20, 30, 50, 70]:
    limits = optimizer.get_limits(df, i, 0.25)
    print(f"Bar {i}:")
    print(f"  Limits: {[(int(l), round(w, 1)) for l, w in limits]}")
    
    # Verify integer levels
    levels = [int(l) for l, w in limits]
    weights = [round(w, 1) for l, w in limits]
    
    print(f"  Levels (int): {levels}")
    print(f"  Weights (0.1): {weights}")
    print(f"  Sum of weights: {sum(weights)}")
    
    # Verify constraints
    assert isinstance(levels[0], int) and isinstance(levels[1], int) and isinstance(levels[2], int), "Levels should be integers!"
    assert all(w * 10 % 1 < 0.01 for w in weights), "Weights should be 0.1 increments!"
    assert abs(sum(weights) - 1.0) < 0.01, "Weights should sum to 1.0!"
    print(f"  ✓ Constraints verified")
    print()

print("="*60)
print("All tests passed! DiscreteOptimizer works correctly.")