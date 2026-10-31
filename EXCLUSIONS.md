# Exclusions - epdf-order-execution

This repository is the author's contribution to a three-person course project. Two categories of
material are withheld: (1) anything owned by a third party - licensed vendor futures data,
course-provided competition data, and instructor-authored assignment text; and (2) anything that
would disclose bar-level market prices or another machine's filesystem layout.

A third category is joint work. Where a file was created or modified by a co-author, it is not
published here, even when the author contributed to it. The consequence is that the full-pipeline
driver `order_execution_project.py` is absent: `validation_framework.py run-robustness` needs it and
will raise a clear `ImportError`, while every other command works. All results it produced are
committed as aggregate tables.

---

**275 paths are deliberately not published.** Grouped by reason; every
path is listed so the boundary is auditable rather than implied.

| Reason | Files |
|---|---:|
| Reconstructed 1-minute vendor price series | 111 |
| Co-authored output directory that also contains reconstructed 1-minute price series | 62 |
| Licensed vendor futures bars (Pinnacle/CLC format) - may not be redistributed | 33 |
| Reconstructed 1-minute vendor price series (derived, but is the licensed series) | 22 |
| Course-provided AI-Agent competition data - owned by the course, not by the author | 10 |
| One-off diagnostic script | 8 |
| Bar-level realised returns (realized_R / realized_RU / realized_RD) | 7 |
| Created or modified by another contributor | 3 |
| macOS metadata; can encode local filenames | 2 |
| Requires a commercial Gurobi licence | 2 |
| Bar-level prices: 22 sheets incl. agent_price / best_low / best_high / best_volume | 1 |
| Bar-level prices: 23,452 rows of datetime + agent_price + selected_contract | 1 |
| Data-cleaning notebook whose outputs embed contract codes and price frames | 1 |
| Instructor-authored assignment requirements (third-party copyright) | 1 |
| Instructor-authored assignment material (third-party copyright) | 1 |
| One-off local migration script with hard-coded absolute paths | 1 |
| Internal change log against the private course repository | 1 |
| Internal working notes containing a local absolute path | 1 |
| Trade-level derivative of licensed vendor data (14 MB) | 1 |
| Trade-level derivative of licensed vendor data (35 MB) | 1 |
| Trade-level derivative of licensed vendor data | 1 |
| Duplicated render of final_submission.ipynb | 1 |
| One-off profiling script | 1 |
| Internal working notes | 1 |
| One-off scratch script | 1 |

## Reconstructed 1-minute vendor price series

111 file(s).

<details><summary>Show paths</summary>

