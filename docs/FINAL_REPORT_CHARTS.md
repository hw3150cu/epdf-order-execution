# Final Report: Charts & Visualizations

**IEOR 4703 Term Project 2: Volatility-Volume-based Order Management**

**Generated**: 2026-04-17

**Reconciled**: 2026-05-23

**Status**: Charts complete as methodology visuals; use `validation_outputs/corrected_raw_strategy_results.csv` for the current result table

---

## 📊 Generated Charts

### 1. ePDF Histograms (Nasdaq)

**File**: `results/epdf_histograms_nasdaq.png` (139KB)

**Contents**:
- Range Distribution (H-L)
- RangeUp Distribution (H-O) — Sell Opportunity
- RangeDn Distribution (O-L) — Buy Opportunity
- Fill Probability vs Limit Order Distance

**Key Findings**:
- Most trades cluster at 0 ticks (inside OHLC)
- Fill probability decays exponentially with distance
- Buy and sell fill probabilities are symmetric (no directional bias)

---

### 2. State-Conditioned ePDFs (Nasdaq NQH20)

**File**: `results/state_conditioned_epdf_nasdaq.png` (228KB)

**Contents**: 3×3 grid showing Range, RangeUp, RangeDn distributions for each volatility state:
- **Low State** (n=34,845, 33.3%)
- **Med State** (n=34,846, 33.3%)
- **High State** (n=34,845, 33.3%)

**Key Findings**:
- High volatility state shows wider range distributions
- Mean range increases with volatility state
- RangeUp and RangeDn remain symmetric across all states

---

### 3. State Distribution (Nasdaq)

**File**: `results/state_distribution_nasdaq.png` (47KB)

**Contents**: Bar chart showing volatility state frequencies

**Distribution**:
- Low: ~33%
- Med: ~33%
- High: ~33%

**Method**: Rolling 60-bar EWMA with tertile-based binning

---

### 4. Backtest Comparison Chart

**File**: `results/backtest_comparison_chart.png` (86KB)

**Contents**: 3-panel comparison of strategies (NQH20 data)
- Net Savings (ticks)
- Fill Rate
- PnL

**Strategies Compared**:
- Market (baseline)
- TWAP
- Aggressive
- StochasticControl

**Key Findings**:
- **SELL direction**: Aggressive wins (+213,540 ticks) but only 1.9% fill rate
- **BUY direction**: Market baseline (0 ticks)
- StochasticControl: 100% fill rate, consistent but conservative

---

### 5. All Assets Summary

**File**: `results/all_assets_summary.png` (232KB)

**Contents**: 4-panel summary across all 7 assets
- Total Trades by Asset
- Coverage Rate (%)
- Inside OHLC Rate (%)
- Buy vs Sell Distribution

**Validation Summary**:
| Metric | Value |
|--------|-------|
| Total Assets | 7 |
| Total Trades | 5,863 |
| Average Coverage | 98.9% |
| Average Inside OHLC | 96.5% |

**Per-Asset Breakdown**:
| Asset | Trades | Coverage | Inside OHLC |
|-------|--------|----------|-------------|
| Nasdaq | 2,164 | 99.8% | 99.2% |
| Gold | 1,276 | 99.8% | 96.0% |
| JPY | 804 | 99.9% | 98.5% |
| German Bunds | 613 | 99.8% | 98.9% |
| GBP | 504 | 99.6% | 97.6% |
| HeatingOil | 290 | 94.8% | 86.9% |
| EuroStoxx | 212 | 98.6% | 98.6% |

---

## 📋 PDF Requirements Checklist

| Requirement | Paper Section | Status | File |
|-------------|---------------|:------:|------|
| **ePDF Histograms** (Range, RangeUp, RangeDn) | Section 4 | ✅ | `epdf_histograms_nasdaq.png` |
| **State-Conditioned ePDFs** (3 regimes) | Section 5 | ✅ | `state_conditioned_epdf_nasdaq.png` |
| **Fill Probability Curves** | Section 4 | ✅ | `epdf_histograms_nasdaq.png` (panel 4) |
| **Backtest Comparison** | Section 6 | ✅ | `backtest_comparison_chart.png` |
| **State Distribution** | Algorithm 1 | ✅ | `state_distribution_nasdaq.png` |
| **Data Validation Summary** | Section 2.1 | ✅ | `all_assets_summary.png` |

---

## 🎯 Key Insights

### 1. Data Quality ✅
- **98.9% coverage** across 7 assets
- **96.5% inside OHLC** — agent trades match market data precisely
- Validated on 5,863 total trades

### 2. No Directional Bias ⚠️
- RangeUp ≈ RangeDn across all states
- **Implication**: Strategy should support both buy and sell directions equally

### 3. State Separation ⚠️
- Low/Med states have overlapping distributions
- **Recommendation**: Consider 2-regime approach (LowMed, High)

### 4. Strategy Performance
- **Aggressive**: High reward, low fill rate (1.9%)
- **StochasticControl**: 100% fill rate, conservative returns
- **Trade-off**: Fill rate vs. savings per trade

---

## 📁 File Locations

```
IEOR4703_Project/
├── results/
│   ├── epdf_histograms_nasdaq.png          # ePDF + Fill probability
│   ├── state_conditioned_epdf_nasdaq.png   # 3-state ePDFs
│   ├── state_distribution_nasdaq.png       # State frequencies
│   ├── backtest_comparison_chart.png       # Strategy comparison
│   ├── all_assets_summary.png              # 7-asset validation
│   ├── backtest_report_*.md                # Text report
│   └── backtest_results_*.csv              # Raw data
├── all_futures_analysis_*.xlsx             # Excel validation report
└── FINAL_REPORT_CHARTS.md                  # This file
```

---

## 🔗 Related Documents

- `README.md` — Project overview and quick start
- `PROJECT_ROADMAP.md` — Final project status and submission checklist
- `FINAL_SUMMARY.md` — Methodology and corrections
- `TEST_RESULTS_REPORT.md` — Unit test results
- `TermProject2_OrderExecution.pdf` — Original assignment

---

## ✅ Completion Status

**All required charts for PDF submission are now complete!**

| Component | Status |
|-----------|:------:|
| Data Validation | ✅ 100% |
| ePDF Construction | ✅ 100% |
| State Detection | ✅ 100% |
| Backtest Engine | ✅ 100% |
| Strategy Optimization | ✅ 100% |
| **Charts & Visualizations** | ✅ **100%** |
| Final Report Integration | ✅ **100%** |

---

**Next Steps**:
1. Use these charts with `FINAL_SUMMARY.md` for the final PDF/report.
2. Prepare presentation slides only if required.

---

*Generated: 2026-04-17 | IEOR 4703 Term Project 2*
