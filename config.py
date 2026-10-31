"""
Centralized market configuration.

Important distinction:
- exchange_tick is the official exchange minimum price fluctuation.
- raw_tick is the price increment used by the CSV files in this repository.
- display_multiplier = raw_tick / exchange_tick.

Backtests and ePDF distances must use raw_tick because OHLC and AIAgent prices
are stored in raw CSV display units. Reports can cite exchange_tick/tick_value
for economic interpretation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Tuple


DEFAULT_DISTANCE_BINS = [0, 0.5, 1, 1.5, 2, 3, 4, 5, 7, 10, 15, 20, float("inf")]
DEFAULT_BIN_LABELS = [
    "0",
    "0.5",
    "1",
    "1.5",
    "2",
    "3",
    "4",
    "5",
    "7",
    "10",
    "15",
    "20+",
]


ASSET_CONFIGS: Dict[str, Dict[str, Any]] = {
    "Nasdaq": {
        "exchange_tick": 0.25,
        "raw_tick": 0.25,
        "display_multiplier": 1.0,
        "tick_value": 5.0,
        "tick_size": 0.25,  # Backward-compatible alias for raw_tick.
        "legacy_tick_size": 0.25,
        "agent_pattern": "AIAgent_Nasdaq",
        "distance_bins": [0, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 7, 10, float("inf")],
        "bin_labels": ["0", "0.25", "0.5", "0.75", "1", "1.5", "2", "3", "4", "5", "7", "10+"],
        "tick_source_url": "",
        "tick_source_note": "Not part of the current unit-fix audit; raw tick inferred from local CSV prices.",
    },
    "German Bunds - German Government Bonds": {
        "exchange_tick": 0.01,
        "raw_tick": 0.01,
        "display_multiplier": 1.0,
        "tick_value": 10.0,
        "tick_size": 0.01,
        "legacy_tick_size": 0.01,
        "agent_pattern": "AIAgent_Bunds",
        "distance_bins": DEFAULT_DISTANCE_BINS,
        "bin_labels": DEFAULT_BIN_LABELS,
        "tick_source_url": "",
        "tick_source_note": "Not part of the current unit-fix audit; raw tick inferred from local CSV prices.",
    },
    "EuroStoxx": {
        "exchange_tick": 0.5,
        "raw_tick": 0.5,
        "display_multiplier": 1.0,
        "tick_value": 5.0,
        "tick_size": 0.5,
        "legacy_tick_size": 1.0,
        "agent_pattern": "AIAgent_EuroStoxx",
        "distance_bins": DEFAULT_DISTANCE_BINS,
        "bin_labels": DEFAULT_BIN_LABELS,
        "tick_source_url": "https://www.eurex.com/ex-en/find/circulars/circular-2407638",
        "tick_source_note": (
            "Eurex Circular 007/21, Introduction and tick table: FESX outright tick changed "
            "from 1.0 to 0.5 index points effective 2021-06-21."
        ),
    },
    "Gold": {
        "exchange_tick": 0.1,
        "raw_tick": 0.1,
        "display_multiplier": 1.0,
        "tick_value": 10.0,
        "tick_size": 0.1,
        "legacy_tick_size": 0.1,
        "agent_pattern": "AIAgent_Gold",
        "distance_bins": [0, 0.5, 1, 1.5, 2, 3, 5, 7, 10, 15, 20, 30, float("inf")],
        "bin_labels": ["0", "0.5", "1", "1.5", "2", "3", "5", "7", "10", "15", "20", "30+"],
        "tick_source_url": "",
        "tick_source_note": "Not part of the current unit-fix audit; raw tick inferred from local CSV prices.",
    },
    "HeatingOil": {
        "exchange_tick": 0.0001,
        "raw_tick": 0.01,
        "display_multiplier": 100.0,
        "tick_value": 4.20,
        "tick_size": 0.01,
        "legacy_tick_size": 0.0001,
        "agent_pattern": "AIAgent_HeatingOil",
        "distance_bins": [0, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30, 50, float("inf")],
        "bin_labels": ["0", "0.5", "1", "2", "3", "5", "7", "10", "15", "20", "30", "50+"],
        "strict_inside_match": True,
        "tick_source_url": "https://www.cmegroup.com/education/courses/introduction-to-energy/introduction-to-refined-products/heating-oil-product-overview.html",
        "tick_source_note": (
            "CME Heating Oil Product Overview, The Contract: minimum price fluctuation is "
            "$0.0001 per gallon, or $4.20 per contract. Local CSV prices are scaled by 100."
        ),
    },
    "JPY - Japanese Yen": {
        "exchange_tick": 0.0000005,
        "raw_tick": 0.005,
        "display_multiplier": 10000.0,
        "tick_value": 6.25,
        "tick_size": 0.005,
        "legacy_tick_size": 0.000001,
        "agent_pattern": "AIAgent_JPY",
        "distance_bins": [0, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30, 50, float("inf")],
        "bin_labels": ["0", "0.5", "1", "2", "3", "5", "7", "10", "15", "20", "30", "50+"],
        "contract_rollover": {
            "JYH25": "2024-12-15",
        },
        "tick_source_url": "https://www.cmegroup.com/trading/why-futures/welcome-to-cme-fx-futures.html",
        "tick_source_note": (
            "CME FX Futures page, Trade the Currencies You Want table: Japanese Yen minimum "
            "tick size is $0.0000005 per yen and dollar value of a tick is $6.25. Local CSV "
            "prices are scaled by 10,000."
        ),
    },
    "GBP - British Pound": {
        "exchange_tick": 0.0001,
        "raw_tick": 0.01,
        "display_multiplier": 100.0,
        "tick_value": 6.25,
        "tick_size": 0.01,
        "legacy_tick_size": 0.0001,
        "agent_pattern": "AIAgent_GBP",
        "distance_bins": [0, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30, 50, float("inf")],
        "bin_labels": ["0", "0.5", "1", "2", "3", "5", "7", "10", "15", "20", "30", "50+"],
        "contract_rollover": {
            "BPZ20": "2020-09-15",
        },
        "tick_source_url": "https://www.cmegroup.com/education/lessons/british-pound-product-overview",
        "tick_source_note": (
            "CME British Pound Product Overview, The Contract: minimum price fluctuation is "
            ".0001 per British pound. Local CSV prices are scaled by 100."
        ),
    },
}


def _match_asset(asset_name: str) -> str | None:
    if asset_name in ASSET_CONFIGS:
        return asset_name
    needle = asset_name.lower()
    for key in ASSET_CONFIGS:
        if key.lower() in needle or needle in key.lower():
            return key
    return None


def get_config(asset_name: str) -> Dict[str, Any]:
    """Return a defensive copy of the full config dict for asset_name."""
    key = _match_asset(asset_name)
    if key is None:
        return {
            "exchange_tick": 0.01,
            "raw_tick": 0.01,
            "display_multiplier": 1.0,
            "tick_value": None,
            "tick_size": 0.01,
            "legacy_tick_size": 0.01,
            "agent_pattern": "AIAgent",
            "distance_bins": DEFAULT_DISTANCE_BINS,
            "bin_labels": DEFAULT_BIN_LABELS,
            "tick_source_url": "",
            "tick_source_note": "Fallback config; no official source configured.",
        }
    return deepcopy(ASSET_CONFIGS[key])


def get_tick_size(asset_name: str) -> float:
    """Backward-compatible raw tick accessor."""
    return float(get_config(asset_name)["raw_tick"])


def get_raw_tick(asset_name: str) -> float:
    return float(get_config(asset_name)["raw_tick"])


def get_exchange_tick(asset_name: str) -> float:
    return float(get_config(asset_name)["exchange_tick"])


def get_legacy_tick_size(asset_name: str) -> float:
    return float(get_config(asset_name).get("legacy_tick_size", get_raw_tick(asset_name)))


def get_tick_metadata(asset_name: str) -> Dict[str, Any]:
    cfg = get_config(asset_name)
    keys = [
        "exchange_tick",
        "raw_tick",
        "display_multiplier",
        "tick_value",
        "legacy_tick_size",
        "tick_source_url",
        "tick_source_note",
    ]
    return {k: cfg.get(k) for k in keys}


def get_agent_pattern(asset_name: str) -> str:
    return str(get_config(asset_name)["agent_pattern"])


def get_distance_bins(asset_name: str) -> Tuple[list, list]:
    cfg = get_config(asset_name)
    return (
        cfg.get("distance_bins", DEFAULT_DISTANCE_BINS),
        cfg.get("bin_labels", DEFAULT_BIN_LABELS),
    )