```text
validation_outputs/corrected_raw_all/EuroStoxx/backtest_trades.csv
validation_outputs/corrected_raw_all/EuroStoxx/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/EuroStoxx/execution_rules.json
validation_outputs/corrected_raw_all/EuroStoxx/features_tau45.csv
validation_outputs/corrected_raw_all/EuroStoxx/missing_bin_summary.csv
validation_outputs/corrected_raw_all/EuroStoxx/roll_schedule.csv
validation_outputs/corrected_raw_all/EuroStoxx/run_summary.json
validation_outputs/corrected_raw_all/GBP - British Pound/backtest_trades.csv
validation_outputs/corrected_raw_all/GBP - British Pound/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/GBP - British Pound/execution_rules.json
validation_outputs/corrected_raw_all/GBP - British Pound/features_tau45.csv
validation_outputs/corrected_raw_all/GBP - British Pound/missing_bin_summary.csv
validation_outputs/corrected_raw_all/GBP - British Pound/roll_schedule.csv
validation_outputs/corrected_raw_all/GBP - British Pound/run_summary.json
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/backtest_trades.csv
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/execution_rules.json
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/features_tau45.csv
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/missing_bin_summary.csv
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/roll_schedule.csv
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/run_summary.json
validation_outputs/corrected_raw_all/Gold/backtest_trades.csv
validation_outputs/corrected_raw_all/Gold/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/Gold/execution_rules.json
validation_outputs/corrected_raw_all/Gold/features_tau45.csv
validation_outputs/corrected_raw_all/Gold/missing_bin_summary.csv
validation_outputs/corrected_raw_all/Gold/roll_schedule.csv
validation_outputs/corrected_raw_all/Gold/run_summary.json
validation_outputs/corrected_raw_all/HeatingOil/backtest_trades.csv
validation_outputs/corrected_raw_all/HeatingOil/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/HeatingOil/execution_rules.json
validation_outputs/corrected_raw_all/HeatingOil/features_tau45.csv
validation_outputs/corrected_raw_all/HeatingOil/missing_bin_summary.csv
validation_outputs/corrected_raw_all/HeatingOil/roll_schedule.csv
validation_outputs/corrected_raw_all/HeatingOil/run_summary.json
validation_outputs/corrected_raw_all/JPY - Japanese Yen/backtest_trades.csv
validation_outputs/corrected_raw_all/JPY - Japanese Yen/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/JPY - Japanese Yen/execution_rules.json
validation_outputs/corrected_raw_all/JPY - Japanese Yen/features_tau45.csv
validation_outputs/corrected_raw_all/JPY - Japanese Yen/missing_bin_summary.csv
validation_outputs/corrected_raw_all/JPY - Japanese Yen/roll_schedule.csv
validation_outputs/corrected_raw_all/JPY - Japanese Yen/run_summary.json
validation_outputs/corrected_raw_all/Nasdaq/backtest_trades.csv
validation_outputs/corrected_raw_all/Nasdaq/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_all/Nasdaq/execution_rules.json
validation_outputs/corrected_raw_all/Nasdaq/features_tau45.csv
validation_outputs/corrected_raw_all/Nasdaq/missing_bin_summary.csv
validation_outputs/corrected_raw_all/Nasdaq/roll_schedule.csv
validation_outputs/corrected_raw_all/Nasdaq/run_summary.json
validation_outputs/corrected_raw_all/all_exchanges_benchmark_vs_ai.csv
validation_outputs/corrected_raw_all/all_exchanges_summary.csv
validation_outputs/corrected_raw_all/execution_rules_all_exchanges.json
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/backtest_trades.csv
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/epdf_R_uncond_top20.csv
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/execution_rules.json
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/features_tau45.csv
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/missing_bin_summary.csv
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/roll_schedule.csv
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/run_summary.json
validation_outputs/fixed_signals/EuroStoxx/backtest_trades.csv
validation_outputs/fixed_signals/EuroStoxx/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/EuroStoxx/execution_rules.json
validation_outputs/fixed_signals/EuroStoxx/features_tau45.csv
validation_outputs/fixed_signals/EuroStoxx/missing_bin_summary.csv
validation_outputs/fixed_signals/EuroStoxx/roll_schedule.csv
validation_outputs/fixed_signals/EuroStoxx/run_summary.json
validation_outputs/fixed_signals/GBP - British Pound/backtest_trades.csv
validation_outputs/fixed_signals/GBP - British Pound/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/GBP - British Pound/execution_rules.json
validation_outputs/fixed_signals/GBP - British Pound/features_tau45.csv
validation_outputs/fixed_signals/GBP - British Pound/missing_bin_summary.csv
validation_outputs/fixed_signals/GBP - British Pound/roll_schedule.csv
validation_outputs/fixed_signals/GBP - British Pound/run_summary.json
validation_outputs/fixed_signals/German Bunds - German Government Bonds/backtest_trades.csv
validation_outputs/fixed_signals/German Bunds - German Government Bonds/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/German Bunds - German Government Bonds/execution_rules.json
validation_outputs/fixed_signals/German Bunds - German Government Bonds/features_tau45.csv
validation_outputs/fixed_signals/German Bunds - German Government Bonds/missing_bin_summary.csv
validation_outputs/fixed_signals/German Bunds - German Government Bonds/roll_schedule.csv
validation_outputs/fixed_signals/German Bunds - German Government Bonds/run_summary.json
validation_outputs/fixed_signals/Gold/backtest_trades.csv
validation_outputs/fixed_signals/Gold/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/Gold/execution_rules.json
validation_outputs/fixed_signals/Gold/features_tau45.csv
validation_outputs/fixed_signals/Gold/missing_bin_summary.csv
validation_outputs/fixed_signals/Gold/roll_schedule.csv
validation_outputs/fixed_signals/Gold/run_summary.json
validation_outputs/fixed_signals/HeatingOil/backtest_trades.csv
validation_outputs/fixed_signals/HeatingOil/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/HeatingOil/execution_rules.json
validation_outputs/fixed_signals/HeatingOil/features_tau45.csv
validation_outputs/fixed_signals/HeatingOil/missing_bin_summary.csv
validation_outputs/fixed_signals/HeatingOil/roll_schedule.csv
validation_outputs/fixed_signals/HeatingOil/run_summary.json
validation_outputs/fixed_signals/JPY - Japanese Yen/backtest_trades.csv
validation_outputs/fixed_signals/JPY - Japanese Yen/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/JPY - Japanese Yen/execution_rules.json
validation_outputs/fixed_signals/JPY - Japanese Yen/features_tau45.csv
validation_outputs/fixed_signals/JPY - Japanese Yen/missing_bin_summary.csv
validation_outputs/fixed_signals/JPY - Japanese Yen/roll_schedule.csv
validation_outputs/fixed_signals/JPY - Japanese Yen/run_summary.json
validation_outputs/fixed_signals/Nasdaq/backtest_trades.csv
validation_outputs/fixed_signals/Nasdaq/epdf_R_uncond_top20.csv
validation_outputs/fixed_signals/Nasdaq/execution_rules.json
validation_outputs/fixed_signals/Nasdaq/features_tau45.csv
validation_outputs/fixed_signals/Nasdaq/missing_bin_summary.csv
validation_outputs/fixed_signals/Nasdaq/roll_schedule.csv
validation_outputs/fixed_signals/Nasdaq/run_summary.json
validation_outputs/fixed_signals/all_exchanges_benchmark_vs_ai.csv
validation_outputs/fixed_signals/all_exchanges_summary.csv
validation_outputs/fixed_signals/execution_rules_all_exchanges.json
```

