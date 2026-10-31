# Stochastic Control Framework for Order Execution
## Based on Xunyu Zhou's "Stochastic Controls: Hamiltonian Systems and HJB Equations"

---

## 📚 Reference Book Structure

**Book**: *Stochastic Controls: Hamiltonian Systems and HJB Equations* (465 pages)
**Author**: Xunyu Zhou (Columbia University)
**Publisher**: Springer, Applications of Mathematics Series

### Key Chapters for Order Execution

| Chapter | Title | Pages | Relevance to Order Execution |
|---------|-------|:-----:|------------------------------|
| Ch. 1 | Basic Stochastic Calculus | 25-74 | Foundation: Itô's formula, SDEs |
| Ch. 2 | Stochastic Optimal Control Problems | 75-124 | **Core: Problem formulation** |
| Ch. 3 | Maximum Principle & Hamiltonian Systems | 125-180 | **Pontryagin's maximum principle** |
| Ch. 4 | Dynamic Programming & HJB Equations | 181-240 | **⭐ MOST RELEVANT: HJB theory** |
| Ch. 5 | MP-DP Relationship | 241-304 | Verification theorems |
| Ch. 6 | Linear Quadratic (LQ) Problems | 305-368 | **Mean-variance portfolio selection** |
| Ch. 7 | Backward SDEs (BSDEs) | 369-424 | Option pricing, forward-backward systems |

---

## 🎯 Proposed Framework: Stochastic Control for Order Execution

### 1. Problem Formulation (Based on Zhou Ch. 2)

#### 1.1 State Variables

```
State Vector: X(t) = [P(t), I(t), V(t), σ(t)]ᵀ

Where:
- P(t) = Mid-price process
- I(t) = Inventory (remaining shares to execute)
- V(t) = Volume state (market liquidity)
- σ(t) = Volatility state
```

#### 1.2 State Dynamics (SDEs)

```mathematical
dP(t) = μ(P,t)dt + σ(P,t)dW(t)           # Price dynamics (geometric Brownian)
dI(t) = -u(t)dt                           # Inventory depletion
dV(t) = α_V(V - V(t))dt + σ_V dW_V(t)    # Volume (mean-reverting)
dσ(t) = α_σ(σ̄ - σ(t))dt + σ_σ dW_σ(t)    # Volatility (Ornstein-Uhlenbeck)
```

#### 1.3 Control Variable

```
u(t) = Order rate (shares per unit time)
       u(t) > 0 for selling, u(t) < 0 for buying

Constraints:
- 0 ≤ u(t) ≤ u_max (execution speed limit)
- I(T) = 0 (complete execution by terminal time)
```

#### 1.4 Market Impact Model

```
Temporary Impact: P_exec(t) = P(t) - η · u(t)
Permanent Impact: dP(t) includes -γ · u(t)dt term

Where:
- η = temporary impact coefficient
- γ = permanent impact coefficient
```

### 2. Objective Function (Mean-Variance Formulation)

Based on **Zhou Ch. 6.8: Mean-Variance Portfolio Selection** (p.359-366)

```mathematical
Minimize: J(u) = E[Cost(u)] + λ · Var[Cost(u)]

Where:
Cost(u) = ∫₀ᵀ P_exec(t) · u(t) dt - P_target · Q_total

Or equivalently (for selling):
Maximize: E[Revenue] - λ · Var[Revenue]
```

### 3. HJB Equation Framework (Based on Zhou Ch. 4)

#### 3.1 Value Function

```
V(t, P, I, V, σ) = min_u E[ ∫ₜᵀ L(s,X,u)ds + Φ(X(T)) | X(t)=x ]

Where:
- L = Running cost (market impact + risk)
- Φ = Terminal cost (penalty for incomplete execution)
```

#### 3.2 HJB Equation

```mathematical
∂V/∂t + min_u { H(t, x, u, ∂V/∂x, ∂²V/∂x²) } = 0

With Hamiltonian:
H = L(x,u) + μ(x,u)ᵀ · ∂V/∂x + ½ tr[σσᵀ · ∂²V/∂x²]

Terminal condition:
V(T, x) = Φ(x)
```

#### 3.3 Optimal Control (Feedback Form)

```
u*(t, x) = argmin_u H(t, x, u, V_x, V_xx)

This gives optimal execution rate as function of current state!
```

---

## 🔄 Integration with Your ePDF Approach

### Connection Points

| Your ePDF Approach | Zhou's Stochastic Control |
|--------------------|---------------------------|
| State detection (EWMA/EWMV) | State variables X(t) |
| P(R \| state) from histograms | Transition density from SDE |
| Discrete state bins | Discretized state space |
| Heuristic order placement | Optimal feedback control u*(t,x) |

