# Volatility-Volume Order Management

**A state-conditioned empirical-distribution (ePDF) execution engine for futures limit orders.**

Columbia University · IEOR 4703 (Monte Carlo Simulation Methods) · term project, extracted and
documented as a standalone research repository.

MIT licensed · no market data redistributed · results fully committed

---

## What this is

A systematic order-management module that splits a parent buy/sell order across limit levels using
**state-conditioned empirical probability distributions of intrabar range**, then simulates fills
against a no-look-ahead benchmark.

The engine estimates the prevailing market state from lagged volume, volatility and trend features,
builds Range / RangeUp / RangeDn ePDFs at each decision point from *completed* bars only, and places
limit slices around the benchmark open. Simulated fills are compared afterwards against a
course-provided benchmark agent's fills — benchmark prices are never used for placement.

Core loop:

1. Build 1-minute OHLCV futures histories and stitch continuous contracts.
2. Aggregate to τ-bars and compute Range, RangeUp, RangeDn in ticks.
3. Classify market state from lagged volume / volatility / trend.
4. Form the ePDF at each decision point from completed history only.
5. Slice limit orders around the benchmark open; simulate fills with no same-bar look-ahead.

**Note on scope.** This repository is the author's portion of a three-person course project. Some
jointly-authored material and all vendor data are deliberately withheld — see
[`EXCLUSIONS.md`](EXCLUSIONS.md) for the complete, path-by-path manifest and
[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) for contributions.

---

## Headline results

Canonical run: τ = 45 minutes, raw display ticks, default fill policy.
Evidence: [`validation_outputs/corrected_raw_strategy_results.csv`](validation_outputs/corrected_raw_strategy_results.csv).

| Exchange | Trades | Mean Slippage (ticks) | PnL vs Benchmark | PnL vs Benchmark Agent | Beat Agent % | Beat Agent |
|---|---:|---:|---:|---:|---:|:---:|
| EuroStoxx | 17,870 | 43.57 | 1,127,726 | 1,261,337 | 87.4% | Yes |
| GBP - British Pound | 13,745 | 17.94 | 15,102 | 15,039 | 82.8% | Yes |
| German Bunds | 12,992 | 5.28 | 2,889 | 3,687 | 78.5% | Yes |
| Gold | 19,711 | 40.95 | 281,239 | 203,712 | 78.5% | Yes |
| HeatingOil | 6,314 | 25.70 | 4,965 | 55,024 | 66.2% | Yes |
| JPY - Japanese Yen | 12,662 | 17.40 | 4,057 | 4,013 | 84.0% | Yes |
| Nasdaq | 18,932 | 62.20 | 1,799,976 | 1,895,484 | 77.6% | Yes |
| **Total** | **102,226** | | **3,235,955** | **3,438,296** | | **7/7** |

This run fixes earlier unit-assumption errors for JPY, GBP, HeatingOil and EuroStoxx by separating
**raw CSV display ticks** from **official exchange ticks**. Robustness labels are deliberately
conservative and come from the committed 126-row stress grid.

| Asset | Stress Rows | Stress Pass Rate | Label |
|---|---:|---:|---|
| EuroStoxx | 18 / 18 | 88.9% | Robust win |
| HeatingOil | 18 / 18 | 88.9% | Fragile win |
| German Bunds | 18 / 18 | 72.2% | Fragile win |
| Nasdaq | 18 / 18 | 66.7% | Fragile win |
| GBP | 18 / 18 | 66.7% | Fragile win |
| JPY | 18 / 18 | 66.7% | Fragile win |
| Gold | 18 / 18 | 16.7% | Fragile win |

Start here → [`final_submission.ipynb`](final_submission.ipynb) (pre-executed, charts and tables visible).

---

## Data validation

The benchmark agent's reported fills are matched to deterministic contract selectors before any
comparison. Artifacts: `validation_outputs/matching_audit_summary.csv`,
`matching_selector_recommendation.csv`, `tick_audit.csv`.

| Asset | Agent Trades | Coverage | Inside OHLC | Outside OHLC |
|---|---:|---:|---:|---:|
| EuroStoxx | 212 | 98.6% | 98.6% | 0.0% |
| GBP - British Pound | 504 | 99.6% | 97.6% | 2.0% |
| German Bunds | 613 | 99.8% | 98.9% | 1.0% |
| Gold | 1,276 | 99.8% | 96.0% | 3.8% |
| HeatingOil | 290 | 94.8% | 86.9% | 7.9% |
| JPY - Japanese Yen | 804 | 99.9% | 98.5% | 1.4% |
| Nasdaq | 2,164 | 99.8% | 99.2% | 0.6% |
| **Total** | **5,863** | **98.9%** | **96.8%** | **2.4%** |

Front-month selection only helps GBP under the current rule; for the other six assets it adds
ambiguity without improving inside-OHLC coverage, so it stays a robustness scenario.

---

## Repository layout

