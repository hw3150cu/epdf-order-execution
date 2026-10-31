# Contract Matching Audit

Selectors tested: `min_distance`, `inside_high_volume`, `calendar_front_month`, and `volume_front_month`.

| Asset | Recommended Selector | Front-Month Default Supported | Current Inside % | Front-Month Inside % | Front-Month Ambiguity % |
|---|---|---:|---:|---:|---:|
| EuroStoxx | inside_high_volume | False | 98.58 | 98.11 | 0.00 |
| GBP - British Pound | inside_high_volume | True | 100.00 | 100.00 | 5.75 |
| German Bunds - German Government Bonds | inside_high_volume | False | 99.84 | 98.69 | 0.00 |
| Gold | min_distance | False | 99.14 | 93.50 | 0.08 |
| HeatingOil | min_distance | False | 86.90 | 79.31 | 0.00 |
| JPY - Japanese Yen | inside_high_volume | False | 99.88 | 99.25 | 0.00 |
| Nasdaq | inside_high_volume | False | 99.82 | 99.35 | 15.48 |

Full selector metrics are in `matching_audit_summary.csv`.
