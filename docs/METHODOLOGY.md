# Utility-Based Limit Order Optimization Methodology

## 1. Problem Statement

**Goal:** Optimize order execution for buying futures (Nasdaq futures, NQ) using limit orders at strategic price levels to maximize expected savings while managing fill risk.

**Core Trade-off:**
- **Aggressive orders (lower prices)** → Higher savings if filled, but lower fill probability
- **Conservative orders (higher prices)** → Higher fill probability, but lower savings

**Solution:** Utility function balancing expected savings against penalty for missing fills.

---

## 2. Reference Prices & Backtest Logic

### 2.1 Reference Price for Limit Orders

**Critical Question:** What price do we use as the reference when placing limit orders?

**Answer:** We use the **previous bar's close price** as the reference. This is the most realistic backtest assumption because:
- At time `t`, we know the close of bar `t-1`
- We don't know the open, high, or low of bar `t` yet (no look-ahead bias)

### 2.2 Limit Order Placement

For a **buy order** at bar index `t`:

1. **Reference price:** `ref_price = close[t-1]`
2. **Price levels:** `[0.0, 1.0, 2.0]` ticks from reference
3. **Limit prices:**
   ```
   level_0: limit_price_0 = ref_price - 0.0 × tick_size = close[t-1]
   level_1: limit_price_1 = ref_price - 1.0 × tick_size = close[t-1] - $0.25
   level_2: limit_price_2 = ref_price - 2.0 × tick_size = close[t-1] - $0.50
   ```
4. **Weights:** Optimized by utility function (e.g., `[0.4, 0.3, 0.3]`)

### 2.3 Fill Logic

For each bar `t`, we check if limit orders filled:

```
For each level i:
  if bar[t].low <= limit_price_i:
     Order i fills at limit_price_i
  else:
     Order i does NOT fill

If NO orders fill:
     Must buy at bar[t].close (market order)
```

**Key insight:** Only unfilled portion executes at close price.

**Example:**
- Reference: `close[t-1] = 15,000.00`
- Limit orders: `14,999.50` (50% weight), `14,999.25` (50% weight)
- Bar `t`: `low = 14,999.30`, `close = 15,001.50`

Outcome:
- First order fills at `14,999.50` (since `14,999.30 <= 14,999.50`)
- Second order MISSES (price never reached `14,999.25`)
- Execution price: `0.5 × 14,999.50 + 0.5 × 15,001.50 = 15,000.50`
- Savings: `close[t-1] - execution_price = 15,000.00 - 15,000.50 = -0.5 ticks` (loss)

---

## 3. ePDF Construction (Historical Price Distribution)

### 3.1 What Does ePDF Track?

**Feature:** `range_dn_ticks` (range-down in ticks) from open to low:

```
range_dn_ticks = (open - low) / tick_size
```

**Interpretation:** How many ticks did the price drop from open to the lowest point?

**Example:**
- `open = 15,001.00`, `low = 15,000.00`
- `range_dn_ticks = (15,001 - 15,000) / 0.25 = 4.0 ticks`

### 3.2 Volatility-State Detection

We use **EWMA/EWMV** (Exponential Moving Average/Variance) to categorize volatility:

- **Low volatility:** `ewmv < 1.5σ`
- **Medium volatility:** `1.5σ ≤ ewmv < 3.0σ`
- **High volatility:** `ewmv ≥ 3.0σ`

**Key:** We use **lagged state** (`prev_state`) to avoid look-ahead bias:
```
prev_state[t] = vol_state[t-1]
```

### 3.3 ePDF Structure

**Sliding window:** Last 60 bars per volatility state

```
ePDF_Low = deque(maxlen=60)   # Range-down values in Low-vol regime
ePDF_Med = deque(maxlen=60)   # Range-down values in Med-vol regime
ePDF_High = deque(maxlen=60)  # Range-down values in High-vol regime
```

### 3.4 Cumulative Probability Query

For each price level `[0, 1, 2]` ticks:

```
P(reach level_i | state) = P(range_dn_ticks >= level_i | state)
                           = mean(ePDF_state >= level_i)
```

**Interpretation:** In the current volatility regime, what's the probability the price drops by at least `level_i` ticks from the opening point?

**Example (High volatility):**
- P(reach 0 ticks) = 100% (price always drops to at least open)
- P(reach 1 tick) = 85%
- P(reach 2 ticks) = 60%

