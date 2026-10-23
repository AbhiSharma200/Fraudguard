"""
Unit & Regression Tests for Feature 3: Time-Span Analysis
Writes structured JSON test report to test_results/feature_3_{timestamp}.json
"""

import os
import sys
import json
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.time_analyzer import TimeSpanAnalyzer
from tests.test_feature_1 import run_feature_1_tests
from tests.test_feature_2 import run_feature_2_tests


def run_feature_3_tests():
    analyzer = TimeSpanAnalyzer()
    results = []

    # Test Case 1: Transaction at 2am local time, account never transacts at night -> UNUSUAL_HOUR flag
    tx_2am = {
        "transaction_id": "tx_f3_2am",
        "source_account": "acc_f3_1",
        "amount": 120.0,
        "timestamp": "2026-10-21T06:00:00Z",  # 02:00 AM EDT in America/New_York (UTC-4)
        "account_typical_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17]
    }
    origin_ny = {"timezone": "America/New_York"}
    out_2am = analyzer.evaluate(tx_2am, origin=origin_ny)
    passed_2am = (
        out_2am["time_analysis"]["transaction_hour"] == 2
        and out_2am["time_analysis"]["is_night_transaction"] is True
        and out_2am["time_analysis"]["hour_anomaly"] is True
        and "UNUSUAL_HOUR" in out_2am["flags"]
    )
    results.append({
        "feature": "FEATURE_3_TIME_SPAN_ANALYSIS",
        "test_case": "Transaction at 2am, account never transacts at night -> UNUSUAL_HOUR",
        "input": tx_2am,
        "expected_output": {"transaction_hour": 2, "is_night_transaction": True, "flags": ["UNUSUAL_HOUR"]},
        "actual_output": {
            "time_analysis": out_2am["time_analysis"],
            "flags": out_2am["flags"],
            "risk_points": out_2am["risk_points"]
        },
        "passed": passed_2am,
        "notes": "2am local transaction outside daytime typical hours triggers UNUSUAL_HOUR (+15 risk)."
    })

    # Test Case 2: Two transactions 90 seconds apart -> RAPID_SUCCESSION flag
    tx_rapid = {
        "transaction_id": "tx_f3_rapid_2",
        "source_account": "acc_f3_2",
        "amount": 80.0,
        "timestamp": "2026-10-21T15:01:30Z"
    }
    prev_ts = "2026-10-21T15:00:00Z"  # 90 seconds = 1.5 mins prior
    out_rapid = analyzer.evaluate(tx_rapid, origin={"timezone": "UTC"}, previous_ts_str=prev_ts)
    passed_rapid = (
        out_rapid["time_analysis"]["time_since_last_txn_mins"] == 1.5
        and "RAPID_SUCCESSION" in out_rapid["flags"]
    )
    results.append({
        "feature": "FEATURE_3_TIME_SPAN_ANALYSIS",
        "test_case": "Two transactions 90 seconds apart -> RAPID_SUCCESSION",
        "input": {"tx": tx_rapid, "previous_ts": prev_ts},
        "expected_output": {"time_since_last_txn_mins": 1.5, "flags": ["RAPID_SUCCESSION"]},
        "actual_output": {
            "time_analysis": out_rapid["time_analysis"],
            "flags": out_rapid["flags"],
            "risk_points": out_rapid["risk_points"]
        },
        "passed": passed_rapid,
        "notes": "90s gap (1.5 mins < 2.0 mins threshold) triggers RAPID_SUCCESSION (+20 risk)."
    })

    # Test Case 3: Weekend transaction for a business account -> log is_weekend=True but no automatic flag
    # 2026-10-24 is a Saturday (day_of_week = 5) at 14:00 UTC
    tx_weekend = {
        "transaction_id": "tx_f3_weekend",
        "source_account": "acc_f3_biz",
        "account_type": "BUSINESS",
        "amount": 200.0,
        "timestamp": "2026-10-24T14:00:00Z",
        "account_typical_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17]
    }
    out_weekend = analyzer.evaluate(tx_weekend, origin={"timezone": "UTC"})
    passed_weekend = (
        out_weekend["time_analysis"]["is_weekend"] is True
        and out_weekend["time_analysis"]["transaction_day_of_week"] == 5
        and out_weekend["flags"] == []
        and out_weekend["risk_points"] == 0
    )
    results.append({
        "feature": "FEATURE_3_TIME_SPAN_ANALYSIS",
        "test_case": "Weekend transaction for business account logs is_weekend without automatic flag",
        "input": tx_weekend,
        "expected_output": {"is_weekend": True, "flags": [], "risk_points": 0},
        "actual_output": {
            "time_analysis": out_weekend["time_analysis"],
            "flags": out_weekend["flags"],
            "risk_points": out_weekend["risk_points"]
        },
        "passed": passed_weekend,
        "notes": "Saturday daytime business transaction records is_weekend=True with no false-positive flag."
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_3_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 3 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    print("--- Running Feature 1 & 2 Regression Checks ---")
    run_feature_1_tests()
    run_feature_2_tests()
    print("--- Running Feature 3 Unit Tests ---")
    run_feature_3_tests()
