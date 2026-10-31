#!/usr/bin/env python3
"""
Validation and robustness framework for the order-management project.

The strategy runner uses raw CSV display units for execution math. This module
audits that assumption, validates contract matching, and packages fair
strategy-vs-Agent comparison outputs without introducing new strategy research.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import ASSET_CONFIGS, get_tick_metadata
from contract_matching import SELECTORS, audit_asset_matching, infer_raw_tick_for_asset


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data_export"
RESULTS_ROOT = PROJECT_ROOT / "strategy_all"
OUTPUT_DIR = PROJECT_ROOT / "validation_outputs"
ANNUALIZATION_DAYS = 252
ROBUST_TAUS = (15, 30, 45)
ROBUST_FILL_POLICIES = ("default", "strict_next_bar")
ROBUST_REMAINDER_POLICIES = ("best_or_benchmark", "benchmark", "close")

TICK_SOURCE_ROWS = [
    {
        "asset": "JPY - Japanese Yen",
        "symbol": "6J",
        "official_source": "CME FX Futures",
        "url": "https://www.cmegroup.com/trading/why-futures/welcome-to-cme-fx-futures.html",
        "exact_place": (
            "Trade the Currencies You Want table, Japanese Yen row: Minimum Tick Size "
            "$0.0000005 per yen increments; Dollar Value of a Tick $6.25."
        ),
    },
    {
        "asset": "GBP - British Pound",
        "symbol": "6B",
        "official_source": "CME British Pound Product Overview",
        "url": "https://www.cmegroup.com/education/lessons/british-pound-product-overview",
        "exact_place": (
            "The Contract section: each contract represents 62,500 British pounds "
            "with minimum price fluctuation .0001 per British pound increments."
        ),
    },
    {
        "asset": "HeatingOil",
        "symbol": "HO",
        "official_source": "CME Heating Oil Product Overview",
        "url": (
            "https://www.cmegroup.com/education/courses/introduction-to-energy/"
            "introduction-to-refined-products/heating-oil-product-overview.html"
        ),
        "exact_place": (
            "The Contract section: minimum price fluctuation $.0001 per gallon, "
            "or $4.20 per contract."
        ),
    },
    {
        "asset": "EuroStoxx",
        "symbol": "FESX",
        "official_source": "Eurex Circular 007/21",
        "url": "https://www.eurex.com/ex-en/find/circulars/circular-2407638",
        "exact_place": (
            "Introduction and futures tick table: FESX outright tick changed from "
            "1.0 to 0.5 index points effective 2021-06-21; tick value changed to EUR 5."
        ),
    },
]


def asset_dirs(data_root: Path = DATA_ROOT) -> List[str]:
    return [
        path.name
        for path in sorted(data_root.iterdir())
        if path.is_dir() and any(path.glob("AIAgent*.csv"))
    ]


def asset_result_dir(results_root: Path, asset: str) -> Optional[Path]:
    candidates = [
        results_root / asset,
        results_root / asset.replace("HeatingOil", "Heating_oil"),
        results_root / asset.replace(" ", "_"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def format_float(value: object, digits: int = 10) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}g}"
    return str(value)


def df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(format_float(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def read_json(path: Path) -> Dict:
    with open(path) as handle:
        return json.load(handle)


def safe_div(numerator: float, denominator: float) -> float:
    if denominator is None or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator) / float(denominator)


def max_drawdown(cumulative: pd.Series) -> float:
    if cumulative.empty:
        return np.nan
    running_max = cumulative.cummax()
    return float((cumulative - running_max).min())


def risk_metrics_from_daily(daily_pnl: pd.Series) -> Dict[str, float]:
    pnl = pd.Series(daily_pnl).dropna().astype(float)
    if pnl.empty:
        return {
            "n_days": 0,
            "total_pnl_econ": np.nan,
            "mean_daily_pnl_econ": np.nan,
            "median_daily_pnl_econ": np.nan,
            "daily_sharpe": np.nan,
            "daily_sortino": np.nan,
            "max_drawdown_econ": np.nan,
            "profit_factor": np.nan,
            "worst_5pct_daily_pnl_econ": np.nan,
            "pnl_to_mdd": np.nan,
            "positive_day_pct": np.nan,
            "sign_test_pvalue": np.nan,
            "wilcoxon_signed_rank_pvalue": np.nan,
        }

    total = float(pnl.sum())
    mean = float(pnl.mean())
    median = float(pnl.median())
    std = float(pnl.std(ddof=1)) if len(pnl) > 1 else 0.0
    sharpe = np.inf if std == 0 and mean > 0 else (math.sqrt(ANNUALIZATION_DAYS) * mean / std if std > 0 else np.nan)
    downside = pnl[pnl < 0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = np.inf if downside_std == 0 and mean > 0 else (
        math.sqrt(ANNUALIZATION_DAYS) * mean / downside_std if downside_std > 0 else np.nan
    )
    cumulative = pnl.cumsum()
    mdd = max_drawdown(cumulative)
    mdd_abs = abs(mdd) if np.isfinite(mdd) else np.nan
    pos_sum = float(pnl[pnl > 0].sum())
    neg_sum = float(pnl[pnl < 0].sum())
    profit_factor = np.inf if neg_sum == 0 and pos_sum > 0 else safe_div(pos_sum, abs(neg_sum))
    pnl_to_mdd = np.inf if mdd_abs == 0 and total > 0 else safe_div(total, mdd_abs)
    return {
        "n_days": int(len(pnl)),
        "total_pnl_econ": total,
        "mean_daily_pnl_econ": mean,
        "median_daily_pnl_econ": median,
        "daily_sharpe": sharpe,
        "daily_sortino": sortino,
        "max_drawdown_econ": mdd,
        "profit_factor": profit_factor,
        "worst_5pct_daily_pnl_econ": float(pnl.quantile(0.05)),
        "pnl_to_mdd": pnl_to_mdd,
        "positive_day_pct": float((pnl > 0).mean() * 100.0),
        "sign_test_pvalue": sign_test_pvalue(pnl),
        "wilcoxon_signed_rank_pvalue": wilcoxon_signed_rank_pvalue(pnl),
    }


def sign_test_pvalue(values: pd.Series) -> float:
    vals = pd.Series(values).dropna()
    positives = int((vals > 0).sum())
    negatives = int((vals < 0).sum())
    n = positives + negatives
    if n == 0:
        return np.nan
    k = min(positives, negatives)
    if n <= 1000:
        tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
        return float(min(1.0, 2.0 * tail))
    mean = n / 2
    std = math.sqrt(n / 4)
    z = (k + 0.5 - mean) / std
    return float(min(1.0, 2.0 * 0.5 * math.erfc(abs(z) / math.sqrt(2))))


def wilcoxon_signed_rank_pvalue(values: pd.Series) -> float:
    vals = pd.Series(values).dropna().astype(float)
    vals = vals[vals != 0]
    n = len(vals)
    if n == 0:
        return np.nan
    ranks = vals.abs().rank(method="average")
    w_plus = float(ranks[vals > 0].sum())
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24
    if var <= 0:
        return np.nan
    z = (w_plus - mean) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2)))


def bootstrap_daily_metrics(
    daily_pnl: pd.Series,
    n_bootstrap: int = 2000,
    seed: int = 4703,
) -> Dict[str, float]:
    pnl = pd.Series(daily_pnl).dropna().astype(float).to_numpy()
    if len(pnl) == 0:
        return {}
    rng = np.random.default_rng(seed)
    totals = np.empty(n_bootstrap)
    means = np.empty(n_bootstrap)
    sharpes = np.empty(n_bootstrap)
    drawdowns = np.empty(n_bootstrap)
    n = len(pnl)
    for i in range(n_bootstrap):
        sample = pd.Series(pnl[rng.integers(0, n, size=n)])
        metrics = risk_metrics_from_daily(sample)
        totals[i] = metrics["total_pnl_econ"]
        means[i] = metrics["mean_daily_pnl_econ"]
        sharpes[i] = metrics["daily_sharpe"]
        drawdowns[i] = metrics["max_drawdown_econ"]
    return {
        "bootstrap_days": int(n),
        "bootstrap_reps": int(n_bootstrap),
        "total_pnl_ci_lower": float(np.nanpercentile(totals, 2.5)),
        "total_pnl_ci_upper": float(np.nanpercentile(totals, 97.5)),
        "mean_daily_pnl_ci_lower": float(np.nanpercentile(means, 2.5)),
        "mean_daily_pnl_ci_upper": float(np.nanpercentile(means, 97.5)),
        "daily_sharpe_ci_lower": float(np.nanpercentile(sharpes, 2.5)),
        "daily_sharpe_ci_upper": float(np.nanpercentile(sharpes, 97.5)),
        "max_drawdown_ci_lower": float(np.nanpercentile(drawdowns, 2.5)),
        "max_drawdown_ci_upper": float(np.nanpercentile(drawdowns, 97.5)),
    }


def add_economic_columns(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    if "asset" not in out.columns:
        raise ValueError("Trades must include an asset column.")
    meta = {asset: get_tick_metadata(asset) for asset in ASSET_CONFIGS}
    out["raw_tick"] = out["asset"].map(lambda x: float(meta[x]["raw_tick"]))
    out["tick_value"] = out["asset"].map(lambda x: float(meta[x]["tick_value"] or 0.0))
    out["date"] = pd.to_datetime(out["datetime"]).dt.date
    out["order_size"] = np.where(out["is_large"], "large", "small")
    out["regime"] = out["vol_rule"].fillna(out["vol_regime"].astype(str))
    out["pnl_vs_agent_price_units"] = out["pnl_vs_aiagent"]
    out["pnl_vs_agent_econ"] = out["pnl_vs_aiagent"] / out["raw_tick"] * out["tick_value"]
    out["pnl_vs_benchmark_econ"] = out["pnl_vs_benchmark"] / out["raw_tick"] * out["tick_value"]
    out["benchmark_vs_agent_price_units"] = (
        out["side"] * (out["aiagent_price"] - out["benchmark"]) * out["qty"]
    )
    out["benchmark_vs_agent_econ"] = (
        out["benchmark_vs_agent_price_units"] / out["raw_tick"] * out["tick_value"]
    )
    out["improvement_ticks_per_contract"] = (
        out["side"] * (out["aiagent_price"] - out["avg_price"]) / out["raw_tick"]
    )
    return out


def summarize_trades_for_scenario(
    trades: pd.DataFrame,
    asset: str,
    tau: int,
    fill_policy: str,
    remainder_policy: str,
) -> Dict[str, float]:
    enriched = add_economic_columns(trades.assign(asset=asset))
    daily = enriched.groupby("date")["pnl_vs_agent_econ"].sum()
    risk = risk_metrics_from_daily(daily)
    return {
        "asset": asset,
        "contract_selector": "current_volume_roll",
        "tick_source": "raw",
        "tau": tau,
        "fill_policy": fill_policy,
        "remainder_policy": remainder_policy,
        "n_trades": int(len(enriched)),
        "total_pnl_vs_aiagent": float(enriched["pnl_vs_aiagent"].sum()),
        "total_pnl_vs_aiagent_econ": float(enriched["pnl_vs_agent_econ"].sum()),
        "mean_trade_improvement_ticks": float(enriched["improvement_ticks_per_contract"].mean()),
        "pct_trades_beat_ai": float((enriched["pnl_vs_agent_econ"] > 0).mean() * 100.0),
        "stress_pass": bool(
            risk["total_pnl_econ"] > 0
            and risk["daily_sharpe"] > 0
            and (risk["pnl_to_mdd"] >= 1.0 or np.isinf(risk["pnl_to_mdd"]))
        ),
        **risk,
    }


def audit_ticks(data_root: Path = DATA_ROOT, output_dir: Path = OUTPUT_DIR) -> pd.DataFrame:
    output_dir = ensure_output_dir(output_dir)
    rows = []
    for asset in asset_dirs(data_root):
        meta = get_tick_metadata(asset)
        inferred = infer_raw_tick_for_asset(data_root / asset)
        raw_tick = float(meta["raw_tick"])
        inferred_matches_raw = bool(np.isclose(inferred, raw_tick, rtol=0, atol=max(raw_tick, 1.0) * 1e-9))
        rows.append(
            {
                "asset": asset,
                "inferred_raw_tick": inferred,
                "configured_raw_tick": raw_tick,
                "exchange_tick": meta["exchange_tick"],
                "display_multiplier": meta["display_multiplier"],
                "tick_value": meta["tick_value"],
                "legacy_tick_size": meta["legacy_tick_size"],
                "raw_matches_inferred": inferred_matches_raw,
                "legacy_matches_raw": bool(np.isclose(float(meta["legacy_tick_size"]), raw_tick)),
                "unit_issue": not inferred_matches_raw or not np.isclose(float(meta["legacy_tick_size"]), raw_tick),
                "tick_source_url": meta["tick_source_url"],
                "tick_source_note": meta["tick_source_note"],
            }
        )

    df = pd.DataFrame(rows).sort_values("asset")
    df.to_csv(output_dir / "tick_audit.csv", index=False)
    pd.DataFrame(TICK_SOURCE_ROWS).to_csv(output_dir / "official_tick_sources.csv", index=False)
    write_tick_audit_md(df, output_dir)
    return df


def write_tick_audit_md(df: pd.DataFrame, output_dir: Path) -> None:
    lines = [
        "# Tick and Display-Unit Audit",
        "",
        "Execution math uses `configured_raw_tick`; official exchange ticks are citation/economic metadata.",
        "",
        "| Asset | Inferred Raw Tick | Configured Raw Tick | Exchange Tick | Multiplier | Legacy Tick | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in df.iterrows():
        status = "ok" if row["raw_matches_inferred"] else "raw mismatch"
        if row["unit_issue"] and row["raw_matches_inferred"]:
            status = "legacy unit fixed"
        lines.append(
            "| {asset} | {inferred} | {raw} | {exchange} | {mult} | {legacy} | {status} |".format(
                asset=row["asset"],
                inferred=format_float(row["inferred_raw_tick"]),
                raw=format_float(row["configured_raw_tick"]),
                exchange=format_float(row["exchange_tick"]),
                mult=format_float(row["display_multiplier"], 6),
                legacy=format_float(row["legacy_tick_size"]),
                status=status,
            )
        )
    lines.extend(
        [
            "",
            "## Official Sources",
            "",
            "| Asset | Source | Exact Place |",
            "|---|---|---|",
        ]
    )
    for source in TICK_SOURCE_ROWS:
        lines.append(
            f"| {source['asset']} | [{source['official_source']}]({source['url']}) | {source['exact_place']} |"
        )
    (output_dir / "tick_audit.md").write_text("\n".join(lines) + "\n")


def audit_matching(
    data_root: Path = DATA_ROOT,
    output_dir: Path = OUTPUT_DIR,
    signal_mode: str = "position_change",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output_dir = ensure_output_dir(output_dir)
    summaries = []
    details = []
    for asset in asset_dirs(data_root):
        summary, detail = audit_asset_matching(
            asset,
            base_dir=data_root,
            selectors=SELECTORS,
            signal_mode=signal_mode,
        )
        summaries.append(summary)
        details.append(detail)

    summary_df = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    detail_df = pd.concat(details, ignore_index=True) if details else pd.DataFrame()
    recommendation = selector_recommendations(summary_df)

    summary_df.to_csv(output_dir / "matching_audit_summary.csv", index=False)
    detail_df.to_csv(output_dir / "matching_audit_detail.csv", index=False)
    recommendation.to_csv(output_dir / "matching_selector_recommendation.csv", index=False)
    write_matching_md(summary_df, recommendation, output_dir)
    return summary_df, detail_df, recommendation


def selector_recommendations(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if summary_df.empty:
        return pd.DataFrame(rows)
    for asset, group in summary_df.groupby("asset"):
        current = group[group["selector"] == "min_distance"]
        current_row = current.iloc[0] if len(current) else group.iloc[0]
        best = group.sort_values(
            ["inside_ohlc_pct", "coverage_pct", "ambiguous_inside_pct", "median_distance_ticks"],
            ascending=[False, False, True, True],
        ).iloc[0]
        front_group = group[group["selector"].isin(["calendar_front_month", "volume_front_month"])]
        front_best = (
            front_group.sort_values(
                ["inside_ohlc_pct", "coverage_pct", "ambiguous_inside_pct", "median_distance_ticks"],
                ascending=[False, False, True, True],
            ).iloc[0]
            if len(front_group)
            else best
        )
        improves_front = (
            front_best["inside_ohlc_pct"] >= current_row["inside_ohlc_pct"]
            and front_best["coverage_pct"] >= current_row["coverage_pct"]
            and front_best["ambiguous_inside_pct"] <= current_row["ambiguous_inside_pct"]
        )
        rows.append(
            {
                "asset": asset,
                "current_selector": current_row["selector"],
                "current_coverage_pct": current_row["coverage_pct"],
                "current_inside_ohlc_pct": current_row["inside_ohlc_pct"],
                "best_selector": best["selector"],
                "best_coverage_pct": best["coverage_pct"],
                "best_inside_ohlc_pct": best["inside_ohlc_pct"],
                "best_ambiguous_inside_pct": best["ambiguous_inside_pct"],
                "front_month_best_selector": front_best["selector"],
                "front_month_inside_ohlc_pct": front_best["inside_ohlc_pct"],
                "front_month_coverage_pct": front_best["coverage_pct"],
                "front_month_ambiguous_inside_pct": front_best["ambiguous_inside_pct"],
                "front_month_default_supported": bool(improves_front),
            }
        )
    return pd.DataFrame(rows)


def write_matching_md(summary_df: pd.DataFrame, recommendation: pd.DataFrame, output_dir: Path) -> None:
    lines = [
        "# Contract Matching Audit",
        "",
        "Selectors tested: `min_distance`, `inside_high_volume`, `calendar_front_month`, and `volume_front_month`.",
        "",
        "| Asset | Recommended Selector | Front-Month Default Supported | Current Inside % | Front-Month Inside % | Front-Month Ambiguity % |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for _, row in recommendation.iterrows():
        lines.append(
            "| {asset} | {selector} | {supported} | {current:.2f} | {front:.2f} | {ambig:.2f} |".format(
                asset=row["asset"],
                selector=row["best_selector"],
                supported=str(row["front_month_default_supported"]),
                current=float(row["current_inside_ohlc_pct"]),
                front=float(row["front_month_inside_ohlc_pct"]),
                ambig=float(row["front_month_ambiguous_inside_pct"]),
            )
        )
    lines.extend(["", "Full selector metrics are in `matching_audit_summary.csv`."])
    (output_dir / "matching_audit.md").write_text("\n".join(lines) + "\n")


def canonical_results(
    results_root: Path = RESULTS_ROOT,
    output_dir: Path = OUTPUT_DIR,
    tick_audit: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    output_dir = ensure_output_dir(output_dir)
    source = results_root / "all_exchanges_benchmark_vs_ai.csv"
    if not source.exists():
        return pd.DataFrame()
    df = pd.read_csv(source)
    meta_rows = []
    for asset in df["exchange"]:
        meta = get_tick_metadata(asset)
        meta_rows.append({"exchange": asset, **meta})
    meta_df = pd.DataFrame(meta_rows)
    out = df.merge(meta_df, on="exchange", how="left", suffixes=("", "_config"))
    out["result_status"] = "provisional_pending_tick_and_matching_audit"
    if tick_audit is not None and not tick_audit.empty:
        issues = tick_audit.set_index("asset")["unit_issue"].to_dict()
        out["unit_issue"] = out["exchange"].map(issues).fillna(False)
    out.to_csv(output_dir / "canonical_strategy_results_provisional.csv", index=False)
    return out


def load_strategy_trades(results_root: Path = RESULTS_ROOT) -> pd.DataFrame:
    frames = []
    for asset in ASSET_CONFIGS:
        result_dir = asset_result_dir(results_root, asset)
        if result_dir is None:
            continue
        trades_path = result_dir / "backtest_trades.csv"
        if not trades_path.exists():
            continue
        trades = pd.read_csv(trades_path)
        if trades.empty:
            continue
        trades["asset"] = asset
        trades["datetime"] = pd.to_datetime(trades["datetime"])
        trades["bar_time"] = pd.to_datetime(trades["bar_time"])
        stitched_path = result_dir / "stitched_1min.csv"
        if stitched_path.exists() and "_contract" not in trades:
            stitched = pd.read_csv(stitched_path, usecols=["datetime", "_contract"])
            stitched["bar_time"] = pd.to_datetime(stitched["datetime"])
            stitched = stitched.drop(columns=["datetime"]).drop_duplicates("bar_time")
            trades = trades.merge(stitched, on="bar_time", how="left")
            trades = trades.rename(columns={"_contract": "contract"})
        frames.append(trades)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fair_compare(results_root: Path = RESULTS_ROOT, output_dir: Path = OUTPUT_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir = ensure_output_dir(output_dir)
    trades = load_strategy_trades(results_root)
    if trades.empty:
        empty = pd.DataFrame()
        empty.to_csv(output_dir / "fair_comparison_trades.csv", index=False)
        empty.to_csv(output_dir / "fair_comparison_summary.csv", index=False)
        return empty, empty

    standard = pd.DataFrame(
        {
            "datetime": trades["datetime"],
            "asset": trades["asset"],
            "contract": trades.get("contract"),
            "side": trades["side"],
            "qty": trades["qty"],
            "order_size": np.where(trades["is_large"], "large", "small"),
            "regime": trades["vol_rule"].fillna(trades["vol_regime"].astype(str)),
            "benchmark": trades["benchmark"],
            "agent_price": trades["aiagent_price"],
            "strategy_price": trades["avg_price"],
            "fill_rate": trades["fill_rate"],
            "pnl_vs_benchmark": trades["pnl_vs_benchmark"],
            "pnl_vs_agent": trades["pnl_vs_aiagent"],
            "beat_agent": trades["pnl_vs_aiagent"] > 0,
        }
    )
    standard.to_csv(output_dir / "fair_comparison_trades.csv", index=False)

    groups = ["asset", "side", "order_size", "regime"]
    summary = (
        standard.groupby(groups, dropna=False)
        .agg(
            n_trades=("datetime", "count"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_pnl_vs_benchmark=("pnl_vs_benchmark", "mean"),
            total_pnl_vs_benchmark=("pnl_vs_benchmark", "sum"),
            mean_pnl_vs_agent=("pnl_vs_agent", "mean"),
            total_pnl_vs_agent=("pnl_vs_agent", "sum"),
            pct_trades_beat_agent=("beat_agent", lambda x: 100.0 * x.mean()),
        )
        .reset_index()
    )
    summary.to_csv(output_dir / "fair_comparison_summary.csv", index=False)
    return standard, summary


def run_robustness_grid(
    data_root: Path = DATA_ROOT,
    output_dir: Path = OUTPUT_DIR,
    grid: str = "defensible",
) -> pd.DataFrame:
    if grid != "defensible":
        raise ValueError("Only the defensible robustness grid is currently defined.")

    try:
        from order_execution_project import (
            EPDF_WARMUP,
            EXCHANGE_TUNING,
            backtest_vs_aiagent_walkforward,
            build_features,
            compute_exchange_calibration,
            load_aiagent,
            make_tau_bars,
            merge_exchange_by_volume,
            signals_from_aiagent,
        )
    except ImportError as exc:  # pragma: no cover - optional entry point
        raise ImportError(
            "run_robustness_grid() requires order_execution_project.py, which is not "
            "distributed with this repository: it is joint work and is deliberately "
            "excluded (see EXCLUSIONS.md). The results it produced are committed under "
            "validation_outputs/robustness_stress_results.csv. The remaining framework "
            "commands (all, stats, run-backtest) work without it."
        ) from exc

    output_dir = ensure_output_dir(output_dir)
    stress_dir = output_dir / "robustness_stress_runs"
    stress_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    assets = asset_dirs(data_root)
    scenarios = list(itertools.product(ROBUST_TAUS, ROBUST_FILL_POLICIES, ROBUST_REMAINDER_POLICIES))

    for asset in assets:
        print(f"Robustness asset: {asset}")
        tick = float(get_tick_metadata(asset)["raw_tick"])
        df_1min, _ = merge_exchange_by_volume(data_root / asset)
        ai = load_aiagent(data_root / asset)
        all_signals = signals_from_aiagent(ai)
        for tau in ROBUST_TAUS:
            bars = make_tau_bars(df_1min, tau)
            if len(bars) <= EPDF_WARMUP + 1:
                continue
            exchange_cal = compute_exchange_calibration(bars, tick)
            exchange_cal["exchange_name"] = asset
            exchange_cal["tick_mode"] = "raw"
            feat = build_features(bars, tick, ell_divisor=exchange_cal["ell_divisor"])
            signals = all_signals[
                (all_signals.index >= feat.index[EPDF_WARMUP])
                & (all_signals.index <= feat.index[-1])
            ]
            for scenario_tau, fill_policy, remainder_policy in scenarios:
                if scenario_tau != tau:
                    continue
                print(f"  tau={tau} fill={fill_policy} remainder={remainder_policy}")
                bt = backtest_vs_aiagent_walkforward(
                    bars,
                    feat,
                    signals,
                    tick,
                    tau,
                    df_1min=df_1min,
                    exchange_cal=exchange_cal,
                    exchange_tuning=EXCHANGE_TUNING.get(asset, {}),
                    fill_policy=fill_policy,
                    remainder_policy=remainder_policy,
                )
                rows.append(
                    summarize_trades_for_scenario(
                        bt,
                        asset=asset,
                        tau=tau,
                        fill_policy=fill_policy,
                        remainder_policy=remainder_policy,
                    )
                )
                pd.DataFrame(rows).to_csv(stress_dir / "robustness_stress_results_partial.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "robustness_stress_results.csv", index=False)
    labels = classify_robustness(output_dir, stress_results=df)
    labels.to_csv(output_dir / "robustness_asset_labels.csv", index=False)
    write_robustness_stress_md(df, labels, output_dir)
    return df


def classify_robustness(
    output_dir: Path = OUTPUT_DIR,
    stress_results: Optional[pd.DataFrame] = None,
    metrics: Optional[pd.DataFrame] = None,
    bootstrap: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    output_dir = ensure_output_dir(output_dir)
    if stress_results is None:
        path = output_dir / "robustness_stress_results.csv"
        stress_results = pd.read_csv(path) if path.exists() else pd.DataFrame()
    if metrics is None:
        path = output_dir / "statistical_metrics_by_asset.csv"
        metrics = pd.read_csv(path) if path.exists() else pd.DataFrame()
    if bootstrap is None:
        path = output_dir / "bootstrap_confidence_intervals.csv"
        bootstrap = pd.read_csv(path) if path.exists() else pd.DataFrame()

    match_path = output_dir / "matching_selector_recommendation.csv"
    matching = pd.read_csv(match_path) if match_path.exists() else pd.DataFrame()
    tick_path = output_dir / "tick_audit.csv"
    tick_audit = pd.read_csv(tick_path) if tick_path.exists() else pd.DataFrame()

    rows = []
    for asset in ASSET_CONFIGS:
        stress = stress_results[stress_results["asset"] == asset] if not stress_results.empty else pd.DataFrame()
        metric = metrics[metrics["asset"] == asset] if not metrics.empty and "asset" in metrics else pd.DataFrame()
        boot = bootstrap[bootstrap["scope"] == asset] if not bootstrap.empty and "scope" in bootstrap else pd.DataFrame()
        match = matching[matching["asset"] == asset] if not matching.empty else pd.DataFrame()
        tick = tick_audit[tick_audit["asset"] == asset] if not tick_audit.empty else pd.DataFrame()

        stress_pass_rate = float(stress["stress_pass"].mean() * 100.0) if len(stress) else np.nan
        total_pnl = (
            float(metric["total_pnl_econ"].iloc[0])
            if len(metric)
            else (float(stress.loc[stress["tau"].eq(45), "total_pnl_vs_aiagent_econ"].iloc[0]) if len(stress) else np.nan)
        )
        sharpe = float(metric["daily_sharpe"].iloc[0]) if len(metric) else np.nan
        pnl_to_mdd = float(metric["pnl_to_mdd"].iloc[0]) if len(metric) else np.nan
        ci_lower = float(boot["total_pnl_ci_lower"].iloc[0]) if len(boot) else np.nan
        coverage = float(match["current_coverage_pct"].iloc[0]) if len(match) else np.nan
        inside = float(match["current_inside_ohlc_pct"].iloc[0]) if len(match) else np.nan
        raw_ok = bool(tick["raw_matches_inferred"].iloc[0]) if len(tick) else True

        matching_ok = (
            (np.isnan(coverage) or coverage >= 95.0)
            and (np.isnan(inside) or inside >= 90.0)
        )
        stats_ok = (
            np.isfinite(total_pnl)
            and total_pnl > 0
            and (np.isnan(sharpe) or sharpe > 0)
            and (np.isnan(pnl_to_mdd) or pnl_to_mdd >= 1.0 or np.isinf(pnl_to_mdd))
            and (np.isnan(ci_lower) or ci_lower > 0)
        )
        stress_ok = (not np.isnan(stress_pass_rate)) and stress_pass_rate >= 75.0

        if not raw_ok or (not np.isnan(coverage) and coverage < 90.0):
            label = "data issue"
        elif not np.isfinite(total_pnl) or total_pnl <= 0:
            label = "loss"
        elif stats_ok and stress_ok and matching_ok:
            label = "robust win"
        else:
            label = "fragile win"

        if label == "robust win":
            rationale = "Positive corrected PnL, positive risk metrics, positive bootstrap lower bound, and stress pass rate >= 75%."
        elif label == "fragile win":
            rationale = "Corrected baseline wins, but one or more robustness, drawdown, bootstrap, or matching thresholds is not fully satisfied."
        elif label == "data issue":
            rationale = "Raw tick or matching coverage needs explicit qualification before claiming robustness."
        else:
            rationale = "Corrected baseline does not beat AIAgent."

        rows.append(
            {
                "asset": asset,
                "robustness_label": label,
                "stress_pass_rate_pct": stress_pass_rate,
                "total_pnl_econ": total_pnl,
                "daily_sharpe": sharpe,
                "pnl_to_mdd": pnl_to_mdd,
                "total_pnl_ci_lower": ci_lower,
                "matching_coverage_pct": coverage,
                "inside_ohlc_pct": inside,
                "rationale": rationale,
            }
        )
    return pd.DataFrame(rows)


def write_robustness_stress_md(
    stress_results: pd.DataFrame,
    labels: pd.DataFrame,
    output_dir: Path,
) -> None:
    lines = [
        "# Robustness Stress Results",
        "",
        "Stress grid: tau in {15, 30, 45}, fill policy in {default, strict_next_bar}, remainder policy in {best_or_benchmark, benchmark, close}; corrected raw ticks only.",
        "",
        "| Asset | Label | Stress Pass % | Total PnL Econ | Daily Sharpe | PnL/MDD | Rationale |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for _, row in labels.sort_values("asset").iterrows():
        lines.append(
            "| {asset} | {label} | {pass_rate} | {pnl} | {sharpe} | {pnl_mdd} | {rationale} |".format(
                asset=row["asset"],
                label=row["robustness_label"],
                pass_rate=format_float(row["stress_pass_rate_pct"], 5),
                pnl=format_float(row["total_pnl_econ"], 8),
                sharpe=format_float(row["daily_sharpe"], 5),
                pnl_mdd=format_float(row["pnl_to_mdd"], 5),
                rationale=row["rationale"],
            )
        )
    lines.extend(["", "Full scenario table: `robustness_stress_results.csv`."])
    (output_dir / "ROBUSTNESS_STRESS_REPORT.md").write_text("\n".join(lines) + "\n")


def build_statistical_report(
    output_dir: Path = OUTPUT_DIR,
    n_bootstrap: int = 2000,
    seed: int = 4703,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output_dir = ensure_output_dir(output_dir)
    corrected_root = output_dir / "corrected_raw_all"
    trades = load_strategy_trades(corrected_root)
    if trades.empty:
        raise FileNotFoundError(f"No corrected raw trade logs found under {corrected_root}")

    enriched = add_economic_columns(trades)
    enriched.to_csv(output_dir / "statistical_trade_metrics.csv", index=False)

    daily_asset = (
        enriched.groupby(["asset", "date"], dropna=False)
        .agg(
            pnl_vs_agent_econ=("pnl_vs_agent_econ", "sum"),
            pnl_vs_benchmark_econ=("pnl_vs_benchmark_econ", "sum"),
            benchmark_vs_agent_econ=("benchmark_vs_agent_econ", "sum"),
            n_trades=("datetime", "count"),
        )
        .reset_index()
    )
    daily_asset.to_csv(output_dir / "daily_pnl_by_asset.csv", index=False)

    metric_rows = []
    bootstrap_rows = []
    for asset, group in daily_asset.groupby("asset"):
        metrics = risk_metrics_from_daily(group["pnl_vs_agent_econ"])
        metric_rows.append({"asset": asset, **metrics})
        bootstrap_rows.append(
            {
                "scope": asset,
                **bootstrap_daily_metrics(group["pnl_vs_agent_econ"], n_bootstrap=n_bootstrap, seed=seed),
            }
        )

    portfolio_daily = (
        daily_asset.groupby("date", dropna=False)
        .agg(
            pnl_vs_agent_econ=("pnl_vs_agent_econ", "sum"),
            pnl_vs_benchmark_econ=("pnl_vs_benchmark_econ", "sum"),
            benchmark_vs_agent_econ=("benchmark_vs_agent_econ", "sum"),
            n_trades=("n_trades", "sum"),
        )
        .reset_index()
    )
    portfolio_daily.to_csv(output_dir / "daily_pnl_portfolio.csv", index=False)
    portfolio_metrics = pd.DataFrame(
        [{"scope": "portfolio", **risk_metrics_from_daily(portfolio_daily["pnl_vs_agent_econ"])}]
    )
    bootstrap_rows.append(
        {
            "scope": "portfolio",
            **bootstrap_daily_metrics(portfolio_daily["pnl_vs_agent_econ"], n_bootstrap=n_bootstrap, seed=seed),
        }
    )

    metrics = pd.DataFrame(metric_rows).sort_values("asset")
    stress_path = output_dir / "robustness_stress_results.csv"
    if stress_path.exists():
        stress = pd.read_csv(stress_path)
        pass_rates = (
            stress.groupby("asset")["stress_pass"]
            .mean()
            .mul(100.0)
            .rename("stress_pass_rate_pct")
            .reset_index()
        )
        metrics = metrics.merge(pass_rates, on="asset", how="left")
    metrics.to_csv(output_dir / "statistical_metrics_by_asset.csv", index=False)
    portfolio_metrics.to_csv(output_dir / "statistical_metrics_portfolio.csv", index=False)

    bootstrap = pd.DataFrame(bootstrap_rows)
    bootstrap.to_csv(output_dir / "bootstrap_confidence_intervals.csv", index=False)

    attribution = build_attribution_tables(enriched, output_dir)
    labels = classify_robustness(output_dir, metrics=metrics, bootstrap=bootstrap)
    labels.to_csv(output_dir / "robustness_asset_labels.csv", index=False)
    write_statistical_appendix(metrics, portfolio_metrics, bootstrap, attribution, labels, output_dir)
    write_robustness_stress_md(
        pd.read_csv(stress_path) if stress_path.exists() else pd.DataFrame(),
        labels,
        output_dir,
    )
    write_final_validation_report(output_dir)
    return metrics, portfolio_metrics, bootstrap


def build_attribution_tables(enriched: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    group_cols = ["asset", "side", "order_size", "regime"]
    attribution = (
        enriched.groupby(group_cols, dropna=False)
        .agg(
            n_trades=("datetime", "count"),
            strategy_vs_agent_econ=("pnl_vs_agent_econ", "sum"),
            strategy_vs_benchmark_econ=("pnl_vs_benchmark_econ", "sum"),
            benchmark_vs_agent_econ=("benchmark_vs_agent_econ", "sum"),
            mean_improvement_ticks=("improvement_ticks_per_contract", "mean"),
            pct_trades_beat_agent=("pnl_vs_agent_econ", lambda x: float((x > 0).mean() * 100.0)),
        )
        .reset_index()
    )
    attribution.to_csv(output_dir / "attribution_by_asset_side_size_regime.csv", index=False)

    asset_attr = (
        enriched.groupby("asset", dropna=False)
        .agg(
            n_trades=("datetime", "count"),
            strategy_vs_agent_econ=("pnl_vs_agent_econ", "sum"),
            strategy_vs_benchmark_econ=("pnl_vs_benchmark_econ", "sum"),
            benchmark_vs_agent_econ=("benchmark_vs_agent_econ", "sum"),
            mean_improvement_ticks=("improvement_ticks_per_contract", "mean"),
        )
        .reset_index()
    )
    asset_attr.to_csv(output_dir / "attribution_by_asset.csv", index=False)
    return asset_attr


def write_statistical_appendix(
    metrics: pd.DataFrame,
    portfolio_metrics: pd.DataFrame,
    bootstrap: pd.DataFrame,
    attribution: pd.DataFrame,
    labels: pd.DataFrame,
    output_dir: Path,
) -> None:
    portfolio = portfolio_metrics.iloc[0].to_dict() if len(portfolio_metrics) else {}
    portfolio_boot = (
        bootstrap[bootstrap["scope"] == "portfolio"].iloc[0].to_dict()
        if len(bootstrap) and "scope" in bootstrap
        else {}
    )
    lines = [
        "# Statistical Validation Appendix",
        "",
        "This appendix evaluates the corrected raw-tick strategy against AIAgent using daily economic PnL, risk metrics, day-block bootstrap intervals, and attribution.",
        "",
        "## Framework",
        "",
        "- Trade-level incremental PnL: `side * (agent_price - strategy_price) * qty`.",
        "- Economic conversion: `(price-unit PnL / raw_tick) * tick_value`.",
        "- Daily PnL is summed by calendar day before computing Sharpe, Sortino, drawdown, sign tests, and bootstrap intervals.",
        "- AIAgent is a comparator only; it is never used to place strategy orders.",
        "",
        "## ePDF Definition",
        "",
        "For tau-bar `j`, `RangeUp = round((High_j - Open_j) / raw_tick / ell_divisor)` and `RangeDown = round((Open_j - Low_j) / raw_tick / ell_divisor)`, both capped at 80.",
        "State is `S_j = (volume_bin, volatility_bin, trend_bin)` from historical EWMA/EWMV and lagged trend only.",
        "At signal time, buy orders use the smoothed empirical distribution `P(RangeDown=d | S_j)` and sell orders use `P(RangeUp=d | S_j)` from completed prior bars; missing state history falls back to the unconditional ePDF with Laplace smoothing.",
        "",
        "## Portfolio Result",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total economic PnL vs AIAgent | {format_float(portfolio.get('total_pnl_econ'), 8)} |",
        f"| Daily Sharpe | {format_float(portfolio.get('daily_sharpe'), 5)} |",
        f"| Daily Sortino | {format_float(portfolio.get('daily_sortino'), 5)} |",
        f"| Max drawdown | {format_float(portfolio.get('max_drawdown_econ'), 8)} |",
        f"| PnL / MDD | {format_float(portfolio.get('pnl_to_mdd'), 5)} |",
        f"| Bootstrap total PnL 2.5% | {format_float(portfolio_boot.get('total_pnl_ci_lower'), 8)} |",
        f"| Bootstrap total PnL 97.5% | {format_float(portfolio_boot.get('total_pnl_ci_upper'), 8)} |",
        "",
        "## Asset Risk Metrics",
        "",
        df_to_markdown(
            metrics[
                [
                    "asset",
                    "total_pnl_econ",
                    "daily_sharpe",
                    "max_drawdown_econ",
                    "profit_factor",
                    "pnl_to_mdd",
                    "stress_pass_rate_pct",
                ]
                if "stress_pass_rate_pct" in metrics.columns
                else [
                    "asset",
                    "total_pnl_econ",
                    "daily_sharpe",
                    "max_drawdown_econ",
                    "profit_factor",
                    "pnl_to_mdd",
                ]
            ]
        ),
        "",
        "## Robustness Labels",
        "",
        df_to_markdown(
            labels[
                [
                    "asset",
                    "robustness_label",
                    "stress_pass_rate_pct",
                    "daily_sharpe",
                    "pnl_to_mdd",
                    "total_pnl_ci_lower",
                    "matching_coverage_pct",
                    "inside_ohlc_pct",
                ]
            ]
        ),
        "",
        "## Attribution by Asset",
        "",
        df_to_markdown(
            attribution[
                [
                    "asset",
                    "strategy_vs_agent_econ",
                    "strategy_vs_benchmark_econ",
                    "benchmark_vs_agent_econ",
                    "mean_improvement_ticks",
                ]
            ]
        ),
    ]
    (output_dir / "STATISTICAL_VALIDATION_APPENDIX.md").write_text("\n".join(lines) + "\n")


def robustness_matrix(
    output_dir: Path = OUTPUT_DIR,
    canonical: Optional[pd.DataFrame] = None,
    tick_audit: Optional[pd.DataFrame] = None,
    matching_recommendation: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    output_dir = ensure_output_dir(output_dir)
    if canonical is None or canonical.empty:
        canonical = canonical_results(output_dir=output_dir)
    unit_issues = (
        tick_audit.set_index("asset")["unit_issue"].to_dict()
        if tick_audit is not None and not tick_audit.empty
        else {}
    )
    front_supported = (
        matching_recommendation.set_index("asset")["front_month_default_supported"].to_dict()
        if matching_recommendation is not None and not matching_recommendation.empty
        else {}
    )
    corrected_path = output_dir / "corrected_raw_all" / "all_exchanges_benchmark_vs_ai.csv"
    corrected = pd.read_csv(corrected_path) if corrected_path.exists() else pd.DataFrame()

    scenario_rows = []
    selectors = ["current", "calendar_front_month", "volume_front_month"]
    tick_sources = ["legacy", "raw"]
    taus = [15, 30, 45]
    fill_policies = ["strict_next_bar", "default"]
    remainder_policies = ["best_or_benchmark", "benchmark", "close"]
    for asset in ASSET_CONFIGS:
        base = canonical[canonical["exchange"] == asset] if canonical is not None else pd.DataFrame()
        base_pnl = float(base["total_pnl_vs_aiagent"].iloc[0]) if len(base) else np.nan
        base_win = bool(base_pnl > 0) if np.isfinite(base_pnl) else False
        corrected_row = corrected[corrected["exchange"] == asset] if not corrected.empty else pd.DataFrame()
        corrected_pnl = (
            float(corrected_row["total_pnl_vs_aiagent"].iloc[0])
            if len(corrected_row)
            else np.nan
        )
        corrected_win = bool(corrected_pnl > 0) if np.isfinite(corrected_pnl) else False
        issue = bool(unit_issues.get(asset, False))
        front_ok = bool(front_supported.get(asset, False))
        if issue and not corrected_win:
            label = "unit/matching issue"
            rationale = "Legacy result used stale or scaled tick units; corrected raw-tick rerun required."
        elif corrected_win:
            label = "fragile win"
            rationale = "Corrected raw-tick tau45 run wins; selector/tau/fill/remainder robustness grid remains pending."
        elif not base_win:
            label = "loss"
            rationale = "Current provisional baseline does not beat AIAgent."
        elif front_ok:
            label = "fragile win"
            rationale = "Current result wins, but robustness scenarios must be rerun before marking robust."
        else:
            label = "fragile win"
            rationale = "Current result wins; matching audit does not yet justify a front-month default."
        for selector, tick_source, tau, fill_policy, remainder_policy in itertools.product(
            selectors, tick_sources, taus, fill_policies, remainder_policies
        ):
            is_current = (
                selector == "current"
                and tick_source == "legacy"
                and tau == 45
                and fill_policy == "default"
                and remainder_policy == "best_or_benchmark"
            )
            is_corrected = (
                selector == "current"
                and tick_source == "raw"
                and tau == 45
                and fill_policy == "default"
                and remainder_policy == "best_or_benchmark"
                and np.isfinite(corrected_pnl)
            )
            scenario_rows.append(
                {
                    "asset": asset,
                    "contract_selector": selector,
                    "tick_source": tick_source,
                    "tau": tau,
                    "fill_policy": fill_policy,
                    "remainder_policy": remainder_policy,
                    "status": "existing_provisional" if is_current else ("corrected_raw_run" if is_corrected else "requires_rerun"),
                    "total_pnl_vs_aiagent": base_pnl if is_current else (corrected_pnl if is_corrected else np.nan),
                    "beat_ai": base_win if is_current else (corrected_win if is_corrected else np.nan),
                    "robustness_label": label,
                    "rationale": rationale,
                }
            )
    df = pd.DataFrame(scenario_rows)
    df.to_csv(output_dir / "robustness_matrix.csv", index=False)
    write_robustness_md(df, output_dir)
    return df


def write_robustness_md(df: pd.DataFrame, output_dir: Path) -> None:
    labels = (
        df[["asset", "robustness_label", "rationale"]]
        .drop_duplicates()
        .sort_values("asset")
    )
    lines = [
        "# Robustness Matrix",
        "",
        "The matrix enumerates selector, tick-source, tau, fill-policy, and remainder-policy scenarios.",
        "Rows marked `requires_rerun` are deliberate next-step checks; no new tuning is implied.",
        "",
        "| Asset | Label | Rationale |",
        "|---|---|---|",
    ]
    for _, row in labels.iterrows():
        lines.append(f"| {row['asset']} | {row['robustness_label']} | {row['rationale']} |")
    lines.extend(["", "Full scenario grid is in `robustness_matrix.csv`."])
    (output_dir / "robustness_matrix.md").write_text("\n".join(lines) + "\n")


def write_final_validation_report(output_dir: Path = OUTPUT_DIR) -> None:
    output_dir = ensure_output_dir(output_dir)
    tick_path = output_dir / "tick_audit.csv"
    match_path = output_dir / "matching_selector_recommendation.csv"
    canonical_path = output_dir / "canonical_strategy_results_provisional.csv"
    robust_path = output_dir / "robustness_matrix.csv"
    labels_path = output_dir / "robustness_asset_labels.csv"
    stats_path = output_dir / "statistical_metrics_by_asset.csv"
    portfolio_stats_path = output_dir / "statistical_metrics_portfolio.csv"

    tick_df = pd.read_csv(tick_path) if tick_path.exists() else pd.DataFrame()
    match_df = pd.read_csv(match_path) if match_path.exists() else pd.DataFrame()
    canonical_df = pd.read_csv(canonical_path) if canonical_path.exists() else pd.DataFrame()
    robust_df = pd.read_csv(robust_path) if robust_path.exists() else pd.DataFrame()
    labels_df = pd.read_csv(labels_path) if labels_path.exists() else pd.DataFrame()
    stats_df = pd.read_csv(stats_path) if stats_path.exists() else pd.DataFrame()
    portfolio_stats = pd.read_csv(portfolio_stats_path) if portfolio_stats_path.exists() else pd.DataFrame()

    lines = [
        "# Validation and Robustness Report",
        "",
        "The May 21 `strategy_all` result table is retained as historical/provisional. The corrected raw-tick table in `corrected_raw_strategy_results.csv` is the current canonical validation output.",
        "",
        "## Objective",
        "",
        "Compare the project strategy against AIAgent on the same timestamps, side, quantity, benchmark open, and fill policy, with no AIAgent price used for strategy placement.",
        "",
        "## Tick Unit Rule",
        "",
        "`raw_tick` is used for ePDF distances, limit offsets, fill checks, and backtest slippage. `exchange_tick` and `tick_value` are documentation/economic fields only.",
        "",
        "| Asset | Raw Tick | Exchange Tick | Multiplier | Source |",
        "|---|---:|---:|---:|---|",
    ]
    for _, row in tick_df.iterrows():
        source = row.get("tick_source_url", "")
        has_source = isinstance(source, str) and len(source.strip()) > 0
        source_label = "official/local audit" if source else "local raw increment audit"
        source_md = f"[{source_label}]({source})" if has_source else "local raw increment audit"
        lines.append(
            "| {asset} | {raw} | {exchange} | {mult} | {source} |".format(
                asset=row["asset"],
                raw=format_float(row["configured_raw_tick"]),
                exchange=format_float(row["exchange_tick"]),
                mult=format_float(row["display_multiplier"], 6),
                source=source_md,
            )
        )
    lines.extend(
        [
            "",
            "## Official Citation Places",
            "",
            "| Asset | Exact Place |",
            "|---|---|",
        ]
    )
    for source in TICK_SOURCE_ROWS:
        lines.append(f"| {source['asset']} | [{source['official_source']}]({source['url']}), {source['exact_place']} |")

    lines.extend(["", "## Matching Decision", "", "| Asset | Best Selector | Front-Month Default Supported |"])
    lines.append("|---|---|---:|")
    for _, row in match_df.iterrows():
        lines.append(
            f"| {row['asset']} | {row['best_selector']} | {row['front_month_default_supported']} |"
        )

    lines.extend(
        [
            "",
            "## ePDF Definition",
            "",
            "For tau-bar `j`, `RangeUp = round((High_j - Open_j) / raw_tick / ell_divisor)` and `RangeDown = round((Open_j - Low_j) / raw_tick / ell_divisor)`, capped at 80.",
            "State is `S_j = (volume_bin, volatility_bin, trend_bin)` from lagged EWMA/EWMV and trend only.",
            "At signal time, buy orders use `P(RangeDown=d | S_j)` and sell orders use `P(RangeUp=d | S_j)` from completed prior bars; missing state history falls back to unconditional smoothed ePDF mass.",
        ]
    )

    lines.extend(["", "## Provisional Canonical Results", ""])
    if not canonical_df.empty:
        keep = [
            "exchange",
            "tick",
            "raw_tick",
            "exchange_tick",
            "total_pnl_vs_aiagent",
            "pct_trades_beat_ai",
            "beat_ai_overall",
            "unit_issue",
        ]
        lines.append(df_to_markdown(canonical_df[[c for c in keep if c in canonical_df.columns]]))
    else:
        lines.append("No canonical result table found.")

    corrected_all_path = output_dir / "corrected_raw_all" / "all_exchanges_benchmark_vs_ai.csv"
    if corrected_all_path.exists():
        corrected_all = pd.read_csv(corrected_all_path)
        corrected_copy = output_dir / "corrected_raw_strategy_results.csv"
        corrected_all.to_csv(corrected_copy, index=False)
        keep = [
            "exchange",
            "tick",
            "raw_tick",
            "exchange_tick",
            "total_pnl_vs_aiagent",
            "pct_trades_beat_ai",
            "beat_ai_overall",
        ]
        lines.extend(
            [
                "",
                "## Corrected Raw-Tick All-Market Results",
                "",
                df_to_markdown(corrected_all[[c for c in keep if c in corrected_all.columns]]),
            ]
        )

    corrected_summaries = sorted(output_dir.glob("corrected_raw_*/*/run_summary.json"))
    corrected_summaries = [
        path for path in corrected_summaries if "corrected_raw_all" not in path.parts
    ]
    if corrected_summaries:
        lines.extend(
            [
                "",
                "## Corrected Raw-Tick Spot Checks",
                "",
                "| Exchange | Tick | Median Ell Raw | Ell Divisor | PnL vs AIAgent | % Trades Beat Agent |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for path in corrected_summaries:
            summary = read_json(path)
            cal = summary.get("exchange_calibration", {})
            lines.append(
                "| {exchange} | {tick} | {median_ell} | {ell_divisor} | {pnl} | {beat} |".format(
                    exchange=summary.get("exchange", path.parent.name),
                    tick=format_float(summary.get("tick")),
                    median_ell=format_float(cal.get("median_ell_raw")),
                    ell_divisor=format_float(cal.get("ell_divisor")),
                    pnl=format_float(summary.get("total_pnl_vs_aiagent")),
                    beat=format_float(summary.get("pct_trades_beat_ai"), 6),
                )
            )

    if not stats_df.empty:
        lines.extend(
            [
                "",
                "## Statistical Risk Metrics",
                "",
            ]
        )
        if not portfolio_stats.empty:
            p = portfolio_stats.iloc[0]
            lines.extend(
                [
                    "| Portfolio Metric | Value |",
                    "|---|---:|",
                    f"| Total economic PnL vs AIAgent | {format_float(p.get('total_pnl_econ'), 8)} |",
                    f"| Daily Sharpe | {format_float(p.get('daily_sharpe'), 5)} |",
                    f"| Max drawdown | {format_float(p.get('max_drawdown_econ'), 8)} |",
                    f"| PnL / MDD | {format_float(p.get('pnl_to_mdd'), 5)} |",
                    "",
                ]
            )
        keep = [
            "asset",
            "total_pnl_econ",
            "daily_sharpe",
            "max_drawdown_econ",
            "profit_factor",
            "pnl_to_mdd",
            "stress_pass_rate_pct",
        ]
        lines.append(df_to_markdown(stats_df[[c for c in keep if c in stats_df.columns]]))

    lines.extend(["", "## Robustness Labels", ""])
    if not labels_df.empty:
        keep = [
            "asset",
            "robustness_label",
            "stress_pass_rate_pct",
            "daily_sharpe",
            "pnl_to_mdd",
            "total_pnl_ci_lower",
            "matching_coverage_pct",
            "inside_ohlc_pct",
        ]
        lines.append(df_to_markdown(labels_df[[c for c in keep if c in labels_df.columns]]))
    elif not robust_df.empty:
        labels = robust_df[["asset", "robustness_label"]].drop_duplicates().sort_values("asset")
        lines.append(df_to_markdown(labels))

    lines.extend(
        [
            "",
            "## Reproducibility Commands",
            "",
            "```bash",
            "python -B validation_framework.py all",
            "python -B validation_framework.py run-robustness --grid defensible",
            "python -B validation_framework.py stats --bootstrap-days 2000",
            "python -B run_tests_simple.py",
            "```",
            "",
            "The full-pipeline entry point `order_execution_project.py` is joint work and is",
            "not distributed with this repository; `run-robustness` therefore requires it",
            "and is the only command that does. See `EXCLUSIONS.md`.",
        ]
    )
    (output_dir / "VALIDATION_ROBUSTNESS_REPORT.md").write_text("\n".join(lines) + "\n")


def run_all(output_dir: Path = OUTPUT_DIR, data_root: Path = DATA_ROOT, results_root: Path = RESULTS_ROOT) -> None:
    tick_df = audit_ticks(data_root, output_dir)
    _, _, match_rec = audit_matching(data_root, output_dir)
    canon = canonical_results(results_root, output_dir, tick_df)
    fair_compare(results_root, output_dir)
    robustness_matrix(output_dir, canon, tick_df, match_rec)
    write_final_validation_report(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "all",
            "tick-audit",
            "matching-audit",
            "canonical",
            "fair-compare",
            "robustness",
            "run-robustness",
            "stats",
            "report",
        ],
    )
    parser.add_argument("--data-root", default=str(DATA_ROOT))
    parser.add_argument("--results-root", default=str(RESULTS_ROOT))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--grid", default="defensible", choices=["defensible"])
    parser.add_argument("--bootstrap-days", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=4703)
    parser.add_argument(
        "--signal-mode",
        default="position_change",
        choices=["position_change", "nonzero_signal", "all"],
        help="AIAgent rows to use for contract matching audit",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    results_root = Path(args.results_root)
    output_dir = Path(args.output_dir)

    if args.command == "all":
        run_all(output_dir, data_root, results_root)
    elif args.command == "tick-audit":
        audit_ticks(data_root, output_dir)
    elif args.command == "matching-audit":
        audit_matching(data_root, output_dir, signal_mode=args.signal_mode)
    elif args.command == "canonical":
        tick_df = pd.read_csv(output_dir / "tick_audit.csv") if (output_dir / "tick_audit.csv").exists() else None
        canonical_results(results_root, output_dir, tick_df)
    elif args.command == "fair-compare":
        fair_compare(results_root, output_dir)
    elif args.command == "robustness":
        tick_df = pd.read_csv(output_dir / "tick_audit.csv") if (output_dir / "tick_audit.csv").exists() else None
        match_df = (
            pd.read_csv(output_dir / "matching_selector_recommendation.csv")
            if (output_dir / "matching_selector_recommendation.csv").exists()
            else None
        )
        canon = canonical_results(results_root, output_dir, tick_df)
        robustness_matrix(output_dir, canon, tick_df, match_df)
    elif args.command == "run-robustness":
        run_robustness_grid(data_root, output_dir, grid=args.grid)
    elif args.command == "report":
        write_final_validation_report(output_dir)
    elif args.command == "stats":
        build_statistical_report(output_dir, n_bootstrap=args.bootstrap_days, seed=args.seed)


if __name__ == "__main__":
    main()
