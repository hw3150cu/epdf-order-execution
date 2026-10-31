# Statistical Validation Appendix

This appendix evaluates the corrected raw-tick strategy against the course benchmark agent using daily economic PnL, risk metrics, day-block bootstrap intervals, and attribution.

## Framework

- Trade-level incremental PnL: `side * (agent_price - strategy_price) * qty`.
- Economic conversion: `(price-unit PnL / raw_tick) * tick_value`.
- Daily PnL is summed by calendar day before computing Sharpe, Sortino, drawdown, sign tests, and bootstrap intervals.
- the course benchmark agent is a comparator only; it is never used to place strategy orders.

## ePDF Definition

For tau-bar `j`, `RangeUp = round((High_j - Open_j) / raw_tick / ell_divisor)` and `RangeDown = round((Open_j - Low_j) / raw_tick / ell_divisor)`, both capped at 80.
State is `S_j = (volume_bin, volatility_bin, trend_bin)` from historical EWMA/EWMV and lagged trend only.
At signal time, buy orders use the smoothed empirical distribution `P(RangeDown=d | S_j)` and sell orders use `P(RangeUp=d | S_j)` from completed prior bars; missing state history falls back to the unconditional ePDF with Laplace smoothing.

## Portfolio Result

| Metric | Value |
|---|---:|
| Total economic PnL vs the course benchmark agent | 1.121069e+08 |
| Daily Sharpe | 6.1293 |
| Daily Sortino | 4.1925 |
| Max drawdown | -5460830.4 |
| PnL / MDD | 20.529 |
| Bootstrap total PnL 2.5% | 86436848 |
| Bootstrap total PnL 97.5% | 1.3979817e+08 |

## Asset Risk Metrics

| asset | total_pnl_econ | daily_sharpe | max_drawdown_econ | profit_factor | pnl_to_mdd |
| --- | --- | --- | --- | --- | --- |
| EuroStoxx | 12613367.53 | 14.49998228 | 0 |  |  |
| GBP - British Pound | 9399333.265 | 12.32861991 | -1222.599711 | 7688.98911 | 7687.98911 |
| German Bunds - German Government Bonds | 3687421.053 | 8.089414675 | -367211.0026 | 11.04169545 | 10.04169545 |
| Gold | 20371179.94 | 5.671662534 | -5460830.416 | 4.062624711 | 3.730417975 |
| HeatingOil | 23110279.15 | 6.442524833 | -24730.06346 | 687.7568296 | 934.5014092 |
| JPY - Japanese Yen | 5015636.824 | 14.53402651 | 0 |  |  |
| Nasdaq | 37909679 | 12.04962155 | -58248.27909 | 380.1725578 | 650.8291677 |

## Robustness Labels

| asset | robustness_label | stress_pass_rate_pct | daily_sharpe | pnl_to_mdd | total_pnl_ci_lower | matching_coverage_pct | inside_ohlc_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Nasdaq | robust win |  | 12.04962155 | 650.8291677 | 28243799.05 | 99.81515712 | 99.81515712 |
| German Bunds - German Government Bonds | robust win |  | 8.089414675 | 10.04169545 | 1993718.596 | 99.83686786 | 99.83686786 |
| EuroStoxx | robust win |  | 14.49998228 |  | 9796487.771 | 98.58490566 | 98.58490566 |
| Gold | robust win |  | 5.671662534 | 3.730417975 | 8001260.749 | 99.84326019 | 99.13793103 |
| HeatingOil | fragile win |  | 6.442524833 | 934.5014092 | 7427241.326 | 94.82758621 | 86.89655172 |
| JPY - Japanese Yen | robust win |  | 14.53402651 |  | 3762908.445 | 99.87562189 | 99.87562189 |
| GBP - British Pound | robust win |  | 12.32861991 | 7687.98911 | 6762228.584 | 100 | 100 |

## Attribution by Asset

| asset | strategy_vs_agent_econ | strategy_vs_benchmark_econ | benchmark_vs_agent_econ | mean_improvement_ticks |
| --- | --- | --- | --- | --- |
| EuroStoxx | 12613367.53 | 11277262.53 | 1336105 | 49.92220354 |
| GBP - British Pound | 9399333.265 | 9438645.765 | -39312.5 | 18.00820064 |
| German Bunds - German Government Bonds | 3687421.053 | 2888881.053 | 798540 | 6.579038965 |
| Gold | 20371179.94 | 28123949.94 | -7752770 | 33.96681304 |
| HeatingOil | 23110279.15 | 2085436.149 | 21024843 | 260.4554917 |
| JPY - Japanese Yen | 5015636.824 | 5071699.324 | -56062.5 | 16.80671111 |
| Nasdaq | 37909679 | 35999514 | 1910165 | 64.88566745 |
