"""
Unit & Regression Tests for Feature 2: Transaction Traceback (Full Audit Chain)
Writes structured JSON test report to test_results/feature_2_{timestamp}.json
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.traceback_analyzer import TracebackAnalyzer
from tests.test_feature_1 import run_feature_1_tests


def run_feature_2_tests():
    analyzer = TracebackAnalyzer()
    results = []
    base_time = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)

    # Test Case 1: 6 transactions in 1 hour for same account -> VELOCITY_SPIKE
    acct_vel = "acc_f2_vel"
    last_out = None
    for i in range(1, 7):
        tx = {
            "transaction_id": f"tx_vel_{i}",
            "source_account": acct_vel,
            "amount": 50.0,
            "timestamp": (base_time + timedelta(minutes=i * 5)).isoformat(),
            "merchant": "Amazon",
            "location": "New York"
        }
        last_out = analyzer.evaluate(tx, current_risk_score=10.0)
        tx_stored = dict(tx)
        tx_stored["risk_score"] = 10.0
        analyzer.record_in_local_history(acct_vel, tx_stored)

    # Also verify no double-counting if evaluate is called again for the 6th transaction
    re_eval_6th = analyzer.evaluate({
        "transaction_id": "tx_vel_6",
        "source_account": acct_vel,
        "amount": 50.0,
        "timestamp": (base_time + timedelta(minutes=30)).isoformat()
    }, current_risk_score=10.0)

    passed_vel = (
        "VELOCITY_SPIKE" in last_out["flags"]
        and last_out["traceback"]["velocity_1hr"] == 6
        and re_eval_6th["traceback"]["velocity_1hr"] == 6  # Not 7 (no double counting)
    )
    results.append({
        "feature": "FEATURE_2_TRANSACTION_TRACEBACK",
        "test_case": "6 transactions in 1 hour -> VELOCITY_SPIKE (no double counting)",
        "input": {"account": acct_vel, "txn_count": 6, "window_mins": 30},
        "expected_output": {"flags": ["VELOCITY_SPIKE"], "velocity_1hr": 6},
        "actual_output": {
            "flags": last_out["flags"],
            "traceback": last_out["traceback"],
            "re_eval_velocity_1hr": re_eval_6th["traceback"]["velocity_1hr"]
        },
        "passed": passed_vel,
        "notes": "6th transaction in 1h window raises VELOCITY_SPIKE and avoids double-counting current transaction."
    })

    # Test Case 2: Transaction 5x the account's average amount -> AMOUNT_SPIKE
    acct_amt = "acc_f2_amt"
    for i in range(1, 4):
        analyzer.record_in_local_history(acct_amt, {
            "transaction_id": f"tx_amt_{i}",
            "source_account": acct_amt,
            "amount": 100.0,
            "timestamp": (base_time + timedelta(hours=i)).isoformat(),
            "risk_score": 15.0,
            "merchant": "Target",
            "location": "Chicago"
        })
    tx_spike = {
        "transaction_id": "tx_amt_4",
        "source_account": acct_amt,
        "amount": 500.0,  # 5x average (400% increase > 300%)
        "timestamp": (base_time + timedelta(hours=5)).isoformat(),
        "merchant": "BestBuy",
        "location": "Chicago"
    }
    out_spike = analyzer.evaluate(tx_spike, current_risk_score=35.0)
    passed_spike = (
        "AMOUNT_SPIKE" in out_spike["flags"]
        and out_spike["traceback"]["amount_delta_pct"] == 400.0
    )
    results.append({
        "feature": "FEATURE_2_TRANSACTION_TRACEBACK",
        "test_case": "Transaction 5x account average amount -> AMOUNT_SPIKE",
        "input": tx_spike,
        "expected_output": {"flags": ["AMOUNT_SPIKE"], "amount_delta_pct": 400.0},
        "actual_output": {
            "flags": out_spike["flags"],
            "traceback": out_spike["traceback"]
        },
        "passed": passed_spike,
        "notes": "5x amount ($500 vs $100 baseline = +400% delta) triggers AMOUNT_SPIKE."
    })

    # Test Case 3: First-ever transaction for an account -> gracefully handle null previous_transaction_id
    tx_first = {
        "transaction_id": "tx_first_1",
        "source_account": "acc_f2_brand_new",
        "amount": 45.0,
        "timestamp": base_time.isoformat()
    }
    out_first = analyzer.evaluate(tx_first, current_risk_score=5.0)
    passed_first = (
        out_first["traceback"]["previous_transaction_id"] is None
        and out_first["traceback"]["previous_transaction_ts"] is None
        and out_first["traceback"]["account_transaction_count"] == 1
        and out_first["traceback"]["velocity_1hr"] == 1
        and out_first["flags"] == []
    )
    results.append({
        "feature": "FEATURE_2_TRANSACTION_TRACEBACK",
        "test_case": "First-ever transaction handles null previous_transaction_id",
        "input": tx_first,
        "expected_output": {"previous_transaction_id": None, "account_transaction_count": 1, "flags": []},
        "actual_output": out_first["traceback"],
        "passed": passed_first,
        "notes": "First transaction cleanly sets previous_transaction_id=None with count=1."
    })

    # Test Case 4: Chain of 10 transactions -> verify rolling chain_risk_score accuracy (last 5 scores)
    acct_chain = "acc_f2_chain"
    scores = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    out_chain = None
    for idx, sc in enumerate(scores, start=1):
        tx_c = {
            "transaction_id": f"tx_chain_{idx}",
            "source_account": acct_chain,
            "amount": 50.0,
            "timestamp": (base_time + timedelta(hours=idx * 2)).isoformat()
        }
        out_chain = analyzer.evaluate(tx_c, current_risk_score=sc)
        analyzer.record_in_local_history(acct_chain, {
            "transaction_id": tx_c["transaction_id"],
            "source_account": acct_chain,
            "amount": 50.0,
            "timestamp": tx_c["timestamp"],
            "risk_score": sc
        })

    # Last 5 scores are [60, 70, 80, 90, 100] -> average = 80.0
    expected_rolling_avg = 80.0
    passed_chain = (
        out_chain["traceback"]["account_transaction_count"] == 10
        and out_chain["traceback"]["chain_risk_score"] == expected_rolling_avg
        and out_chain["traceback"]["previous_transaction_id"] == "tx_chain_9"
    )
    results.append({
        "feature": "FEATURE_2_TRANSACTION_TRACEBACK",
        "test_case": "Chain of 10 transactions rolling chain_risk_score accuracy",
        "input": {"account": acct_chain, "scores": scores},
        "expected_output": {"account_transaction_count": 10, "chain_risk_score": 80.0, "previous_transaction_id": "tx_chain_9"},
        "actual_output": out_chain["traceback"],
        "passed": passed_chain,
        "notes": "Rolling average of last 5 scores [60, 70, 80, 90, 100] equals 80.0."
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_2_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 2 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    print("--- Running Feature 1 Regression Check ---")
    run_feature_1_tests()
    print("--- Running Feature 2 Unit Tests ---")
    run_feature_2_tests()
