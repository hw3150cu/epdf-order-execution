# ePDF and Optimization Logic Review

## 1. ePDF (Empirical Probability Density Function) Logic

### Data Structure
```python
# Circular buffers for O(1) updates
self.range_dn_data[state]   # Downward price movements (open - low)
self.range_up_data[state]   # Upward price movements (high - open)
self.movement_data[state]   # Close prices (for expected close)

# Sorted arrays for O(log n) lookups
self.sorted_range_dn[state]  # Sorted range_dn for fast probability lookup
self.sorted_range_up[state]  # Sorted range_up for fast probability lookup
```

### Update Logic (O(1) operation)
```python
def update(state, range_dn, range_up, movement):
    ptr = self.ptrs[state]
    self.range_dn_data[state][ptr] = range_dn   # Store new observation
    self.range_up_data[state][ptr] = range_up
    self.movement_data[state][ptr] = movement

    # Update circular pointer
    self.ptrs[state] = (ptr + 1) % self.window_size

    # Sort for fast lookup (only when needed)
    self.sorted_range_dn[state] = np.sort(valid_dn)
    self.sorted_range_up[state] = np.sort(valid_up)
```

### Fill Probability Calculation (O(log n) operation)
```python
def get_fill_prob(state, level, direction):
    # For buy orders: P(price goes down >= level)
    # For sell orders: P(price goes up >= level)

    if direction == 'buy':
        sorted_data = self.sorted_range_dn[state]  # Use range_dn
    else:  # sell
        sorted_data = self.sorted_range_up[state]  # Use range_up

    # Binary search to find first index where value >= level
    idx = np.searchsorted(sorted_data, level, side='left')
    count_ge = len(sorted_data) - idx

    # Probability = count >= level / total count
    return count_ge / len(sorted_data)
```

**Example:**
- Historical range_dn: [1.0, 2.0, 1.5, 3.0, 0.5] → sorted: [0.5, 1.0, 1.5, 2.0, 3.0]
- Query level = 1.5 ticks
- searchsorted returns idx = 2
- count_ge = 5 - 2 = 3 (values: 1.5, 2.0, 3.0)
- fill_prob = 3/5 = 60%

### Expected Movement Calculation
```python
def get_expected_range_dn(state):
    # Expected downward movement (for buy order penalty)
    return np.mean(self.range_dn_data[state])

def get_expected_range_up(state):
    # Expected upward movement (for sell order penalty)
    return np.mean(self.range_up_data[state])
```

---

## 2. Optimization Logic

### Objective Function
```python
def _objective(x, state, direction, penalty):
    """
    x = [p1, p2, p3, w1, w2, w3]
    - p1, p2, p3: Limit order levels (ticks from open)
    - w1, w2, w3: Order weights (allocation, sum to 1.0)
    """
    levels = [p1, p2, p3]
    weights = [w1, w2, w3]

    # Get fill probabilities for each level
    probs = [get_fill_prob(state, level, direction) for level in levels]

    # Calculate utility components
    fill_prob = sum(w * p for w, p in zip(weights, probs))
    reward = sum(w * p * l for w, p, l in zip(weights, probs, levels))
    miss_penalty = (1.0 - fill_prob) * penalty

    # Maximize: reward - miss_penalty
    return -(reward - miss_penalty)  # Minimize negative utility
```

### Utility Formula
$$U = \underbrace{\sum_{i=1}^{3} w_i \cdot P_i \cdot l_i}_{\text{Expected Savings}} - \underbrace{(1 - \sum_{i=1}^{3} w_i \cdot P_i) \cdot \text{penalty}}_{\text{Expected Miss Cost}}$$

**Example Calculation:**
- levels = [0.5, 1.5, 3.0], weights = [0.3, 0.4, 0.3]
- probs = [0.8, 0.5, 0.2], penalty = 5.0

```
fill_prob = 0.3×0.8 + 0.4×0.5 + 0.3×0.2 = 0.50 (50% overall fill probability)
reward = 0.3×0.8×0.5 + 0.4×0.5×1.5 + 0.3×0.2×3.0 = 0.63 ticks
miss_penalty = (1 - 0.50) × 5.0 = 2.50 ticks
utility = 0.63 - 2.50 = -1.87 ticks
```

### Direction-Aware Penalty
```python
# For buy orders: penalty = expected upward movement
# If price goes up, we miss our buy limit orders
if direction == 'buy':
    expected_movement = self.epdf.get_expected_range_up(state)

# For sell orders: penalty = expected downward movement
# If price goes down, we miss our sell limit orders
else:  # sell
    expected_movement = self.epdf.get_expected_range_dn(state)

penalty = max(self.min_penalty, expected_movement)
```

### Multi-Start SLSQP Optimization
```python
# Pre-defined starting points to escape local minima
starting_points = [
    [0., 1., 2., 1./3., 1./3., 1./3.],  # Default
    [0., 0.5, 1., 1./3., 1./3., 1./3.],  # Tight levels
    [0., 2., 4., 1./3., 1./3., 1./3.],  # Spread out
    [1., 3., 5., 1./3., 1./3., 1./3.],  # Wider spread
    [0., 1., 2., 0.5, 0.5, 0.0],        # Biased weights
    [2., 4., 6., 1./3., 1./3., 1./3.],  # High levels
]

# Run SLSQP from each starting point
best_result = None
best_obj = float('inf')

for x0 in starting_points:
    result = minimize(_objective, x0, method='SLSQP', ...)
    if result.success and result.fun < best_obj:
        best_result = result
        best_obj = result.fun

# Normalize weights to sum to 1.0
w = w / w.sum()
return [(p[0], w[0]), (p[1], w[1]), (p[2], w[2])]
```