---

## 4. Utility Optimization

### 4.1 Utility Function

**Formulation:**

$$
U = \sum_{i=1}^{3} w_i \times P_i \times S_i - P_{\text{miss}} \times \lambda
$$

**Where:**
- `w_i` = weight allocated to level `i` (decision variable, Σ w_i = 1.0)
- `P_i` = P(reach level `i` | state) = cumulative probability from ePDF
- `S_i` = savings if filled at level `i` = `level_i` ticks
- `P_{\text{miss}}` = P(no orders fill) = `1 - max(P_1, P_2, P_3)`
- `λ` = penalty for missing all fills = 10 ticks

**Intuition:**
- **First term:** Expected savings from fills (weighted by probabilities and savings)
- **Second term:** Expected penalty for missing all fills (risk cost)

### 4.2 Penalty Term

**Why 10 ticks?**
- Each tick on NQ futures = $0.25
- 10 ticks = $2.50 penalty for missing all fills
- Provides incentive to ensure at least reasonable fill probability

**Trade-off:**
- Low λ → Optimizer favors aggressive orders (high savings, low fill)
- High λ → Optimizer favors conservative orders (low savings, high fill)

### 4.3 Grid Search Optimization

**Search space:**
- Weight step size: 0.1
- Valid combinations: All `(w1, w2, w3)` where `w1 + w2 + w3 = 1.0`, `w_i ≥ 0`
- Total combinations: ~66 possibilities

**Algorithm:**
```python
for w1 in [0.0, 0.1, ..., 1.0]:
  for w2 in [0.0, 0.1, ..., 1.0]:
    w3 = 1.0 - w1 - w2
    if w3 < 0: continue
    
    weights = [w1, w2, w3]
    utility = calculate_utility(weights, cum_probs, price_levels)
    if utility > best_utility:
      best_utility = utility
      best_weights = weights
```

### 4.4 Example Calculation

**Scenario: High-volatility state**
- Price levels: `[0, 1, 2]` ticks
- Cumulative probs: `[1.0, 0.85, 0.60]`
- Weights to test: `[0.5, 0.3, 0.2]`

**Utility:**
```
First term (expected savings):
  = 0.5 × 1.0 × 0 + 0.3 × 0.85 × 1 + 0.2 × 0.60 × 2
  = 0 + 0.255 + 0.24 = 0.495 ticks

Penalty term:
  P_miss = 1 - max(1.0, 0.85, 0.60) = 1 - 1.0 = 0
  Penalty = 0 × 10 = 0 ticks

Utility = 0.495 - 0 = 0.495 ticks
```

**Alternative weights:** `[0.1, 0.4, 0.5]`
```
First term:
  = 0.1 × 1.0 × 0 + 0.4 × 0.85 × 1 + 0.5 × 0.60 × 2
  = 0 + 0.34 + 0.60 = 0.94 ticks

Penalty:
  P_miss = 1 - 1.0 = 0
  Penalty = 0

Utility = 0.94 ticks (better!)
```

---

## 5. Backtest Implementation

### 5.1 Data Flow

```
1. Load OHLC data (104,536 1-minute bars)
2. Detect volatility states (EWMA/EWMV with lag)
3. Initialize utility optimizer (ePDF window size = 60, penalty = 10 ticks)
4. Iterate through bars:
   a. For bar t, get `prev_state[t]` (state from t-1)
   b. Update ePDF with `range_dn_ticks[t-1]`
   c. Query cumulative probabilities for levels [0, 1, 2]
   d. Optimize weights using grid search
   e. Place limit orders: `[close[t-1] - level_i × tick_size]`
   f. Simulate fills:
      - If `low[t] <= limit_price_i`, fill at `limit_price_i`
      - Else, unfilled at `close[t]`
   g. Calculate savings: `close[t-1] - exec_price`
5. Aggregate metrics: fill rate, avg savings, total savings
```

### 5.2 Fill Simulation Function

