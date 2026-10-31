# Backtest Performance Optimization Roadmap

## Current Performance Issue

**Problem:** Backtest is taking ~1 minute for 200 bars, which extrapolates to:
- 1,000 bars: ~5 minutes
- 5,000 bars: ~25 minutes
- 59,000 bars: ~5 hours (UNACCEPTABLE)

**Target Performance:** < 10 minutes for 59,000 bars (~10ms per bar)

## Identified Bottlenecks

### 1. **CRITICAL: DataFrame.iloc[] Access (estimated 30-50ms per bar)**

**Location:** [backtest_optimized.py#L100-L165](backtest_optimized.py#L100-L165)

**Problem:**
```python
for i in range(warmup, len(df)):
    row = df.iloc[i]              # Slow DataFrame access
    prev = df.iloc[i-1]           # Slow DataFrame access
    gap = row['open'] - row['low']  # Dictionary lookup
    state = row['prev_state']     # Dictionary lookup
    # ... more accesses ...
```

**Why it's slow:**
- `df.iloc[i]` creates a new pandas Series object (overhead)
- Dictionary lookups on Series are slower than numpy array indexing
- This happens **3-5 times per bar**

**Optimization:** Convert to numpy arrays before loop
```python
# BEFORE loop (one-time cost):
open_arr = df['open'].values
low_arr = df['low'].values
high_arr = df['high'].values
close_arr = df['close'].values
state_arr = df['prev_state'].values

# IN loop:
gap = open_arr[i] - low_arr[i]    # Fast numpy indexing
state = state_arr[i]
```

**Expected Speedup:** 50-100x faster for DataFrame access
- Before: 30-50ms per bar
- After: 0.5-1ms per bar
- Impact: Reduces 5 hours → 5-10 minutes

### 2. **HIGH: Dictionary Creation for Trade Records (estimated 10-20ms per bar)**

**Location:** [backtest_optimized.py#L130-L165](backtest_optimized.py#L130-L165)

**Problem:**
```python
record = {
    'bar_index': i,
    'timestamp': row['ts'],
    'open': row['open'],
    'high': row['high'],
    'low': row['low'],
    'close': row['close'],
    'vol': row['vol'],
    'state': state,
    'gap': gap,
    # ... 15+ more fields ...
}
trade_records.append(record)  # Happens EVERY bar
```

**Why it's slow:**
- Creating a 20+ field dictionary is expensive
- Appending to list is O(1) but with overhead
- Not needed for every bar for analysis

**Optimization:**
1. Use numpy arrays for metrics (already done ✓)
2. Only sample trade records every 100 bars (already done ✓)
3. Or collect in list of lists, convert to DataFrame at end

**Expected Speedup:** 10-20x faster
- Before: 10-20ms per bar
- After: 0.5-1ms per bar
- Impact: Reduces 5 hours → 30-60 minutes

### 3. **MEDIUM: get_expected_close() Call (estimated 5-10ms per bar)**

**Location:** [backtest_optimized.py#L115](backtest_optimized.py#L115)

**Problem:**
```python
expected_close = optimizer.epdf.get_expected_close(state)
```

**Why it's potentially slow:**
- Calculates mean of 60 values every time
- Could maintain running mean instead

**Optimization:** Maintain running mean
```python
def update(self, state, range_dn, movement):
    # Update running mean
    old_mean = self.running_mean[state]
    count = self.counts[state]
    self.running_mean[state] = (old_mean * count + movement) / (count + 1)

def get_expected_close(self, state):
    return self.running_mean.get(state, 0.0)  # O(1) lookup
```

**Expected Speedup:** 5-10x faster
- Before: 5-10ms per bar
- After: 0.1-0.2ms per bar
- Impact: Reduces 5 hours → 60-90 minutes

### 4. **MEDIUM: Multiple get_limits() Calls (estimated 50-70ms per bar)**

**Location:** [backtest_optimized.py#L103](backtest_optimized.py#L103)

**Problem:**
```python
limits = optimizer.get_limits(df, i, tick_size)
```

**Why it's slow:**
- Calls scipy.optimize.minimize (trust-constr method)
- trust-constr calls objective function 50-100 times per bar
- Each call does fill probability lookup

**Potential Optimizations:**
1. **Cache results** for similar states (if state doesn't change, reuse)
2. **Use faster optimization method** (e.g., BFGS if constraints allow)
3. **Warm-start optimization** with previous bar's result
4. **Pre-compute lookup table** for discrete levels

**Expected Speedup:** 2-5x faster with caching
- Before: 50-70ms per bar
- After: 10-35ms per bar
- Impact: Reduces 5 hours → 2-4 hours

## Priority Implementation Order

### Phase 1: Quick Wins (1-2 hours) ⭐⭐⭐
**Expected Impact:** 5 hours → 30-60 minutes (60-80% reduction)

1. **Convert DataFrame to numpy arrays** (CRITICAL)
   - Replace all `df.iloc[i]['field']` with `field_arr[i]`
   - One-time conversion before main loop
   - **Time:** 30 minutes
   - **Speedup:** 50-100x for DataFrame access

2. **Remove redundant get_limits() calls** (if any)
   - Check if it's called multiple times per bar
   - Store result in variable, reuse
   - **Time:** 10 minutes
   - **Speedup:** 2-5x if redundant calls exist

### Phase 2: Data Structure Optimization (2-3 hours) ⭐⭐
**Expected Impact:** 30-60 minutes → 10-20 minutes (60-70% further reduction)

3. **Implement running mean for get_expected_close()**
   - Add `running_mean` dict to ePDFBuilder
   - Update incrementally instead of recalculating
   - **Time:** 1 hour
   - **Speedup:** 5-10x for this function

4. **Optimize trade_records collection**
   - Collect as list of tuples instead of dicts
   - Convert to DataFrame only at end
   - Or sample every 1000 bars instead of 100
   - **Time:** 1 hour
   - **Speedup:** 2-5x for record collection

### Phase 3: Algorithm Optimization (4-6 hours) ⭐
**Expected Impact:** 10-20 minutes → 5-10 minutes (50% further reduction)

5. **Add optimization result caching**
   - Cache based on (state, expected_close) tuple
   - Reuse if parameters are similar
   - **Time:** 2 hours
   - **Speedup:** 2-3x for repeated states

6. **Consider discrete optimization approach**
   - Instead of continuous optimization, pre-compute grid
   - Lookup best (level, weight) from pre-computed table
   - **Time:** 4 hours
   - **Speedup:** 5-10x (no optimization per bar)

## Implementation Details

### Fix #1: DataFrame → Numpy Arrays

**File:** [backtest_optimized.py](backtest_optimized.py)

**Changes in `run_backtest()` function:**

```python
def run_backtest(df, window_size, min_penalty, max_level, tick_size=0.25, warmup=1000, verbose=True):
    # ... existing code ...

    # NEW: Convert DataFrame columns to numpy arrays BEFORE loop
    open_arr = df['open'].values
    high_arr = df['high'].values
    low_arr = df['low'].values
    close_arr = df['close'].values
    vol_arr = df['vol'].values
    state_arr = df['prev_state'].values
    ts_arr = df['ts'].values

    # ... existing code ...

    for i in range(warmup, len(df)):
        # NEW: Use numpy arrays instead of DataFrame access
        gap = open_arr[i] - low_arr[i]
        state = state_arr[i]

        # Optimization (still needs df for now, can optimize later)
        limits = optimizer.get_limits(df, i, tick_size)

        bar_save = 0.0
        for level, weight in limits:
            if gap >= level:
                bar_save += weight * level

        # NEW: Use numpy arrays for calculations
        expected_close = optimizer.epdf.get_expected_close(state)
        penalty = max(optimizer.min_penalty, (expected_close - open_arr[i]) / tick_size)

        fill_prob = 0.0
        for level, weight in limits:
            if gap >= level:
                fill_prob += weight

        baseline_pnl = close_arr[i] - open_arr[i]
        optimized_pnl_expected = fill_prob * (baseline_pnl + bar_save * tick_size) - (1 - fill_prob) * penalty * tick_size

        if abs(baseline_pnl) > 0 and bar_save > 0:
            execution_score = 1.0 + (bar_save * tick_size) / abs(baseline_pnl)
        else:
            execution_score = 0.0

        # NEW: Use numpy arrays for recording
        idx = i - warmup
        savings_history[idx] = bar_save
        fill_history[idx] = 1 if bar_save > 0 else 0
        execution_score_history[idx] = execution_score

        # Trade record sampling (only every 100 bars)
        if i % 100 == 0:
            record = {
                'bar_index': i,
                'timestamp': ts_arr[i],
                'open': open_arr[i],
                'high': high_arr[i],
                'low': low_arr[i],
                'close': close_arr[i],
                'vol': vol_arr[i],
                'state': state,
                'gap': gap,
                # ... rest of fields ...
            }
            trade_records.append(record)
```

### Fix #3: Running Mean for Expected Close

**File:** [strategies_optimized_final.py](strategies_optimized_final.py)

**Changes in `ePDFBuilder` class:**

```python
class ePDFBuilder:
    def __init__(self, window_size: int = 60):
        self.window_size = window_size

        # Existing arrays
        self.range_dn_data = {
            "Low": np.zeros(window_size),
            "High": np.zeros(window_size)
        }
        self.movement_data = {
            "Low": np.zeros(window_size),
            "High": np.zeros(window_size)
        }
        self.ptrs = {"Low": 0, "High": 0}
        self.counts = {"Low": 0, "High": 0}
        self.sorted_range_dn = {
            "Low": np.array([]),
            "High": np.array([])
        }

        # NEW: Running means for O(1) lookup
        self.running_mean = {"Low": 0.0, "High": 0.0}
        self.sum_movement = {"Low": 0.0, "High": 0.0}

    def update(self, state: str, range_dn: float, movement: float):
        if state not in self.range_dn_data:
            return

        ptr = self.ptrs[state]
        old_count = self.counts[state]

        # NEW: Update running sum
        if old_count >= self.window_size:
            # Subtract old value that's being overwritten
            self.sum_movement[state] -= self.movement_data[state][ptr]

        self.sum_movement[state] += movement
        self.running_mean[state] = self.sum_movement[state] / max(1, old_count + 1)

        # Existing updates
        self.range_dn_data[state][ptr] = range_dn
        self.movement_data[state][ptr] = movement
        self.ptrs[state] = (ptr + 1) % self.window_size

        if self.counts[state] < self.window_size:
            self.counts[state] += 1

        if self.counts[state] >= 5:
            valid_data = self.range_dn_data[state][:self.counts[state]]
            self.sorted_range_dn[state] = np.sort(valid_data)

    def get_expected_close(self, state: str) -> float:
        """NEW: O(1) running mean lookup"""
        if state not in self.running_mean or self.counts[state] < 5:
            return 0.0
        return self.running_mean[state]
```

## Expected Timeline

**Current Performance:** ~5 hours for 59,000 bars

| Phase | Time to Implement | Expected Performance | Impact |
|-------|------------------|---------------------|---------|
| **Current** | - | 5 hours | - |
| **Phase 1** | 1-2 hours | 30-60 minutes | 60-80% reduction |
| **Phase 2** | 2-3 hours | 10-20 minutes | 60-70% further reduction |
| **Phase 3** | 4-6 hours | 5-10 minutes | 50% further reduction |

**Total:** 7-11 hours implementation → **5-10 minutes execution**

## Verification Plan

After each phase:
1. Run `quick_progress_test.py` with 200 bars
2. Measure actual execution time
3. Extrapolate to 59,000 bars
4. Compare with expected performance

**Success Criteria:**
- Phase 1: < 100ms per bar (200 bars in < 20 seconds)
- Phase 2: < 30ms per bar (200 bars in < 6 seconds)
- Phase 3: < 15ms per bar (200 bars in < 3 seconds)