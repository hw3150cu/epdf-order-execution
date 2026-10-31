# Robustness Stress Results

Stress grid: tau in {15, 30, 45}, fill policy in {default, strict_next_bar}, remainder policy in {best_or_benchmark, benchmark, close}; corrected raw ticks only.

| Asset | Label | Stress Pass % | Total PnL Econ | Daily Sharpe | PnL/MDD | Rationale |
|---|---|---:|---:|---:|---:|---|
| EuroStoxx | robust win | 88.889 | 12613368 | 14.5 |  | Positive corrected PnL, positive risk metrics, positive bootstrap lower bound, and stress pass rate >= 75%. |
| GBP - British Pound | fragile win | 66.667 | 9399333.3 | 12.329 | 7688 | Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied. |
| German Bunds - German Government Bonds | fragile win | 72.222 | 3687421.1 | 8.0894 | 10.042 | Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied. |
| Gold | fragile win | 16.667 | 20371180 | 5.6717 | 3.7304 | Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied. |
| HeatingOil | fragile win | 88.889 | 23110279 | 6.4425 | 934.5 | Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied. |
| JPY - Japanese Yen | fragile win | 66.667 | 5015636.8 | 14.534 |  | Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied. |
| Nasdaq | fragile win | 66.667 | 37909679 | 12.05 | 650.83 | Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied. |

Full scenario table: `robustness_stress_results.csv`.
