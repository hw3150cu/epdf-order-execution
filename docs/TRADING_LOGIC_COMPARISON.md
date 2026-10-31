# Trading Logic Comparison: Old vs New
## Detailed Analysis for Term Project 2

---

## 1. PDF Requirements Summary

### 1.1 Data
- **1-min OHLC** with volume
- **Tick size (ϵ)**: Minimum price fluctuation per contract
- **Holding periods (τ)**: 5, 10, 15, 30, 45, 60 minutes

### 1.2 Core Metrics (All in Ticks)
| Metric | Formula | Description |
|--------|---------|-------------|
| **Range** | R = H - L = ℓϵ | Total price range |
| **RangeUp** | R^(U) = H - O = ℓ₁ϵ | Upper wick |
| **RangeDn** | R^(D) = O - L = ℓ₂ϵ | Lower wick |

### 1.3 ePDF Construction
```
P(R = ℓϵ | v ∈ m, σ ∈ n, Δx ∈ k)
```

### 1.4 Fill Probability (Direction-Dependent)

**BUY Order:**
```
P(Fill | level=k, direction=BUY) = P(RangeDn >= k)
```
- Limit price = Open - k × tick
- Fill condition: Low <= Limit price

**SELL Order:**
```
P(Fill | level=k, direction=SELL) = P(RangeUp >= k)
```
- Limit price = Open + k × tick
- Fill condition: High >= Limit price

---

## 2. Single Bar (1-min) Execution Flow

### 2.1 Scenario Setup