</details>

## Co-authored output directory that also contains reconstructed 1-minute price series

62 file(s).

<details><summary>Show paths</summary>

```text
strategy_all/EXECUTION_RULES.md
strategy_all/EuroStoxx/README.md
strategy_all/EuroStoxx/backtest_trades.csv
strategy_all/EuroStoxx/epdf_R_uncond_top20.csv
strategy_all/EuroStoxx/execution_rules.json
strategy_all/EuroStoxx/features_tau45.csv
strategy_all/EuroStoxx/missing_bin_summary.csv
strategy_all/EuroStoxx/roll_schedule.csv
strategy_all/EuroStoxx/run_summary.json
strategy_all/GBP - British Pound/README.md
strategy_all/GBP - British Pound/backtest_trades.csv
strategy_all/GBP - British Pound/epdf_R_uncond_top20.csv
strategy_all/GBP - British Pound/execution_rules.json
strategy_all/GBP - British Pound/features_tau45.csv
strategy_all/GBP - British Pound/missing_bin_summary.csv
strategy_all/GBP - British Pound/roll_schedule.csv
strategy_all/GBP - British Pound/run_summary.json
strategy_all/German Bunds - German Government Bonds/README.md
strategy_all/German Bunds - German Government Bonds/backtest_trades.csv
strategy_all/German Bunds - German Government Bonds/epdf_R_uncond_top20.csv
strategy_all/German Bunds - German Government Bonds/execution_rules.json
strategy_all/German Bunds - German Government Bonds/features_tau45.csv
strategy_all/German Bunds - German Government Bonds/missing_bin_summary.csv
strategy_all/German Bunds - German Government Bonds/roll_schedule.csv
strategy_all/German Bunds - German Government Bonds/run_summary.json
strategy_all/Gold/README.md
strategy_all/Gold/backtest_trades.csv
strategy_all/Gold/epdf_R_uncond_top20.csv
strategy_all/Gold/execution_rules.json
strategy_all/Gold/features_tau45.csv
strategy_all/Gold/missing_bin_summary.csv
strategy_all/Gold/roll_schedule.csv
strategy_all/Gold/run_summary.json
strategy_all/Heating_oil/README.md
strategy_all/Heating_oil/backtest_trades.csv
strategy_all/Heating_oil/epdf_R_uncond_top20.csv
strategy_all/Heating_oil/execution_rules.json
strategy_all/Heating_oil/features_tau45.csv
strategy_all/Heating_oil/missing_bin_summary.csv
strategy_all/Heating_oil/roll_schedule.csv
strategy_all/Heating_oil/run_summary.json
strategy_all/JPY - Japanese Yen/README.md
strategy_all/JPY - Japanese Yen/backtest_trades.csv
strategy_all/JPY - Japanese Yen/epdf_R_uncond_top20.csv
strategy_all/JPY - Japanese Yen/execution_rules.json
strategy_all/JPY - Japanese Yen/features_tau45.csv
strategy_all/JPY - Japanese Yen/missing_bin_summary.csv
strategy_all/JPY - Japanese Yen/roll_schedule.csv
strategy_all/JPY - Japanese Yen/run_summary.json
strategy_all/Nasdaq/README.md
strategy_all/Nasdaq/backtest_trades.csv
strategy_all/Nasdaq/epdf_R_uncond_top20.csv
strategy_all/Nasdaq/execution_rules.json
strategy_all/Nasdaq/features_tau45.csv
strategy_all/Nasdaq/missing_bin_summary.csv
strategy_all/Nasdaq/roll_schedule.csv
strategy_all/Nasdaq/run_summary.json
strategy_all/README.md
strategy_all/all_exchanges_benchmark_vs_ai.csv
strategy_all/all_exchanges_summary.csv
strategy_all/execution_rules_all_exchanges.json
strategy_all/order_execution_project.py
```

