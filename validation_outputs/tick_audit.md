# Tick and Display-Unit Audit

Execution math uses `configured_raw_tick`; official exchange ticks are citation/economic metadata.

| Asset | Inferred Raw Tick | Configured Raw Tick | Exchange Tick | Multiplier | Legacy Tick | Status |
|---|---:|---:|---:|---:|---:|---|
| EuroStoxx | 0.5 | 0.5 | 0.5 | 1 | 1 | legacy unit fixed |
| GBP - British Pound | 0.01 | 0.01 | 0.0001 | 100 | 0.0001 | legacy unit fixed |
| German Bunds - German Government Bonds | 0.01 | 0.01 | 0.01 | 1 | 0.01 | ok |
| Gold | 0.1 | 0.1 | 0.1 | 1 | 0.1 | ok |
| HeatingOil | 0.01 | 0.01 | 0.0001 | 100 | 0.0001 | legacy unit fixed |
| JPY - Japanese Yen | 0.005 | 0.005 | 5e-07 | 10000 | 1e-06 | legacy unit fixed |
| Nasdaq | 0.25 | 0.25 | 0.25 | 1 | 0.25 | ok |

## Official Sources

| Asset | Source | Exact Place |
|---|---|---|
| JPY - Japanese Yen | [CME FX Futures](https://www.cmegroup.com/trading/why-futures/welcome-to-cme-fx-futures.html) | Trade the Currencies You Want table, Japanese Yen row: Minimum Tick Size $0.0000005 per yen increments; Dollar Value of a Tick $6.25. |
| GBP - British Pound | [CME British Pound Product Overview](https://www.cmegroup.com/education/lessons/british-pound-product-overview) | The Contract section: each contract represents 62,500 British pounds with minimum price fluctuation .0001 per British pound increments. |
| HeatingOil | [CME Heating Oil Product Overview](https://www.cmegroup.com/education/courses/introduction-to-energy/introduction-to-refined-products/heating-oil-product-overview.html) | The Contract section: minimum price fluctuation $.0001 per gallon, or $4.20 per contract. |
| EuroStoxx | [Eurex Circular 007/21](https://www.eurex.com/ex-en/find/circulars/circular-2407638) | Introduction and futures tick table: FESX outright tick changed from 1.0 to 0.5 index points effective 2021-06-21; tick value changed to EUR 5. |
