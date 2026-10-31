"""
Contract matching and tick-audit helpers.

This module is intentionally independent from the strategy logic so validation can
compare contract-selection assumptions before a backtest result is treated as
canonical.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from config import get_config, get_raw_tick


MONTH_CODES = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}

SELECTORS = ("min_distance", "inside_high_volume", "calendar_front_month", "volume_front_month")


@dataclass(frozen=True)
class ContractCandidate:
    name: str
    is_inside: bool
    distance_price: float
    distance_ticks: float
    low: float
    high: float
    volume: float
    bars_in_window: int
    maturity_year: int
    maturity_month: int


def parse_contract_month(contract_name: str) -> tuple[int, int]:
    """Parse a futures code such as JYZ24 or HOF22 into (year, month)."""
    match = re.search(r"([FGHJKMNQUVXZ])(\d{2})$", contract_name)
    if not match:
        return (9999, 99)
    year_2d = int(match.group(2))
    year = 2000 + year_2d if year_2d < 70 else 1900 + year_2d
    return year, MONTH_CODES[match.group(1)]


def load_agent_data(agent_file: str | Path, signal_mode: str = "position_change") -> pd.DataFrame:
    """Load AIAgent data and select either position changes or non-zero signals."""
    df = pd.read_csv(agent_file, header=None, names=["date", "hour", "min", "price", "signal"])
    start_date = datetime(1900, 1, 1)
    df["datetime"] = df.apply(
        lambda row: start_date
        + timedelta(days=int(row["date"]) - 2, hours=int(row["hour"]), minutes=int(row["min"])),
        axis=1,
    )
    df = df.set_index("datetime").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df["position_change"] = df["signal"].diff()
    df["leg_type"] = "flat"
    df.loc[df["position_change"] > 0, "leg_type"] = "buy"
    df.loc[df["position_change"] < 0, "leg_type"] = "sell"
    df["side"] = np.sign(df["signal"]).astype(int)
    df.loc[(df["leg_type"] == "flat") & (df["side"] > 0), "leg_type"] = "buy"
    df.loc[(df["leg_type"] == "flat") & (df["side"] < 0), "leg_type"] = "sell"

    if signal_mode == "position_change":
        return df[df["position_change"].abs() > 0].copy()
    if signal_mode == "nonzero_signal":
        return df[df["signal"] != 0].copy()
    if signal_mode == "all":
        return df.copy()
    raise ValueError(f"Unknown signal_mode: {signal_mode}")


def load_contract_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None)
    df.columns = ["datetime", "open", "high", "low", "close", "volume"]
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d.%H:%M:%S", errors="coerce")
    df = df.dropna(subset=["datetime"])
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    df = df.sort_values("datetime").set_index("datetime")
    return df[~df.index.duplicated(keep="last")]


def load_contracts(asset_dir: str | Path) -> Dict[str, pd.DataFrame]:
    contracts = {}
    for path in sorted(glob.glob(os.path.join(str(asset_dir), "*.csv"))):
        if os.path.basename(path).lower().startswith("aiagent"):
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        contracts[name] = load_contract_csv(path)
    return contracts


def calculate_buy_sell_distance(
    agent_price: float,
    ohlc_low: float,
    ohlc_high: float,
    leg_type: str,
    tick_size: float,
) -> dict:
    """
    Distance from agent price to the nearest OHLC boundary.

    The previous validation logic was directional and could return zero for an
    outside price on the "wrong" side of the range. Matching should measure
    whether the observed price is inside the contract's OHLC envelope, regardless
    of buy/sell side.
    """
    is_inside = ohlc_low <= agent_price <= ohlc_high
    if is_inside:
        distance_price = 0.0
        reference_point = "inside"
    elif agent_price < ohlc_low:
        distance_price = ohlc_low - agent_price
        reference_point = "low"
    else:
        distance_price = agent_price - ohlc_high
        reference_point = "high"

    return {
        "is_inside": is_inside,
        "distance_ticks": distance_price / tick_size if tick_size else np.nan,
        "distance_price": distance_price,
        "reference_point": reference_point,
        "leg_type": leg_type,
    }


def _candidate_from_window(
    name: str,
    cdf: pd.DataFrame,
    lookback_times: Sequence[pd.Timestamp],
    agent_price: float,
    leg_type: str,
    tick_size: float,
) -> Optional[ContractCandidate]:
    existing = cdf.index.intersection(lookback_times)
    if len(existing) == 0:
        return None
    subset = cdf.loc[existing]
    low = float(subset["low"].min())
    high = float(subset["high"].max())
    volume = float(subset["volume"].sum())
    distance = calculate_buy_sell_distance(agent_price, low, high, leg_type, tick_size)
    year, month = parse_contract_month(name)
    return ContractCandidate(
        name=name,
        is_inside=bool(distance["is_inside"]),
        distance_price=float(distance["distance_price"]),
        distance_ticks=float(distance["distance_ticks"]),
        low=low,
        high=high,
        volume=volume,
        bars_in_window=int(len(existing)),
        maturity_year=year,
        maturity_month=month,
    )


def candidates_for_trade(
    timestamp: pd.Timestamp,
    agent_price: float,
    leg_type: str,
    contracts: Dict[str, pd.DataFrame],
    tick_size: float,
    lookback_minutes: int = 5,
) -> List[ContractCandidate]:
    lookback_times = [
        timestamp - pd.Timedelta(minutes=i) for i in range(lookback_minutes - 1, -1, -1)
    ]
    candidates = []
    for name, cdf in contracts.items():
        candidate = _candidate_from_window(name, cdf, lookback_times, agent_price, leg_type, tick_size)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def select_contract(
    candidates: Sequence[ContractCandidate],
    selector: str,
    timestamp: Optional[pd.Timestamp] = None,
) -> Optional[ContractCandidate]:
    if not candidates:
        return None
    if selector == "min_distance":
        return min(candidates, key=lambda c: (c.distance_ticks, -int(c.is_inside), c.maturity_year, c.maturity_month))
    if selector == "inside_high_volume":
        inside = [c for c in candidates if c.is_inside]
        return max(inside, key=lambda c: (c.volume, -c.maturity_year, -c.maturity_month)) if inside else None
    if selector == "calendar_front_month":
        if timestamp is None:
            raise ValueError("calendar_front_month requires timestamp")
        ym = (timestamp.year, timestamp.month)
        live = [c for c in candidates if (c.maturity_year, c.maturity_month) >= ym]
        pool = live or list(candidates)
        return min(pool, key=lambda c: (c.maturity_year, c.maturity_month, -c.volume))
    if selector == "volume_front_month":
        return max(candidates, key=lambda c: (c.volume, -c.maturity_year, -c.maturity_month))
    raise ValueError(f"Unknown selector: {selector}")


def infer_min_increment_from_values(values: Iterable[float], precision: int = 10) -> float:
    clean = np.array([v for v in values if np.isfinite(v)], dtype=float)
    if clean.size < 2:
        return np.nan
    clean = np.unique(np.round(clean, precision))
    diffs = np.diff(np.sort(clean))
    diffs = diffs[diffs > 10 ** (-precision)]
    return float(diffs.min()) if diffs.size else np.nan


def infer_raw_tick_for_asset(asset_dir: str | Path) -> float:
    values: List[float] = []
    for path in sorted(Path(asset_dir).glob("*.csv")):
        if path.name.startswith("."):
            continue
        if path.name.lower().startswith("aiagent"):
            df = pd.read_csv(path, header=None, names=["date", "hour", "min", "price", "signal"])
            values.extend(pd.to_numeric(df["price"], errors="coerce").dropna().tolist())
        else:
            df = pd.read_csv(path, header=None, names=["datetime", "open", "high", "low", "close", "volume"])
            for column in ["open", "high", "low", "close"]:
                values.extend(pd.to_numeric(df[column], errors="coerce").dropna().tolist())
    return infer_min_increment_from_values(values)


def roll_dates_from_selection(detail: pd.DataFrame) -> List[dict]:
    if detail.empty or "selected_contract" not in detail:
        return []
    selected = detail.dropna(subset=["selected_contract"]).sort_values("datetime")
    if selected.empty:
        return []
    shifts = selected["selected_contract"].ne(selected["selected_contract"].shift())
    rolls = selected.loc[shifts, ["datetime", "selected_contract"]]
    return [
        {"datetime": str(row["datetime"]), "selected_contract": row["selected_contract"]}
        for _, row in rolls.iterrows()
    ]


def audit_asset_matching(
    asset: str,
    base_dir: str | Path = "data_export",
    selectors: Sequence[str] = SELECTORS,
    signal_mode: str = "position_change",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    asset_dir = Path(base_dir) / asset
    cfg = get_config(asset)
    agent_files = [
        path for path in asset_dir.glob("*.csv") if cfg["agent_pattern"].lower() in path.name.lower()
    ]
    if not agent_files:
        raise FileNotFoundError(f"No AIAgent file matching {cfg['agent_pattern']} in {asset_dir}")

    trades = load_agent_data(agent_files[0], signal_mode=signal_mode)
    contracts = load_contracts(asset_dir)
    tick = get_raw_tick(asset)
    detail_rows = []

    for timestamp, row in trades.iterrows():
        candidates = candidates_for_trade(
            pd.Timestamp(timestamp),
            float(row["price"]),
            str(row["leg_type"]),
            contracts,
            tick,
        )
        inside_count = sum(c.is_inside for c in candidates)
        min_choice = select_contract(candidates, "min_distance", pd.Timestamp(timestamp))
        for selector in selectors:
            selected = select_contract(candidates, selector, pd.Timestamp(timestamp))
            detail_rows.append(
                {
                    "asset": asset,
                    "datetime": timestamp,
                    "selector": selector,
                    "agent_price": float(row["price"]),
                    "signal": float(row["signal"]),
                    "side": int(row.get("side", 0)),
                    "leg_type": row["leg_type"],
                    "selected_contract": selected.name if selected else None,
                    "is_inside": selected.is_inside if selected else False,
                    "distance_ticks": selected.distance_ticks if selected else np.nan,
                    "distance_price": selected.distance_price if selected else np.nan,
                    "candidate_count": len(candidates),
                    "inside_candidate_count": inside_count,
                    "ambiguous_inside": inside_count > 1,
                    "same_as_min_distance": bool(selected and min_choice and selected.name == min_choice.name),
                }
            )

    detail = pd.DataFrame(detail_rows)
    summary_rows = []
    total = len(trades)
    for selector, group in detail.groupby("selector", dropna=False):
        matched = group["selected_contract"].notna()
        inside = group["is_inside"].fillna(False)
        contract_counts = (
            group.loc[matched, "selected_contract"].value_counts().head(5).to_dict()
            if not group.empty
            else {}
        )
        summary_rows.append(
            {
                "asset": asset,
                "selector": selector,
                "signal_mode": signal_mode,
                "n_signals": total,
                "coverage_pct": 100.0 * matched.sum() / total if total else 0.0,
                "inside_ohlc_pct": 100.0 * inside.sum() / total if total else 0.0,
                "median_distance_ticks": float(group.loc[matched, "distance_ticks"].median()) if matched.any() else np.nan,
                "mean_distance_ticks": float(group.loc[matched, "distance_ticks"].mean()) if matched.any() else np.nan,
                "ambiguous_inside_count": int(group["ambiguous_inside"].sum()),
                "ambiguous_inside_pct": 100.0 * group["ambiguous_inside"].sum() / total if total else 0.0,
                "same_as_min_distance_pct": 100.0 * group["same_as_min_distance"].sum() / matched.sum() if matched.any() else 0.0,
                "selected_contract_distribution": contract_counts,
                "roll_dates": roll_dates_from_selection(group),
            }
        )
    return pd.DataFrame(summary_rows), detail