**Assumptions:**
- We have a **BUY** signal at bar t
- Reference price = `close[t-1]` (previous bar's close)
- Current bar data: `open[t]`, `high[t]`, `low[t]`, `close[t]`
- Tick size = 0.25

**Example Data:**
```
Bar t-1: O=3881.00, H=3882.00, L=3880.50, C=3881.50
Bar t:   O=3881.50, H=3883.00, L=3880.00, C=3882.50
```

---

## 3. OLD VERSION (strategies_optimized_final.py)

### 3.1 Trading Logic

```
Step 1: Get State
─────────────────
state = "Low" or "High" (from EWMA/EWMV)

Step 2: Get Optimal Limits
─────────────────────────
limits = optimizer.get_limits(df, i, tick)
# Returns: [(level1, weight1), (level2, weight2), (level3, weight3)]
# Example: [(0, 0.3), (1, 0.4), (2, 0.3)]

Step 3: Place Limit Orders
──────────────────────────
For BUY order:
  Limit_1 = open[t] - level1 * tick = 3881.50 - 0*0.25 = 3881.50
  Limit_2 = open[t] - level2 * tick = 3881.50 - 1*0.25 = 3881.25
  Limit_3 = open[t] - level3 * tick = 3881.50 - 2*0.25 = 3881.00

Step 4: Check Fill (Using Real Price)
─────────────────────────────────────
gap = open[t] - low[t] = 3881.50 - 3880.00 = 1.50 = 6 ticks

For each (level, weight):
  if gap >= level:
    filled_quantity += weight * total_quantity
    savings += weight * level  # in ticks

Example:
  level=0: gap=6 >= 0 ✓ → filled, savings += 0.3 * 0 = 0
  level=1: gap=6 >= 1 ✓ → filled, savings += 0.4 * 1 = 0.4
  level=2: gap=6 >= 2 ✓ → filled, savings += 0.3 * 2 = 0.6
  
  Total savings = 1.0 ticks

Step 5: No Fill Handling (IMPLICIT)
───────────────────────────────────
If gap < level for ALL levels:
  → Order not filled
  → No explicit penalty in current code!
  → Savings = 0 for that bar
```

### 3.2 Optimization Logic

```python
# Objective Function
def objective(x):
    p1, p2, p3, w1, w2, w3 = x
    levels = [p1, p2, p3]
    weights = [w1, w2, w3]
    
    # Fill probabilities from ePDF
    probs = [epdf.get_fill_prob(state, l) for l in levels]
    
    # Expected reward
    fill_prob = sum(w * pr for w, pr in zip(weights, probs))
    reward = sum(w * pr * l for w, pr, l in zip(weights, probs, levels))
    
    # Penalty for missing
    miss_penalty = (1 - fill_prob) * penalty
    
    # Utility = Reward - Penalty
    utility = reward - miss_penalty
    
    return -utility  # Minimize negative = Maximize positive

# Constraints
sum(weights) = 1
0 <= levels <= max_level
0 <= weights <= 1
```

### 3.3 Utility Function

```
U = Σᵢ wᵢ × P(fill|levelᵢ) × levelᵢ  -  (1 - Σᵢ wᵢ × P(fill|levelᵢ)) × λ

Where:
- wᵢ = weight for level i
- P(fill|levelᵢ) = P(RangeDn >= levelᵢ) from ePDF
- levelᵢ = price level in ticks
- λ = penalty parameter (fixed at 5-10 ticks)
```

### 3.4 Problems with Old Version

| Issue | Description |
|-------|-------------|
| **No explicit penalty** | If order not filled, savings=0 but no real penalty |
| **Fixed penalty λ** | λ is constant, not state-dependent |
| **No inventory tracking** | Each bar optimized independently |
| **No state transition** | Doesn't consider future state probability |

---

## 4. NEW VERSION (Enhanced with Stochastic Control)

### 4.1 Trading Logic

```
Step 1: Get State
─────────────────
state = "Low" or "High" (from EWMA/EWMV)

Step 2: Calculate Dynamic Penalty
─────────────────────────────────
# Expected penalty based on state and ePDF
expected_next_open = close[t-1] + epdf.get_expected_movement(state)
expected_penalty = max(expected_next_open, close[t-1] + tick)

Step 3: Get Optimal Limits (with inventory awareness)
─────────────────────────────────────────────────────
limits = optimizer.get_limits_enhanced(
    df, i, tick, 
    inventory=current_inventory,
    target=target_quantity,
    penalty=expected_penalty
)

Step 4: Place Limit Orders
──────────────────────────
(Same as old version)

Step 5: Check Fill (Using Real Price)
─────────────────────────────────────
(Same as old version)

Step 6: Handle No Fill (EXPLICIT PENALTY)
─────────────────────────────────────────
If order NOT filled:
  # Real penalty at next bar
  next_open = open[t+1]
  execution_price = max(next_open, close[t] + tick)
  penalty = execution_price - reference_price
```

### 4.2 Optimization Logic

```python
# Enhanced Objective Function
def objective(x, state, inventory, target, t, T):
    p1, p2, p3, w1, w2, w3 = x
    levels = [p1, p2, p3]
    weights = [w1, w2, w3]
    
    # Fill probabilities from ePDF
    probs = [epdf.get_fill_prob(state, l) for l in levels]
    
    # Expected reward
    fill_prob = sum(w * pr for w, pr in zip(weights, probs))
    reward = sum(w * pr * l for w, pr, l in zip(weights, probs, levels))
    
    # Dynamic penalty (state-dependent)
    expected_penalty = calculate_expected_penalty(state, close[t-1], tick)
    
    # Urgency factor (inventory-time aware)
    urgency = get_urgency_factor(inventory, target, t, T)
    
    # Enhanced penalty
    miss_penalty = (1 - fill_prob) * expected_penalty * urgency
    
    # Utility = Reward - Penalty
    utility = reward - miss_penalty
    
    return -utility
```

### 4.3 Utility Function (Enhanced)

```
U = Σᵢ wᵢ × P(fill|levelᵢ) × levelᵢ  -  (1 - Σᵢ wᵢ × P(fill|levelᵢ)) × λ(state,t,I)

Where:
- wᵢ = weight for level i
- P(fill|levelᵢ) = P(RangeDn >= levelᵢ) from ePDF
- levelᵢ = price level in ticks
- λ(state,t,I) = dynamic penalty function

Dynamic Penalty:
  λ(state, t, I) = λ_base × f(state) × g(t, T) × h(I, target)
  
  f(state) = volatility adjustment
  g(t, T) = time pressure = 1 + α × (1 - (T-t)/T)
  h(I, target) = inventory pressure = 1 + β × (I/target - 1)
```

### 4.4 Real Penalty Calculation (Simplified)

**Current Implementation (Simple):**
```python
def calculate_penalty(next_open, reference_price, direction):
    """
    Simple penalty = next_open - reference_price
    
    For BUY:  penalty = next_open - reference (positive if price went up)
    For SELL: penalty = reference - next_open (positive if price went down)
    """
    if direction == 'buy':
        return next_open - reference_price
    else:
        return reference_price - next_open
```

**Example:**
```
BUY Order:
  reference = 3881.50
  next_open = 3882.50 (price went up)
  penalty = 3882.50 - 3881.50 = 1.00 = 4 ticks (bad for buyer)

  reference = 3881.50
  next_open = 3880.50 (price went down)
  penalty = 3880.50 - 3881.50 = -1.00 = -4 ticks (good for buyer)

SELL Order:
  reference = 3881.50
  next_open = 3880.50 (price went down)
  penalty = 3881.50 - 3880.50 = 1.00 = 4 ticks (bad for seller)

  reference = 3881.50
  next_open = 3882.50 (price went up)
  penalty = 3881.50 - 3882.50 = -1.00 = -4 ticks (good for seller)
```

**TODO: Future Enhancements for Penalty:**
1. State-dependent penalty: λ(state) based on volatility regime
2. Time-dependent penalty: λ(t, T) increases as time runs out
3. Inventory-dependent penalty: λ(I, target) based on remaining quantity
4. Combined: λ(state, t, I) = λ_base × f(state) × g(t,T) × h(I,target)
5. Expected penalty: E[max(next_open, close+tick) | state] for optimization

---

## 5. Comparison Summary

### 5.1 Trading Logic

| Step | Old Version | New Version |
|------|-------------|-------------|
| State Detection | EWMA/EWMV | EWMA/EWMV (same) |
| Limit Optimization | SLSQP | SLSQP + inventory awareness |
| Fill Check | `gap >= level` | `gap >= level` (same) |
| No Fill Handling | Implicit (savings=0) | **Explicit penalty** |

### 5.2 Optimization Logic

| Aspect | Old Version | New Version |
|--------|-------------|-------------|
| Penalty | Fixed λ = 5-10 | **Dynamic λ(state, t, I)** |
| Inventory | Not tracked | **Tracked and used** |
| State Transition | Not used | **Used for multi-period** |

### 5.3 Utility Function

| Component | Old Version | New Version |
|-----------|-------------|-------------|
| Reward | `Σ wᵢ × Pᵢ × levelᵢ` | Same |
| Penalty | `(1-fill_prob) × λ` | **(1-fill_prob) × λ(state,t,I)** |
| λ | Fixed | **State + Time + Inventory dependent** |

---

## 6. Single Bar Execution Example

### 6.1 Setup
```
Bar t-1: close = 3881.50
Bar t:   open=3881.50, high=3883.00, low=3880.00, close=3882.50
Bar t+1: open=3882.75
Tick = 0.25
State = "Low"
Target quantity = 100 shares
Current inventory = 0
```

### 6.2 Old Version Execution

```
1. Get limits: [(0, 0.3), (1, 0.4), (2, 0.3)]

2. Place orders:
   - 30 shares @ 3881.50 (level 0)
   - 40 shares @ 3881.25 (level 1)
   - 30 shares @ 3881.00 (level 2)

3. Check fill:
   gap = 3881.50 - 3880.00 = 6 ticks
   
   All levels filled (6 >= 0, 1, 2)
   
4. Calculate savings:
   savings = 0.3*0 + 0.4*1 + 0.3*2 = 1.0 tick
   
5. If NOT filled (hypothetically):
   savings = 0 (no explicit penalty)
```

### 6.3 New Version Execution

```
1. Calculate expected penalty:
   expected_movement = epdf.get_expected_close("Low") = 0.5 ticks
   expected_next_open = 3881.50 + 0.5*0.25 = 3881.625
   expected_penalty = max(3881.625, 3881.75) = 3881.75

2. Get limits (with inventory awareness):
   urgency = 0.5 (mid-period)
   enhanced_penalty = expected_penalty * urgency
   limits = optimizer.get_limits_enhanced(...)

3. Place orders: (same as old)

4. Check fill: (same as old)

5. If NOT filled:
   next_open = 3882.75
   execution_price = max(3882.75, 3882.50 + 0.25) = 3882.75
   real_penalty = 3882.75 - 3881.50 = 1.25 = 5 ticks
```

---

## 7. What If T Minutes Without Fill?

### 7.1 Problem Statement

If we have a T-minute execution window and place limit orders each minute, what happens if we never get filled?

### 7.2 Old Version (Implicit)

```
For each bar t in [0, T):
  place limit orders
  if not filled:
    savings[t] = 0  # No penalty!

Total savings = Σ savings[t]  # Could be 0 if never filled
```

**Problem**: No penalty for missing the entire execution window!

### 7.3 New Version (Explicit)

```
For each bar t in [0, T):
  place limit orders
  if not filled:
    # Must execute at worse price
    execution_price = max(open[t+1], close[t] + tick)
    penalty[t] = execution_price - reference_price

At T:
  if still have inventory:
    # Must market order at T
    final_execution = close[T]
    final_penalty = final_execution - reference_price
```

### 7.4 Expected vs Real Penalty

| Type | When Used | Calculation |
|------|-----------|-------------|
| **Expected Penalty** | Optimization (before execution) | `E[max(next_open, close+tick) | state]` |
| **Real Penalty** | Execution (after no fill) | `max(actual_next_open, close+tick)` |

---

## 8. Implementation Checklist

### 8.1 Must Fix

- [ ] Add explicit penalty for no-fill scenario
- [ ] Calculate real penalty = `max(next_open, close + tick)`
- [ ] Use expected penalty in optimization

### 8.2 Enhancements

- [ ] Add inventory tracking
- [ ] Add state transition matrix
- [ ] Add dynamic penalty function

### 8.3 Testing

- [ ] Test single bar execution
- [ ] Test no-fill penalty calculation
- [ ] Compare old vs new backtest results

---

## 9. Key Formulas

### 9.1 Fill Probability (Direction-Dependent)

**BUY Order:**
```
P(Fill | level=k, state=s, direction=BUY) = P(RangeDn >= k | state=s)
                                          = count(RangeDn >= k) / total_count
```

**SELL Order:**
```
P(Fill | level=k, state=s, direction=SELL) = P(RangeUp >= k | state=s)
                                           = count(RangeUp >= k) / total_count
```

### 9.2 Expected Utility (Old)
```
U = Σᵢ wᵢ × Pᵢ × kᵢ - (1 - Σᵢ wᵢ × Pᵢ) × λ
```

### 9.3 Expected Utility (New)
```
U = Σᵢ wᵢ × Pᵢ × kᵢ - (1 - Σᵢ wᵢ × Pᵢ) × λ(state, t, I)

Where:
λ(state, t, I) = E[max(next_open, close+tick) | state] × urgency(t, I)
```

### 9.4 Real Penalty
```
penalty_real = max(next_open, close + tick) - reference_price
```

---

*Document created: Feb 27, 2026*
*Based on: TermProject2_OrderExecution.pdf and existing code analysis*