```python
def simulate_multi_fill(row: pd.Series, limit_orders: list):
    """
    Simulate fills for multiple weighted limit orders.
    
    Args:
        row: OHLC bar with 'low' and 'close'
        limit_orders: [(price, weight), (price, weight), ...]
    
    Returns:
        (weighted_exec_price, fill_rate)
    """
    weighted_price = 0.0
    total_filled_weight = 0.0
    
    for limit_price, weight in limit_orders:
        if row['low'] <= limit_price:
            weighted_price += limit_price * weight
            total_filled_weight += weight
    
    # Unfilled portion buys at close (market order)
    unfilled_weight = 1.0 - total_filled_weight
    if unfilled_weight > 0:
        weighted_price += row['close'] * unfilled_weight
    
    return weighted_price, total_filled_weight
```

### 5.3 Savings Calculation

**Definition:** Savings = Reference price - Execution price

```
savings[t] = close[t-1] - exec_price[t]
```

**Interpretation:**
- Positive savings: Bought BELOW reference (good!)
- Negative savings: Bought ABOVE reference (bad, overpaid)

**Why close[t-1] as reference?**
- Represents "fair" price if we had just placed market order
- Savings shows value of limit order strategy vs naive market order

### 5.4 Metrics

**Primary Metric:**
- **Avg Savings:** Average savings per bar (in ticks and $)

**Secondary Metrics:**
- **Total Savings:** Cumulative savings over backtest
- **Fill Rate:** Fraction of bars where at least one order filled

**Example Results (10k bars):**
```
Fill Rate: 15.53%
Avg Savings: +0.0763 ticks ($0.02)
Total Savings: +759 ticks ($189.87)
```

**Interpretation:**
- Optimizer found a strategy with low fill rate but positive savings
- On average, gained 0.08 ticks ($0.02) per minute
- When fills occurred, saved enough to offset misses

---

## 6. Key Assumptions

1. **No look-ahead bias:** Only use information available at `t-1` to make decision at `t`
2. **Instant execution:** Limit orders execute instantly if price touched
3. **Partial fills possible:** Multiple orders with different weights
4. **Penalty represents opportunity cost:** Missing all fills = 10 tick penalty
5. **Volatility regime persists:** Current state informs price movement distribution

---

## 7. Extensions

### 7.1 Alternative Reference Prices

- **Open price:** `limit_price = open[t] - level × tick_size`
- **Weighted price:** `limit_price = 0.5 × close[t-1] + 0.5 × open[t] - level × tick_size`

### 7.2 Penalty Tuning

- **Low penalty (5 ticks):** More aggressive orders
- **High penalty (15 ticks):** More conservative orders

### 7.3 Price Level Expansion

- **5 levels:** `[0, 1, 2, 3, 4]` ticks
- **Adaptive levels:** `[0, ewmv/2, ewmv, ewmv*2, ewmv*3]` ticks

### 7.4 State-Specific Optimization

- **Different weights per state:**
  - Low volatility: `[0.6, 0.3, 0.1]`
  - High volatility: `[0.2, 0.4, 0.4]`

---

## 8. Code Structure

```
├── epdf.py
│   ├── ePDFBuilder: Manage sliding window per state
│   └── get_cumulative_probabilities(): P(reach level | state)
├── strategies_utility_clean.py
│   ├── UtilityOptimizerStrategy: Main strategy class
│   ├── get_limit_prices(): Optimized weights for current bar
│   └── _optimize_weights(): Grid search for max utility
├── backtest_engine.py
│   ├── simulate_multi_fill(): Fill logic with weights
│   └── backtest(): Main backtest loop
└── test_utility_optimizer.py: Test runner + visualization
```

---

## 9. Summary

**Methodology:**
1. Build ePDF of price movements per volatility regime
2. For each bar, query fill probabilities for price levels
3. Optimize weights to maximize: `expected savings - penalty × miss_prob`
4. Simulate fills vs real price action
5. Calculate savings vs reference price

**Backtest Logic:**
- **Reference:** Previous bar's close
- **Limit prices:** `close[t-1] - level × tick_size`
- **Fill:** If `low[t] ≤ limit_price`
- **Unfilled:** Execute at `close[t]`
- **Savings:** `close[t-1] - exec_price[t]`

**Primary Metric:** Average savings per bar (ticks or $)

---

## 10. Next Steps

1. **Validate reference price choice:** Is `close[t-1]` the right reference?
2. **Adjust penalty:** Test λ = [5, 10, 15, 20] ticks
3. **Expand price levels:** Test `[0, 1, 2, 3, 4]` or adaptive levels
4. **Full dataset test:** Run on all 104,536 bars
5. **Cross-asset:** Test on Gold, GBPUSD, Euro Bunds