```text
config.py                      Market config: raw tick, exchange tick, tick value per venue
epdf.py                        Empirical PDF construction (Range / RangeUp / RangeDn)
fill_model.py                  Limit-order fill simulation
contract_matching.py           Contract selection and benchmark-trade matching
data_roller.py                 Continuous-contract rolling
validation_framework.py        Audits, statistical validation, report generation
backtest_optimized.py          Backtest driver
mc_bootstrap.py                Bootstrap confidence intervals
run_tests_simple.py            Lightweight test entry point

src/                           Packaged variants of the data / strategy / backtest layers
tests/                         Unit and scenario tests
docs/                          Methodology, architecture and analysis write-ups
results/                       Report charts (PNG)
validation_outputs/            Aggregate result tables (CSV) and validation reports
attribution_outputs/           Aggregate attribution and IC summaries
final_submission.ipynb         Pre-executed walkthrough of the results
```

---

## Quickstart

```bash
git clone https://github.com/hw3150cu/epdf-order-execution.git
cd epdf-order-execution
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook final_submission.ipynb
```

The notebook reads only committed aggregate artifacts, so it runs end-to-end with **no data
acquisition at all**. Re-running the backtests needs the vendor data — see below.

### Re-running the engine

Vendor futures data is **not** redistributed here (see `DATA_POLICY.md`). Point the code at your own
copy:

```bash
export ORDER_DATA_ROOT=/path/to/your/market_data
python -B validation_framework.py all
python -B validation_framework.py stats --bootstrap-days 2000
python -B validation_framework.py report
```

Expected layout under `ORDER_DATA_ROOT`: one directory per asset, each containing per-contract CSVs
in `YYYY.MM.DD.HH:MM:00,open,high,low,close,volume` form, plus the benchmark agent's trade file.
`DATA_POLICY.md` documents this in full.

### Tests

```bash
python -B run_tests_simple.py
```

---

## Market configuration

Execution math uses `raw_tick` because price columns are stored in display units; official exchange
ticks and tick values are kept for economic interpretation.

| Asset | Raw Tick | Exchange Tick | Display Multiplier | Source |
|---|---:|---:|---:|---|
| EuroStoxx | 0.5 | 0.5 | 1 | [Eurex Circular 007/21](https://www.eurex.com/ex-en/find/circulars/circular-2407638) |
| GBP - British Pound | 0.01 | 0.0001 | 100 | [CME British Pound Product Overview](https://www.cmegroup.com/education/lessons/british-pound-product-overview) |
| German Bunds | 0.01 | 0.01 | 1 | Raw increment audit |
| Gold | 0.1 | 0.1 | 1 | Raw increment audit |
| HeatingOil | 0.01 | 0.0001 | 100 | [CME Heating Oil Product Overview](https://www.cmegroup.com/education/courses/introduction-to-energy/introduction-to-refined-products/heating-oil-product-overview.html) |
| JPY - Japanese Yen | 0.005 | 0.0000005 | 10000 | [CME FX Futures](https://www.cmegroup.com/trading/why-futures/welcome-to-cme-fx-futures.html) |
| Nasdaq | 0.25 | 0.25 | 1 | Raw increment audit |

---

## Limitations

- These are **backtest results**, not production trading claims. No live execution is implied.
- The τ = 45 corrected baseline is strong, but robustness varies materially by asset — read
  `validation_outputs/robustness_asset_labels.csv` before trusting any single asset.
- Fill simulation assumes a simple no-look-ahead policy; queue position, adverse selection and
  market impact are out of scope.
- Aggregate results and charts are committed; the underlying price series are not, so an exact
  numeric reproduction requires equivalent vendor data.

---

## License and attribution

Released under the [MIT License](LICENSE). Benchmark-agent prices are used only for post-hoc
comparison, never for order placement. See [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md),
[`DATA_POLICY.md`](DATA_POLICY.md) and [`EXCLUSIONS.md`](EXCLUSIONS.md).

## References

- Almgren, R. and Chriss, N. (2000), [Optimal Execution of Portfolio Transactions](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=252925).
- Cont, R., Stoikov, S., and Talreja, R. (2010), [A Stochastic Model for Order Book Dynamics](https://arxiv.org/abs/0903.2440).
- QuantConnect, [Continuous Futures Contracts](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures).

---

## Continuous integration

The compliance workflow is committed as [`ci-templates/oss-compliance.yml`](ci-templates/oss-compliance.yml)
rather than under `.github/workflows/` because publishing it requires a GitHub token with the
`workflow` scope. To activate it, run these once:

```bash
gh auth refresh -s workflow          # grants the scope
mkdir -p .github/workflows
cp ci-templates/oss-compliance.yml .github/workflows/
git add .github/workflows && git commit -m "ci: enable compliance workflow" && git push
```

The same gate runs locally without CI:

```bash
pip install -r requirements.txt
python tools/check_publish.py --repo .        # paths, PII, granularity, size, licence
pip install pre-commit && pre-commit install  # run it on every commit
```
