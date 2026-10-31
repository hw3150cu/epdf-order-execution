#!/usr/bin/env python3
"""Lightweight validation tests for tick units and contract matching."""

import sys

import pandas as pd

from config import get_exchange_tick, get_raw_tick
from contract_matching import (
    ContractCandidate,
    calculate_buy_sell_distance,
    infer_min_increment_from_values,
    parse_contract_month,
    select_contract,
)


def test_contract_month_parsing():
    assert parse_contract_month("JYZ24") == (2024, 12)
    assert parse_contract_month("HOF22") == (2022, 1)
    assert parse_contract_month("RXU25") == (2025, 9)
    assert parse_contract_month("unknown") == (9999, 99)


def test_distance_inside_and_outside_cases():
    inside = calculate_buy_sell_distance(100.0, 99.0, 101.0, "buy", 0.5)
    assert inside["is_inside"] is True
    assert inside["distance_ticks"] == 0.0

    below_buy = calculate_buy_sell_distance(98.0, 99.0, 101.0, "buy", 0.5)
    assert below_buy["is_inside"] is False
    assert below_buy["reference_point"] == "low"
    assert below_buy["distance_ticks"] == 2.0

    above_sell = calculate_buy_sell_distance(102.0, 99.0, 101.0, "sell", 0.5)
    assert above_sell["is_inside"] is False
    assert above_sell["reference_point"] == "high"
    assert above_sell["distance_ticks"] == 2.0


def candidate(name, inside, distance, volume):
    year, month = parse_contract_month(name)
    return ContractCandidate(
        name=name,
        is_inside=inside,
        distance_price=distance,
        distance_ticks=distance,
        low=99.0,
        high=101.0,
        volume=volume,
        bars_in_window=5,
        maturity_year=year,
        maturity_month=month,
    )


def test_selectors_are_deterministic():
    candidates = [
        candidate("JYZ24", True, 0.0, 100.0),
        candidate("JYU24", True, 0.0, 200.0),
        candidate("JYH25", False, 1.0, 500.0),
    ]
    timestamp = pd.Timestamp("2024-09-10 10:00")
    assert select_contract(candidates, "min_distance", timestamp).name == "JYU24"
    assert select_contract(candidates, "inside_high_volume", timestamp).name == "JYU24"
    assert select_contract(candidates, "calendar_front_month", timestamp).name == "JYU24"
    assert select_contract(candidates, "volume_front_month", timestamp).name == "JYH25"


def test_corrected_tick_config():
    assert get_exchange_tick("JPY - Japanese Yen") == 0.0000005
    assert get_raw_tick("JPY - Japanese Yen") == 0.005
    assert get_exchange_tick("GBP - British Pound") == 0.0001
    assert get_raw_tick("GBP - British Pound") == 0.01
    assert get_exchange_tick("HeatingOil") == 0.0001
    assert get_raw_tick("HeatingOil") == 0.01
    assert get_exchange_tick("EuroStoxx") == 0.5
    assert get_raw_tick("EuroStoxx") == 0.5


def test_infer_min_increment_from_values():
    values = [66.000, 66.005, 66.010, 66.025]
    assert abs(infer_min_increment_from_values(values) - 0.005) < 1e-12


def main():
    tests = [
        test_contract_month_parsing,
        test_distance_inside_and_outside_cases,
        test_selectors_are_deterministic,
        test_corrected_tick_config,
        test_infer_min_increment_from_values,
    ]
    for test in tests:
        test()
        print(f"PASSED {test.__name__}")
    print(f"PASSED {len(tests)}/{len(tests)} validation tests")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)