</details>

## Licensed vendor futures bars (Pinnacle/CLC format) - may not be redistributed

33 file(s).

<details><summary>Show paths</summary>

```text
data_export/.DS_Store
data_export/EuroStoxx/AIAgent_EuroStoxx.csv
data_export/EuroStoxx/VGH22.csv
data_export/EuroStoxx/VGM22.csv
data_export/GBP - British Pound/AIAgent_GBPUSD.csv
data_export/GBP - British Pound/BPM20.csv
data_export/GBP - British Pound/BPU20.csv
data_export/GBP - British Pound/BPZ20.csv
data_export/German Bunds - German Government Bonds/AIAgent_Bunds.csv
data_export/German Bunds - German Government Bonds/RXM25.csv
data_export/German Bunds - German Government Bonds/RXU25.csv
data_export/German Bunds - German Government Bonds/RXZ25.csv
data_export/Gold/AIAgent_Gold.csv
data_export/Gold/GCG24.csv
data_export/Gold/GCJ24.csv
data_export/Gold/GCM24.csv
data_export/Gold/GCQ24.csv
data_export/HeatingOil/AIAgent_HeatingOil.csv
data_export/HeatingOil/HOF22.csv
data_export/HeatingOil/HOG22.csv
data_export/HeatingOil/HOH22.csv
data_export/HeatingOil/HOJ22.csv
data_export/HeatingOil/HOK22.csv
data_export/HeatingOil/HOM22.csv
data_export/HeatingOil/HON22.csv
data_export/JPY - Japanese Yen/AIAgent_JPY.csv
data_export/JPY - Japanese Yen/JYH25.csv
data_export/JPY - Japanese Yen/JYU24.csv
data_export/JPY - Japanese Yen/JYZ24.csv
data_export/Nasdaq/AIAgent_Nasdaq.csv
data_export/Nasdaq/NQH20.csv
data_export/Nasdaq/NQM20.csv
data_export/Nasdaq/NQU20.csv
```

</details>

## Reconstructed 1-minute vendor price series (derived, but is the licensed series)

22 file(s).

<details><summary>Show paths</summary>

```text
strategy_all/EuroStoxx/stitched_1min.csv
strategy_all/GBP - British Pound/stitched_1min.csv
strategy_all/German Bunds - German Government Bonds/stitched_1min.csv
strategy_all/Gold/stitched_1min.csv
strategy_all/Heating_oil/stitched_1min.csv
strategy_all/JPY - Japanese Yen/stitched_1min.csv
strategy_all/Nasdaq/stitched_1min.csv
validation_outputs/corrected_raw_all/EuroStoxx/stitched_1min.csv
validation_outputs/corrected_raw_all/GBP - British Pound/stitched_1min.csv
validation_outputs/corrected_raw_all/German Bunds - German Government Bonds/stitched_1min.csv
validation_outputs/corrected_raw_all/Gold/stitched_1min.csv
validation_outputs/corrected_raw_all/HeatingOil/stitched_1min.csv
validation_outputs/corrected_raw_all/JPY - Japanese Yen/stitched_1min.csv
validation_outputs/corrected_raw_all/Nasdaq/stitched_1min.csv
validation_outputs/corrected_raw_jpy/JPY - Japanese Yen/stitched_1min.csv
validation_outputs/fixed_signals/EuroStoxx/stitched_1min.csv
validation_outputs/fixed_signals/GBP - British Pound/stitched_1min.csv
validation_outputs/fixed_signals/German Bunds - German Government Bonds/stitched_1min.csv
validation_outputs/fixed_signals/Gold/stitched_1min.csv
validation_outputs/fixed_signals/HeatingOil/stitched_1min.csv
validation_outputs/fixed_signals/JPY - Japanese Yen/stitched_1min.csv
validation_outputs/fixed_signals/Nasdaq/stitched_1min.csv
```

</details>

## Course-provided AI-Agent competition data - owned by the course, not by the author

10 file(s).

<details><summary>Show paths</summary>