### Constraints
```python
# Bounds: 0 <= p_i <= max_level, 0 <= w_i <= 1
bounds = [(0., max_level)]*3 + [(0., 1.)]*3

# Constraint: w1 + w2 + w3 = 1.0
cons = {'type': 'eq', 'fun': lambda x: sum(x[3:6]) - 1.}
```

---

## 3. Round Down Logic

### Optimization Results (NOT Rounded)
```python
# Optimization returns raw floats
p = [0.7, 2.3, 4.8]  # Levels in ticks (can be fractional)
w = [0.4, 0.35, 0.25]  # Weights (normalized to sum to 1.0)

# Returns: [(0.7, 0.4), (2.3, 0.35), (4.8, 0.25)]
```

### Savings Calculation (NOT Rounded)
```python
# Buy gap calculation
buy_gap = open - low  # In dollars

# Savings calculation (levels are already in ticks)
for level, weight in limits:
    if buy_gap >= level * tick_size:
        buy_save += weight * level  # Save in tick units

# Example:
# buy_gap = $2.00, tick_size = $0.25
# buy_gap_ticks = 2.00 / 0.25 = 8.0 ticks
# limits = [(0.7, 0.4), (2.3, 0.35), (4.8, 0.25)]

# Check fills:
# 0.7t: 0.7 * 0.25 = $0.175 <= $2.00 ✓ fills
# 2.3t: 2.3 * 0.25 = $0.575 <= $2.00 ✓ fills
# 4.8t: 4.8 * 0.25 = $1.20 <= $2.00 ✓ fills

# Savings:
# buy_save = 0.4*0.7 + 0.35*2.3 + 0.25*4.8 = 2.355 ticks (NOT rounded)
```

### Display Values (Rounded for output)
```python
# When displaying results, we round to 1-2 decimal places
print(f"Optimized savings: {total_savings:.1f} ticks")

# But internal calculations use full precision
```

### Trade Records (Full Precision)
```python
trade_records.append({
    'timestamp': current_time,
    'optimized_buy_savings': buy_save,  # Full precision
    'optimized_sell_savings': sell_save,  # Full precision
    'optimized_total_savings': total_save,  # Full precision
    'optimized_limits': str(limits),  # Full precision
    ...
})
```

---

## 4. Key Observations

### What's Working Well
✅ **Circular buffer design**: O(1) updates, O(log n) lookups
✅ **Direction-aware fill probability**: buy→range_dn, sell→range_up
✅ **Direction-aware penalty**: buy→upward movement, sell→downward movement
✅ **Multi-start optimization**: 6 starting points to escape local minima
✅ **Full precision in calculations**: No premature rounding

### Potential Issues
⚠️ **Fractional limit levels**: Optimization returns 0.7, 2.3, 4.8 ticks
   - Real exchanges require integer ticks (0, 1, 2, 3, ...)
   - Should we round levels to integers?

⚠️ **Weight allocation**: 0.4, 0.35, 0.25 - how to split order size?
   - If order size = 10 contracts, how to allocate 4, 3.5, 2.5?
   - Should weights be multiples of 1/N where N is order size?

⚠️ **No integer constraints**: Optimization allows fractional ticks
   - May need to add discrete optimization or post-rounding

---

## 5. Recommendations

### For Real-World Implementation
1. **Round limit levels to integers**:
   ```python
   levels = [round(p) for p, w in limits]  # [0.7, 2.3, 4.8] → [1, 2, 5]
   ```

2. **Adjust weights for integer allocation**:
   ```python
   # If order size = 10, allocate 4, 3, 3 contracts (sums to 10)
   weights_int = [int(w * order_size) for w in weights]
   ```

3. **Consider discrete optimization**:
   - Use integer programming or grid search
   - Ensure levels and weights are realistic

### For Backtesting
✅ Keep current approach with full precision for theoretical analysis
✅ Add rounding step when simulating real trading

---

## 6. Performance Metrics

### Current Results (Window=60)
- **Agent baseline**: 3,473 ticks
- **Optimized strategy**: 2,711 ticks (-22.0% worse)
- **Still underperforming** - need further investigation

### Possible Reasons for Underperformance
1. **Optimization target**: Maybe maximizing expected savings isn't the right objective
2. **State detection**: Current 2-state (Low/High) may not capture market dynamics
3. **Penalty calibration**: min_penalty=5.0 may be too high
4. **Fill probability**: Historical distribution may not predict future fills well
5. **Agent strategy**: Agent may be using better execution than simple limit orders

### Next Steps for Investigation
1. Analyze individual trades to understand where strategy fails
2. Compare agent's execution prices vs our limit order prices
3. Check if state detection is working correctly
4. Try different penalty values
5. Consider alternative utility functions