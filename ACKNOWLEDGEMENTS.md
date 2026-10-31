# Acknowledgements

## Course context

This work began as the term project for **IEOR 4703 — Monte Carlo Simulation Methods** (Columbia
University). The exchange tick sizes, tick values and contract metadata quoted in the README come
from public exchange documentation (Eurex, CME Group) and from the raw-increment audits recorded in
`validation_outputs/tick_audit.csv`.

## Contributors

- **Hao Wang** ([@hw3150cu](https://github.com/hw3150cu)) — strategy design, ePDF construction, fill
  simulation, backtesting, validation framework, attribution and reporting. Author of the files in
  this repository.
- A co-author contributed to the shared execution-rule layer and to the joint pipeline driver. Their
  files are **not** published here — see `EXCLUSIONS.md` — and are credited here in recognition of
  that joint work.

## Methodology

The execution approach draws on the microstructure literature cited in the README, in particular
Almgren–Chriss (2000) for optimal execution and Cont–Stoikov–Talreja (2010) for order-book dynamics.
The ePDF construction and the state-conditioning scheme are original to this project.

## Third-party material

- **No market data is redistributed.** The vendor futures series were supplied under a licence that
  does not permit redistribution, and the reconstructed 1-minute series derived from them are withheld
  for the same reason. See [`DATA_POLICY.md`](DATA_POLICY.md).
- **No course material is redistributed.** The assignment specification and instructor-provided PDFs
  are excluded.
- Benchmark-agent trade files were provided by the course for comparison only; those files and the
  per-bar audit tables derived from them are excluded.

## Attribution of the benchmark

Results in the README compare against a **course-provided benchmark agent**. In the source code this
benchmark is referred to by its original identifier in column names and file paths; the prose here
calls it the "course benchmark agent". Benchmark prices are used only for post-hoc comparison and
never for order placement.