```text
Agent_Trades_Guess_match/smart_matched_20260220_002419.csv
Agent_Trades_Guess_match/smart_matched_20260220_002911.csv
Agent_Trades_Guess_match/smart_matched_EuroStoxx_20260220_095526.csv
Agent_Trades_Guess_match/smart_matched_GBP___British_Pound_20260220_095528.csv
Agent_Trades_Guess_match/smart_matched_German_Bunds___German_Government_Bonds_20260220_095530.csv
Agent_Trades_Guess_match/smart_matched_Gold_20260220_095533.csv
Agent_Trades_Guess_match/smart_matched_HeatingOil_20260220_095536.csv
Agent_Trades_Guess_match/smart_matched_JPY___Japanese_Yen_20260220_095538.csv
Agent_Trades_Guess_match/smart_matched_Nasdaq_20260220_095541.csv
Agent_Trades_Guess_match/summary_report_20260220_095541.csv
```

</details>

## One-off diagnostic script

8 file(s).

<details><summary>Show paths</summary>

```text
check_hours.py
check_objective.py
check_range_dn.py
debug_optimization.py
debug_trust_constr.py
diagnose_matching.py
enhanced_diagnostic.py
investigate_heatingoil.py
```

</details>

## Bar-level realised returns (realized_R / realized_RU / realized_RD)

7 file(s).

<details><summary>Show paths</summary>

```text
attribution_outputs/ic_predictions_EuroStoxx.csv
attribution_outputs/ic_predictions_GBP__British_Pound.csv
attribution_outputs/ic_predictions_German_Bunds__German_Government_Bonds.csv
attribution_outputs/ic_predictions_Gold.csv
attribution_outputs/ic_predictions_Heating_oil.csv
attribution_outputs/ic_predictions_JPY__Japanese_Yen.csv
attribution_outputs/ic_predictions_Nasdaq.csv
```

</details>

## Created or modified by another contributor

3 file(s).

<details><summary>Show paths</summary>

```text
all_exchanges_benchmark_vs_ai.csv
all_exchanges_summary.csv
order_execution_project.py
```

</details>

## macOS metadata; can encode local filenames

2 file(s).

<details><summary>Show paths</summary>

```text
.DS_Store
src/.DS_Store
```

</details>

## Requires a commercial Gurobi licence

2 file(s).

<details><summary>Show paths</summary>

```text
test_gurobi.py
test_gurobi_opt.py
```

</details>

## Bar-level prices: 22 sheets incl. agent_price / best_low / best_high / best_volume

1 file(s).

<details><summary>Show paths</summary>

```text
all_futures_analysis_20260417_165056.xlsx
```

</details>

## Bar-level prices: 23,452 rows of datetime + agent_price + selected_contract

1 file(s).

<details><summary>Show paths</summary>

```text
validation_outputs/matching_audit_detail.csv
```

</details>

## Data-cleaning notebook whose outputs embed contract codes and price frames

1 file(s).

<details><summary>Show paths</summary>

```text
clean_df.ipynb
```

</details>

## Instructor-authored assignment requirements (third-party copyright)

1 file(s).

<details><summary>Show paths</summary>

```text
PROJECT_REQUIREMENTS.md
```

</details>

## Instructor-authored assignment material (third-party copyright)

1 file(s).

<details><summary>Show paths</summary>

```text
TermProject2_OrderExecution.pdf
```

</details>

## One-off local migration script with hard-coded absolute paths

1 file(s).

<details><summary>Show paths</summary>

```text
migrate_to_order_management.py
```

</details>

## Internal change log against the private course repository

1 file(s).

<details><summary>Show paths</summary>

```text
CHANGES_VS_MASTER.md
```

</details>

## Internal working notes containing a local absolute path

1 file(s).

<details><summary>Show paths</summary>

```text
MIGRATION_PLAN.md
```

</details>

## Trade-level derivative of licensed vendor data (14 MB)

1 file(s).

<details><summary>Show paths</summary>

```text
validation_outputs/fair_comparison_trades.csv
```

</details>

## Trade-level derivative of licensed vendor data (35 MB)

1 file(s).

<details><summary>Show paths</summary>

```text
validation_outputs/statistical_trade_metrics.csv
```

</details>

## Trade-level derivative of licensed vendor data

1 file(s).

<details><summary>Show paths</summary>

```text
validation_outputs/robustness_stress_runs/robustness_stress_results_partial.csv
```

</details>

## Duplicated render of final_submission.ipynb

1 file(s).

<details><summary>Show paths</summary>

```text
final_submission.html
```

</details>

## One-off profiling script

1 file(s).

<details><summary>Show paths</summary>

```text
profile_bottleneck.py
```

</details>

## Internal working notes

1 file(s).

<details><summary>Show paths</summary>

```text
POST mid term to check.md
```

</details>

## One-off scratch script

1 file(s).

<details><summary>Show paths</summary>

```text
quick_progress_test.py
```

</details>

