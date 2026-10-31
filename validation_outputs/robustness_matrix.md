# Robustness Matrix

The matrix enumerates selector, tick-source, tau, fill-policy, and remainder-policy scenarios.
Rows marked `requires_rerun` are deliberate next-step checks; no new tuning is implied.

| Asset | Label | Rationale |
|---|---|---|
| EuroStoxx | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |
| GBP - British Pound | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |
| German Bunds - German Government Bonds | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |
| Gold | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |
| HeatingOil | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |
| JPY - Japanese Yen | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |
| Nasdaq | fragile win | Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending. |

Full scenario grid is in `robustness_matrix.csv`.
