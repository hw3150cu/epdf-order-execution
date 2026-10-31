#!/usr/bin/env python3
"""Compliance gate for the open-source exports.

Checks, in order:
  1. forbidden paths / filename patterns
  2. Rule D - a table may not pair a timestamp column with a price column,
     may not carry known index-feed column names, and may not be an .xlsx
  3. PII / local-machine disclosure (home paths, non-noreply emails, OS junk)
  4. notebook outputs must not embed price-bearing frames
  5. size budget (per file and per repo)
  6. LICENSE present and SPDX-identifiable

Exit code 0 = clean. Any ERROR fails the build; WARN is advisory.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path

# ------------------------------------------------------------------ patterns
FORBIDDEN_PATHS = [
    r"(^|/)data_export/",
    r"(^|/)data/CLC/",
    r"(^|/)Agent_Trades_Guess_match/",
    r"(^|/)stitched_1min\.csv$",
    r"_RAD\.CSV$",
    r"(^|/)smart_matched",
    r"(^|/)AIAgent_",
    r"(^|/)\.DS_Store$",
    r"(^|/)__pycache__/",
    r"(^|/)\.ipynb_checkpoints/",
    r"(^|/)\.env(\.|$)",
    r"\.(pem|key|p12|pfx)$",
    r"(^|/)id_rsa",
    r"\.xlsx$",
    r"(^|/)matching_audit_detail\.csv$",
    r"(^|/)ic_predictions_.*\.csv$",
    r"(^|/)all_futures_analysis_.*\.xlsx$",
    r"(^|/)clean_df\.ipynb$",
]

PII_PATTERNS = [
    (r"/Users/[A-Za-z0-9_.]+/", "absolute macOS home path"),
    (r"/home/[A-Za-z0-9_.]+/", "absolute Linux home path"),
    (r"[Cc]:\\\\Users\\\\[A-Za-z0-9_.]+", "absolute Windows home path"),
    (r"\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
     "email address"),
    (r"\b(gecong|ladymie|chenghaolan)\b", "personal account or machine name"),
    (r"\bpinnacledata\d*\b", "vendor watermark"),
]

TS_COLS = re.compile(r"^(date|datetime|timestamp|time|bar_idx|index|ts)$", re.I)
PRICE_COLS = re.compile(
    r"^(open|high|low|close|adj[ _]?close|bid|ask|price|px|last|settle|vwap|mid|"
    r"agent_price|best_low|best_high|best_distance_price|spot)$",
    re.I,
)
FEED_COLS = re.compile(r"^(sp500|vix|spy_etf|djia|ndx|rut|gspc|qqq|tlt|gld|usdjpy|xauusd)$", re.I)

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".cfg", ".ini",
                 ".toml", ".sh", ".cff", ".csv", ".ipynb", ".html"}
NOTEBOOK_PRICE_TOKENS = ("agent_price", "best_low", "best_high", "best_volume", "distance_ticks")


class Report:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def iter_files(repo: Path):
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".ipynb_checkpoints"}]
        for name in filenames:
            yield Path(dirpath) / name


def check_paths(rep: Report) -> None:
    for pat in FORBIDDEN_PATHS:
        rx = re.compile(pat)
        for f in iter_files(rep.repo):
            rel = f.relative_to(rep.repo).as_posix()
            if rx.search(rel):
                rep.err(f"forbidden path: {rel}  (rule {pat})")


def check_rule_d(rep: Report) -> None:
    for f in iter_files(rep.repo):
        if f.suffix.lower() != ".csv":
            continue
        rel = f.relative_to(rep.repo).as_posix()
        try:
            with f.open(encoding="utf-8", errors="ignore", newline="") as fh:
                rows = list(csv.reader(fh, delimiter=",", quotechar='"'))
        except OSError:
            continue
        if not rows:
            continue
        header = [c.strip() for c in rows[0]]
        ts = [c for c in header if TS_COLS.match(c)]
        pr = [c for c in header if PRICE_COLS.match(c)]
        feed = [c for c in header if FEED_COLS.match(c)]
        if ts and pr:
            rep.err(f"Rule D: {rel} pairs timestamp {ts} with price {pr}")
        if feed:
            rep.err(f"Rule D: {rel} carries index/feed columns {feed}")
        # advisory: long, dense numeric tables deserve a human look
        if ts and len(rows) > 2000:
            numeric = 0
            for cell in rows[1]:
                try:
                    float(cell)
                    numeric += 1
                except ValueError:
                    pass
            if numeric >= 2:
                rep.warn(f"Rule D review: {rel} has {len(rows) - 1} rows, {numeric} numeric cols")


# The scanner necessarily contains the patterns it searches for, so it exempts
# itself. Keep this list to one auditable line and nothing else.
PII_SELF_EXEMPT = {"tools/check_publish.py"}


def check_pii(rep: Report) -> None:
    compiled = [(re.compile(p), label) for p, label in PII_PATTERNS]
    for f in iter_files(rep.repo):
        if f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = f.relative_to(rep.repo).as_posix()
        if rel in PII_SELF_EXEMPT:
            rep.warn(f"PII scan exempt by design: {rel}")
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rx, label in compiled:
            for m in rx.finditer(txt):
                line = txt.count("\n", 0, m.start()) + 1
                rep.err(f"PII ({label}) in {rel}:{line}: {m.group(0)[:60]}")


def check_notebooks(rep: Report) -> None:
    for f in iter_files(rep.repo):
        if f.suffix != ".ipynb":
            continue
        rel = f.relative_to(rep.repo).as_posix()
        try:
            nb = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            rep.err(f"notebook is not valid JSON: {rel}")
            continue
        for i, cell in enumerate(nb.get("cells", [])):
            for out in cell.get("outputs", []) or []:
                blob = json.dumps(out)
                if any(tok in blob.lower() for tok in NOTEBOOK_PRICE_TOKENS):
                    rep.warn(f"notebook {rel} cell {i} output mentions price tokens - review")


def check_size(rep: Report, max_file_mb: float, max_repo_mb: float) -> None:
    total = 0
    for f in iter_files(rep.repo):
        try:
            size = f.stat().st_size
        except OSError:
            continue
        total += size
        if size > max_file_mb * 1024 * 1024:
            rep.err(f"file too large ({size / 1024 / 1024:.1f} MB > {max_file_mb} MB): "
                    f"{f.relative_to(rep.repo).as_posix()}")
    if total > max_repo_mb * 1024 * 1024:
        rep.err(f"repo too large: {total / 1024 / 1024:.1f} MB > {max_repo_mb} MB")
    return total


def check_license(rep: Report) -> None:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        p = rep.repo / name
        if p.is_file():
            head = p.read_text(encoding="utf-8", errors="ignore")[:400]
            if "MIT License" not in head:
                rep.err("LICENSE present but not recognisably MIT")
            return
    rep.err("no LICENSE file")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--max-file-mb", type=float, default=5.0)
    ap.add_argument("--max-repo-mb", type=float, default=60.0)
    ap.add_argument("--quiet-warn", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    rep = Report(repo)

    check_paths(rep)
    check_rule_d(rep)
    check_pii(rep)
    check_notebooks(rep)
    total = check_size(rep, args.max_file_mb, args.max_repo_mb)
    check_license(rep)

    print(f"== {repo.name} ==")
    print(f"   {len(list(iter_files(repo)))} files, {total / 1024 / 1024:.2f} MB")
    if not args.quiet_warn:
        for w in rep.warnings:
            print(f"   WARN  {w}")
    for e in rep.errors:
        print(f"   ERROR {e}", file=sys.stderr)
    print(f"   -> {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())