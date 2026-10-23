"""
Unit & Regression Tests for Feature 4: Account Holder Location vs Transaction Location
Writes structured JSON test report to test_results/feature_4_{timestamp}.json
"""

import os
import sys
import json
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.location_checker import LocationChecker
from tests.test_feature_1 import run_feature_1_tests
from tests.test_feature_2 import run_feature_2_tests
from tests.test_feature_3 import run_feature_3_tests


def run_feature_4_tests():
    checker = LocationChecker()
    results = []

    # Test Case 1: Same city transaction -> distance < 50km, no flag
    tx_same = {
        "transaction_id": "tx_f4_same",
        "account_registered_city": "New York",
        "account_registered_country": "US",
        "transaction_city": "New York",
        "transaction_country": "US"
    }
    out_same = checker.evaluate(tx_same, previous_record={"location": "New York"}, time_since_last_txn_mins=30.0)
    passed_same = (
        out_same["location_check"]["distance_km"] < 50.0
        and out_same["location_check"]["is_international"] is False
        and out_same["location_check"]["is_impossible_travel"] is False
        and out_same["flags"] == []
    )
    results.append({
        "feature": "FEATURE_4_LOCATION_CHECK",
        "test_case": "Same city transaction -> distance < 50km, no flag",
        "input": tx_same,
        "expected_output": {"distance_km": 0.0, "flags": [], "force_block": False},
        "actual_output": {
            "location_check": out_same["location_check"],
            "flags": out_same["flags"],
            "force_block": out_same["force_block"]
        },
        "passed": passed_same,
        "notes": "Same city (New York -> New York) yields 0.0 km distance and no flags."
    })

    # Test Case 2: Mumbai -> London in 10 minutes -> IMPOSSIBLE_TRAVEL -> BLOCK
    tx_impossible = {
        "transaction_id": "tx_f4_impossible",
        "account_registered_city": "Mumbai",
        "account_registered_country": "IN",
        "transaction_city": "London",
        "transaction_country": "GB"
    }
    prev_mumbai = {"location": "Mumbai", "origin": {"city": "Mumbai", "country": "IN"}}
    out_imp = checker.evaluate(tx_impossible, previous_record=prev_mumbai, time_since_last_txn_mins=10.0)
    passed_imp = (
        out_imp["location_check"]["is_impossible_travel"] is True
        and out_imp["location_check"]["travel_speed_kmh"] > 900.0
        and "IMPOSSIBLE_TRAVEL" in out_imp["flags"]
        and "INTERNATIONAL_TRANSACTION" in out_imp["flags"]
        and out_imp["force_block"] is True
    )
    results.append({
        "feature": "FEATURE_4_LOCATION_CHECK",
        "test_case": "Mumbai -> London in 10 minutes -> IMPOSSIBLE_TRAVEL -> BLOCK",
        "input": {"tx": tx_impossible, "prev": prev_mumbai, "time_since_last_mins": 10.0},
        "expected_output": {"is_impossible_travel": True, "flags": ["IMPOSSIBLE_TRAVEL", "INTERNATIONAL_TRANSACTION"], "force_block": True},
        "actual_output": {
            "location_check": out_imp["location_check"],
            "flags": out_imp["flags"],
            "force_block": out_imp["force_block"]
        },
        "passed": passed_imp,
        "notes": f"Mumbai->London (~7191 km in 10m = {out_imp['location_check']['travel_speed_kmh']} km/h) triggers IMPOSSIBLE_TRAVEL and automatic BLOCK."
    })

    # Test Case 3: First transaction (no previous location) -> skip travel check gracefully
    tx_first = {
        "transaction_id": "tx_f4_first",
        "account_registered_city": "Chicago",
        "account_registered_country": "US",
        "transaction_city": "Chicago",
        "transaction_country": "US"
    }
    out_first = checker.evaluate(tx_first, previous_record=None, time_since_last_txn_mins=None)
    passed_first = (
        out_first["location_check"]["is_impossible_travel"] is False
        and out_first["location_check"]["travel_speed_kmh"] == 0.0
        and out_first["flags"] == []
        and out_first["force_block"] is False
    )
    results.append({
        "feature": "FEATURE_4_LOCATION_CHECK",
        "test_case": "First transaction (no previous location) -> skip travel check gracefully",
        "input": tx_first,
        "expected_output": {"is_impossible_travel": False, "travel_speed_kmh": 0.0, "flags": []},
        "actual_output": {
            "location_check": out_first["location_check"],
            "flags": out_first["flags"]
        },
        "passed": passed_first,
        "notes": "First transaction without prior location skips travel speed calculation gracefully."
    })

    # Test Case 4: Domestic travel ~500km in 8 hours (New York -> Pittsburgh) -> no impossible travel flag
    tx_dom = {
        "transaction_id": "tx_f4_domestic_travel",
        "account_registered_city": "New York",
        "account_registered_country": "US",
        "transaction_city": "Pittsburgh",
        "transaction_country": "US"
    }
    prev_ny = {"location": "New York"}
    out_dom = checker.evaluate(tx_dom, previous_record=prev_ny, time_since_last_txn_mins=480.0)  # 8 hours
    passed_dom = (
        400.0 <= out_dom["location_check"]["distance_km"] <= 600.0
        and out_dom["location_check"]["travel_speed_kmh"] < 900.0
        and out_dom["location_check"]["is_impossible_travel"] is False
        and out_dom["flags"] == []
        and out_dom["force_block"] is False
    )
    results.append({
        "feature": "FEATURE_4_LOCATION_CHECK",
        "test_case": "Domestic travel ~500km in 8 hours -> no impossible travel flag",
        "input": {"tx": tx_dom, "prev": prev_ny, "time_since_last_mins": 480.0},
        "expected_output": {"is_impossible_travel": False, "flags": [], "force_block": False},
        "actual_output": {
            "location_check": out_dom["location_check"],
            "flags": out_dom["flags"]
        },
        "passed": passed_dom,
        "notes": f"New York->Pittsburgh ({out_dom['location_check']['distance_km']} km in 8h = {out_dom['location_check']['travel_speed_kmh']} km/h) passes without IMPOSSIBLE_TRAVEL."
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_4_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 4 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    print("--- Running Feature 1, 2, 3 Regression Checks ---")
    run_feature_1_tests()
    run_feature_2_tests()
    run_feature_3_tests()
    print("--- Running Feature 4 Unit Tests ---")
    run_feature_4_tests()