### Proposed Hybrid Framework

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID FRAMEWORK                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. THEORETICAL LAYER (Zhou's HJB)                         │
│     ┌─────────────────────────────────────────────────┐    │
│     │ • Derive optimal policy FORM from HJB equation  │    │
│     │ • u*(t,x) = f(t, I, P; parameters θ)           │    │
│     │ • Policy structure: feedback control law        │    │
│     └─────────────────────────────────────────────────┘    │
│                           ↓                                 │
│  2. EMPIRICAL LAYER (Your ePDF)                            │
│     ┌─────────────────────────────────────────────────┐    │
│     │ • Estimate parameters θ from historical data    │    │
│     │ • Use ePDF to get P(R \| state)                 │    │
│     │ • State detection: EWMA/EWMV → discrete bins    │    │
│     └─────────────────────────────────────────────────┘    │
│                           ↓                                 │
│  3. EXECUTION LAYER (Backtest)                             │
│     ┌─────────────────────────────────────────────────┐    │
│     │ • Implement u*(t,x) with estimated parameters   │    │
│     │ • Backtest on historical data                   │    │
│     │ • Compare vs. baseline (market order)           │    │
│     └─────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📖 Key Theorems to Apply

### From Zhou's Book:

1. **Verification Theorem (Ch. 5.5)**: If V solves HJB, then V is optimal value function
2. **Stochastic Maximum Principle (Ch. 3)**: Necessary conditions for optimality
3. **LQ Problem Solution (Ch. 6)**: Closed-form solution via Riccati equation
4. **Viscosity Solutions (Ch. 4.5)**: Handle non-smooth value functions

### For Mean-Variance (Ch. 6.8):

The mean-variance problem can be solved by:
1. **Embedding technique**: Convert to parameterized problem
2. **Lagrangian relaxation**: Solve for each λ
3. **Efficient frontier**: Pareto optimal solutions

---

## 🚀 Implementation Roadmap

### Phase 1: Simplified Model (Week 1-2)

```python
# Simplified state: only inventory I(t) and time t
# Price: geometric Brownian motion with constant σ

dP = μdt + σdW
dI = -u(t)dt

# HJB reduces to:
V_t + min_u { -u·V_I + ½σ²V_PP - η·u² } = 0

# Optimal: u*(t,I) = V_I / (2η)
```

### Phase 2: Add State Variables (Week 3-4)

```python
# Add volatility state σ(t) (Ornstein-Uhlenbeck)
# State-dependent optimal execution

# HJB becomes 2-dimensional
# Solve numerically or use approximation
```

### Phase 3: Full Model with ePDF (Week 5-6)

```python
# Estimate parameters from ePDF:
# - μ, σ from price data
# - η, γ from market impact analysis
# - State transition probabilities from ePDF

# Implement feedback control:
def optimal_execution_rate(t, inventory, price, state):
    """
    u*(t, I, P, state) based on HJB solution
    with parameters estimated from ePDF
    """
    V_I = solve_hjb_derivative(t, inventory, price, state)
    return V_I / (2 * eta)
```

---

## 📚 Reading Order for Zhou's Book

| Priority | Chapter | Focus | Time |
|:--------:|---------|-------|:----:|
| 1 | Ch. 2.3-2.4 | Problem formulation examples | 2-3h |
| 2 | Ch. 4.3 | HJB equation derivation | 3-4h |
| 3 | Ch. 6.8 | Mean-variance portfolio selection | 2-3h |
| 4 | Ch. 5.5 | Verification theorems | 2h |
| 5 | Ch. 3.2-3.3 | Maximum principle | 3h |

---

## 🔗 Related Papers (Zhou's Later Work)

Based on Zhou's book, extend to:

1. **Zhou & Li (2000)**: Continuous-time mean-variance (direct application of Ch. 6.8)
2. **Zhou & Yin (2003)**: Regime-switching models (Markov chain in state)
3. **Recent work**: RL + stochastic control hybrid methods

---

## 📝 Summary

**Key Insight**: Your ePDF approach is a **data-driven discretization** of stochastic control. By combining:
- **Zhou's theory**: Provides optimal policy structure (HJB solution)
- **Your ePDF**: Provides empirical parameter estimation

You get a **principled yet practical** order execution system.

**Next Step**: Read Zhou Ch. 4.3 (HJB) and Ch. 6.8 (Mean-Variance), then implement simplified model.

---

## 🔀 Framework Comparison: Your Project vs. Zhou's Theory

### Core Differences

| Dimension | Your Project (ePDF) | Zhou's Stochastic Control |
|-----------|---------------------|---------------------------|
| **Time** | Discrete (1-min bars) | Continuous (SDEs) |
| **Method** | Data-driven (ePDF histograms) | Theory-driven (HJB equations) |
| **State** | Volatility state (EWMA/EWMV) | X(t) = [P, I, V, σ]ᵀ |
| **Control** | Limit order weights w = [w₁,w₂,w₃] | Execution rate u(t) |
| **Price Reference** | close[t-1] (previous bar close) | Mid-price P(t) |
| **Inventory** | Single bar independent optimization | Continuous inventory I(t) constraint |
| **Market Impact** | None (limit order assumption) | Temporary + permanent impact model |

### Role Comparison

```
Your Project (Price Taker):
┌─────────────────────────────────┐
│  Agent = Price Taker            │
│  • Accepts market prices        │
│  • Uses limit orders for better │
│    execution                    │
│  • No liquidity provision       │
│  • No mid-price needed          │
└─────────────────────────────────┘

Zhou's Framework (General):
┌─────────────────────────────────┐
│  Agent = Market Maker or Taker  │
│  • Theory is general            │
│  • Often assumes mid-price      │
│  • Needs adaptation for         │
│    Price Taker scenario         │
└─────────────────────────────────┘
```

### Price Reference Mechanism

```
Your Project (No mid-price):
┌──────────────────────────────────────────────────┐
│  Bar t-1              │  Bar t                  │
│  ┌─────────────────┐  │  ┌─────────────────┐    │
│  │ O: 15001        │  │  │ O: 15002        │    │
│  │ H: 15003        │  │  │ H: 15004        │    │
│  │ L: 14999        │  │  │ L: 14998 ←─────┼──┐ │
│  │ C: 15000 ←──────┼──┼──│ C: 15003        │  │ │
│  └─────────────────┘  │  └─────────────────┘  │ │
│         ↑             │                       │ │
│    Reference Price    │    Fill if low ≤ limit│ │
│    = close[t-1]       │                       │ │
│                       │    Unfilled → close[t]├─┘ │
└──────────────────────────────────────────────────┘
```

---

## 🚀 Proposed Improvements (Price Taker Framework)

### Improvement 1: Add Inventory Constraints

**Current Issue**: Each bar optimized independently, no cumulative inventory tracking

**Proposed Solution**:
```python
class InventoryAwareAgent:
    def __init__(self, target_quantity=100, max_inventory=150):
        self.target = target_quantity      # Target position
        self.inventory = 0                 # Current position
        self.max_inventory = max_inventory # Max allowed position
        
    def get_urgency_factor(self, t, T):
        """Calculate urgency based on inventory and time"""
        inventory_ratio = self.inventory / self.target
        time_pressure = 1 - (T - t) / T
        
        # High inventory + low time = high urgency
        urgency = inventory_ratio * (1 + time_pressure)
        return urgency
```

### Improvement 2: Multi-Period Optimization

**Current Issue**: Only considers current bar's expected utility

**Proposed Solution**: Consider future τ periods

```python
def multi_period_utility(weights, current_state, transition_matrix, epdfs, horizon=5):
    """
    Calculate multi-period expected utility
    
    U_multi = Σ_τ Σ_state P(state_τ|current) × U_single(weights, state)
    """
    total_utility = 0
    state_probs = {current_state: 1.0}  # Initial state certain
    
    for tau in range(horizon):
        for state, prob in state_probs.items():
            if prob > 0:
                single_U = calculate_single_utility(weights, epdfs[state])
                total_utility += prob * single_U
        
        # Propagate state probabilities
        state_probs = propagate_probs(state_probs, transition_matrix)
    
    return total_utility
```

**State Transition Matrix Estimation**:
```python
def estimate_transition_matrix(df, state_column='vol_state'):
    """
    Estimate state transition matrix from historical data
    
    Example output:
           To:   Low    Med    High
    From:
     Low        0.75   0.19   0.06
     Med        0.10   0.80   0.10
     High       0.04   0.17   0.79
    """
    states = ['Low', 'Med', 'High']
    counts = np.zeros((3, 3))
    
    for i in range(len(df) - 1):
        from_state = df[state_column].iloc[i]
        to_state = df[state_column].iloc[i + 1]
        counts[states.index(from_state), states.index(to_state)] += 1
    
    # Normalize to probabilities
    transition_matrix = counts / counts.sum(axis=1, keepdims=True)
    return transition_matrix
```

### Improvement 3: Dynamic Penalty λ(t)

**Current Issue**: λ = 10 fixed

**Proposed Solution**: λ varies with inventory and time
```python
def dynamic_penalty(base_lambda, inventory, target, t, T):
    """
    λ(t) = λ_base × f(inventory, time)
    
    - High inventory → Lower penalty (more aggressive)
    - Low time remaining → Lower penalty (must execute)
    """
    inventory_factor = 1 + 0.5 * (inventory / target - 1)
    time_factor = 1 + 0.3 * (1 - (T - t) / T)
    
    return base_lambda * inventory_factor * time_factor
```

**Example Penalty Adjustment**:

| Inventory Ratio | Time Remaining | λ Adjustment |
|:---------------:|:--------------:|:------------:|
| 50% | 80% | λ × 0.75 (conservative) |
| 80% | 50% | λ × 1.15 (normal) |
| 100% | 20% | λ × 1.65 (aggressive) |

---

## 📊 Agent State Tracking

### What Agent Should Track

```
┌─────────────────────────────────────────────────────────────┐
│   PnL (Final Goal)                                          │
│      ↑                                                      │
│      │ Evaluation                                           │
│      │                                                      │
│   Utility Function (Optimization Target)                    │
│      ↑                                                      │
│      │ Drives                                               │
│      │                                                      │
│   Inventory (Constraint)                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Current Utility = Expected PnL

```python
# Your current utility function IS expected PnL
U = Σ wᵢ × P(fill|levelᵢ) × savingsᵢ - P(miss) × λ

# Where savings = close[t-1] - exec_price
# This is single bar expected PnL!
```

### Proposed Agent Class

```python
class RealisticAgent:
    def __init__(self, target_quantity=100):
        self.target = target_quantity
        self.inventory = 0        # Cumulative inventory
        self.total_pnl = 0        # Cumulative PnL
        self.total_cost = 0       # Cumulative cost
    
    def calculate_utility(self, weights, state, t, T):
        """
        Enhanced utility function with inventory awareness
        """
        # 1. Expected savings (as before)
        expected_savings = sum(
            w * P_fill[level] * level 
            for level, w in enumerate(weights)
        )
        
        # 2. Urgency penalty (new)
        urgency = self.inventory / self.target
        time_pressure = 1 - (T - t) / T
        urgency_penalty = urgency * time_pressure * λ_urgency
        
        return expected_savings - urgency_penalty
    
    def update(self, filled_quantity, exec_price, ref_price):
        """Update inventory and PnL"""
        self.inventory += filled_quantity
        bar_pnl = (ref_price - exec_price) * filled_quantity
        self.total_pnl += bar_pnl
        return bar_pnl
```

---

## 🔄 Complete Workflow: From History to Decision

### Phase 1: Offline Estimation (Historical Data Only)

```
┌─────────────────┐      ┌─────────────────┐
│ 10 Years Data   │ ──→  │ State Transition│
│ (OHLCV)         │      │ Matrix P        │
└─────────────────┘      └─────────────────┘
        │                       │
        ↓                       ↓
┌─────────────────┐      ┌─────────────────┐
│ ePDF per state  │      │ P(High→Low)=0.04│
│ P(range|state)  │      │ P(High→Med)=0.17│
└─────────────────┘      │ P(High→High)=0.79│
                         └─────────────────┘
```

### Phase 2: Online Decision (Real-time Trading)

```
┌─────────────────────────────────────────────────────────────┐
│ Current Time t                                               │
│                                                              │
│ Inputs:                                                      │
│   • Current state: High volatility (from EWMA/EWMV)          │
│   • Current inventory: 50 shares                             │
│   • Time remaining: 30 minutes                               │
│                                                              │
│ Use Pre-computed:                                            │
│   • State transition matrix P (from Phase 1)                 │
│   • ePDF per state (from Phase 1)                            │
│                                                              │
│ Compute:                                                     │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ Multi-period Utility:                               │   │
│   │                                                      │   │
│   │ U(w) = Σ_τ Σ_state P(state_τ|current) × U(w, state) │   │
│   │        ↑                    ↑                        │   │
│   │   Future 5 bars    Transition matrix prediction     │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
│ Optimize:                                                    │
│   w* = argmax_w U(w)                                         │
│                                                              │
│ Output:                                                      │
│   w* = [0.3, 0.4, 0.3] ← Trading decision!                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Summary: Key Concepts

| Concept | Role | Your Project |
|---------|------|--------------|
| **Inventory** | Constraint | Need to add tracking |
| **Utility Function** | Optimization target | Already have = Expected PnL |
| **PnL** | Final evaluation metric | Need cumulative tracking |
| **State Transition** | Multi-period prediction | Need to estimate from history |
| **Dynamic Penalty** | Inventory-time awareness | Need to implement |

---

## ✅ Implementation Checklist

- [ ] **Improvement 1**: Add inventory tracking to agent
- [ ] **Improvement 2**: Implement state transition matrix estimation
- [ ] **Improvement 3**: Add dynamic penalty λ(t)
- [ ] **Enhancement**: Cumulative PnL tracking
- [ ] **Enhancement**: Multi-period utility optimization

---

*Framework created: Feb 26, 2026*
*Last updated: Feb 26, 2026*
*Based on: Xunyu Zhou, "Stochastic Controls: Hamiltonian Systems and HJB Equations" (Springer)*
