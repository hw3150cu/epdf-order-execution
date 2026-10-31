# Data Policy

**This repository redistributes no market data.**

Everything committed under `results/`, `validation_outputs/` and `attribution_outputs/` is an
*aggregate*: per-asset summaries, daily P&L series, regime-level attribution, robustness scenario
outcomes, statistical metrics and IC summaries. No bar-level or tick-level price table is published,
and no vendor feed file is included.

## What you need to re-run the engine

The backtests read 1-minute futures bars from a licensed vendor feed. That data is not mine to
redistribute, so the repository ships the *code* and the *conclusions*, not the inputs.

### Expected layout

Set `ORDER_DATA_ROOT` to a directory shaped like this:

```
$ORDER_DATA_ROOT/
├── Nasdaq/
│   ├── NQH20.csv            # per-contract bars
│   ├── NQM20.csv
│   ├── NQU20.csv
│   └── <benchmark agent trades file>
├── Gold/
│   ├── GCG24.csv
│   └── ...
├── EuroStoxx/
├── GBP - British Pound/
├── German Bunds - German Government Bonds/
├── HeatingOil/
└── JPY - Japanese Yen/
```

### Bar file format

Plain CSV, no header, comma-separated:

```
2019.03.15.15:54:00,7400.00000000,7400.00000000,7400.00000000,7400.00000000,1
   timestamp         ,open        ,high        ,low         ,close       ,volume
```

This is the display-unit convention the engine expects; `config.py` records the difference between
these raw increments and official exchange ticks for every venue.

### Where the data comes from

The original project used a licensed continuous-futures feed. Any equivalent source works provided
the file format and display-unit convention above are respected. `data/README.md` in the sibling
reproduction repository documents the CLCData ordering for reference.

## What is deliberately absent, and why

| Absent | Reason |
|---|---|
| Vendor futures bars | Licence forbids redistribution |
| Reconstructed 1-minute stitched series | Derived, but is the licensed series |
| Benchmark-agent trade files | Provided by the course for comparison only |
| Per-bar matching audit tables | Contain timestamped benchmark prices |
| Trade-level P&L tables | Per-trade derivatives of licensed data |
| Excel workbook of the matching audit | Same content, bar-level |

The full path-by-path list is in [`EXCLUSIONS.md`](EXCLUSIONS.md).

## Reporting figures from this repository

You may quote the aggregate numbers and figures with attribution. Please cite the repository rather
than presenting the execution results as your own.