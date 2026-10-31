# Validation and Robustness Report

The May 21 `strategy_all` result table is retained as historical/provisional. The corrected raw-tick table in `corrected_raw_strategy_results.csv` is the current canonical validation output.

## Objective

Compare the project strategy against the course benchmark agent on the same timestamps, side, quantity, benchmark open, and fill policy, with no the course benchmark agent price used for strategy placement.

## Tick Unit Rule

`raw_tick` is used for ePDF distances, limit offsets, fill checks, and backtest slippage. `exchange_tick` and `tick_value` are documentation/economic fields only.

| Asset | Raw Tick | Exchange Tick | Multiplier | Source |
|---|---:|---:|---:|---|
| EuroStoxx | 0.5 | 0.5 | 1 | [official/local audit](https://www.eurex.com/ex-en/find/circulars/circular-2407638) |
| GBP - British Pound | 0.01 | 0.0001 | 100 | [official/local audit](https://www.cmegroup.com/education/lessons/british-pound-product-overview) |
| German Bunds - German Government Bonds | 0.01 | 0.01 | 1 | local raw increment audit |
| Gold | 0.1 | 0.1 | 1 | local raw increment audit |
| HeatingOil | 0.01 | 0.0001 | 100 | [official/local audit](https://www.cmegroup.com/education/courses/introduction-to-energy/introduction-to-refined-products/heating-oil-product-overview.html) |
| JPY - Japanese Yen | 0.005 | 5e-07 | 10000 | [official/local audit](https://www.cmegroup.com/trading/why-futures/welcome-to-cme-fx-futures.html) |
| Nasdaq | 0.25 | 0.25 | 1 | local raw increment audit |

## Official Citation Places

| Asset | Exact Place |
|---|---|
| JPY - Japanese Yen | [CME FX Futures](https://www.cmegroup.com/trading/why-futures/welcome-to-cme-fx-futures.html), Trade the Currencies You Want table, Japanese Yen row: Minimum Tick Size $0.0000005 per yen increments; Dollar Value of a Tick $6.25. |
| GBP - British Pound | [CME British Pound Product Overview](https://www.cmegroup.com/education/lessons/british-pound-product-overview), The Contract section: each contract represents 62,500 British pounds with minimum price fluctuation .0001 per British pound increments. |
| HeatingOil | [CME Heating Oil Product Overview](https://www.cmegroup.com/education/courses/introduction-to-energy/introduction-to-refined-products/heating-oil-product-overview.html), The Contract section: minimum price fluctuation $.0001 per gallon, or $4.20 per contract. |
| EuroStoxx | [Eurex Circular 007/21](https://www.eurex.com/ex-en/find/circulars/circular-2407638), Introduction and futures tick table: FESX outright tick changed from 1.0 to 0.5 index points effective 2021-06-21; tick value changed to EUR 5. |

## Matching Decision

| Asset | Best Selector | Front-Month Default Supported |
|---|---|---:|
| EuroStoxx | inside_high_volume | False |
| GBP - British Pound | inside_high_volume | True |
| German Bunds - German Government Bonds | inside_high_volume | False |
| Gold | min_distance | False |
| HeatingOil | min_distance | False |
| JPY - Japanese Yen | inside_high_volume | False |
| Nasdaq | inside_high_volume | False |

## ePDF Definition

For tau-bar `j`, `RangeUp = round((High_j - Open_j) / raw_tick / ell_divisor)` and `RangeDown = round((Open_j - Low_j) / raw_tick / ell_divisor)`, capped at 80.
State is `S_j = (volume_bin, volatility_bin, trend_bin)` from lagged EWMA/EWMV and trend only.
At signal time, buy orders use `P(RangeDown=d | S_j)` and sell orders use `P(RangeUp=d | S_j)` from completed prior bars; missing state history falls back to unconditional smoothed ePDF mass.

## Provisional Canonical Results

| exchange | tick | raw_tick | exchange_tick | total_pnl_vs_aiagent | pct_trades_beat_ai | beat_ai_overall | unit_issue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EuroStoxx | 1 | 0.5 | 0.5 | 1287884.826 | 82.94348069 | True | True |
| GBP - British Pound | 0.0001 | 0.01 | 0.0001 | 1727.173462 | 64.38704984 | True | True |
| German Bunds - German Government Bonds | 0.01 | 0.01 | 0.01 | 3687.421053 | 78.53294335 | True | False |
| Gold | 0.1 | 0.1 | 0.1 | 203711.7994 | 78.48409518 | True | False |
| HeatingOil | 0.0001 | 0.01 | 0.0001 | 50484.95979 | 58.36236934 | True | True |
| JPY - Japanese Yen | 1e-06 | 0.005 | 5e-07 | 16.8251231 | 56.46817248 | True | True |
| Nasdaq | 0.25 | 0.25 | 0.25 | 1895483.95 | 77.56708219 | True | False |

## Corrected Raw-Tick All-Market Results

| exchange | tick | raw_tick | exchange_tick | total_pnl_vs_aiagent | pct_trades_beat_ai | beat_ai_overall |
| --- | --- | --- | --- | --- | --- | --- |
| EuroStoxx | 0.5 | 0.5 | 0.5 | 1261336.753 | 87.38668159 | True |
| GBP - British Pound | 0.01 | 0.01 | 0.0001 | 15038.93322 | 82.75009094 | True |
| German Bunds - German Government Bonds | 0.01 | 0.01 | 0.01 | 3687.421053 | 78.53294335 | True |
| Gold | 0.1 | 0.1 | 0.1 | 203711.7994 | 78.48409518 | True |
| HeatingOil | 0.01 | 0.01 | 0.0001 | 55024.47417 | 66.23376623 | True |
| JPY - Japanese Yen | 0.005 | 0.005 | 5e-07 | 4012.50946 | 83.9677776 | True |
| Nasdaq | 0.25 | 0.25 | 0.25 | 1895483.95 | 77.56708219 | True |

## Corrected Raw-Tick Spot Checks

| Exchange | Tick | Median Ell Raw | Ell Divisor | PnL vs the course benchmark agent | % Trades Beat Agent |
|---|---:|---:|---:|---:|---:|
| JPY - Japanese Yen | 0.005 | 19 | 1 | 4012.50946 | 83.9678 |

## Statistical Risk Metrics

| Portfolio Metric | Value |
|---|---:|
| Total economic PnL vs the course benchmark agent | 1.121069e+08 |
| Daily Sharpe | 6.1293 |
| Max drawdown | -5460830.4 |
| PnL / MDD | 20.529 |

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

## Reproducibility Commands

```bash
python -B validation_framework.py all
python -B validation_framework.py run-robustness --grid defensible
python -B validation_framework.py stats --bootstrap-days 2000
python -B run_tests_simple.py
```

The full-pipeline entry point `order_execution_project.py` is joint work and is not
distributed with this repository; `run-robustness` therefore requires it and is the
only command that does. See `EXCLUSIONS.md`.
