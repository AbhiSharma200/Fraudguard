"""
Unit & Regression Tests for Feature 5: Anomaly Block & Quarantine System
Writes structured JSON test report to test_results/feature_5_{timestamp}.json
"""

import os
import sys
import json
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.db_client import DBClient
from src.quarantine_manager import QuarantineManager
from tests.test_feature_1 import run_feature_1_tests
from tests.test_feature_2 import run_feature_2_tests
from tests.test_feature_3 import run_feature_3_tests
from tests.test_feature_4 import run_feature_4_tests


def run_feature_5_tests():
    db = DBClient(in_memory_only=True)
    qm = QuarantineManager(db_client=db, api_key="test-secret-key")
    results = []

    # Test Case 1: BLOCK decision -> verify record appears in quarantine table, NOT main table, HTTP 202
    tx_block = {
        "transaction_id": "tx_f5_block_1",
        "source_account": "acc_f5_1",
        "amount": 9500.0,
        "timestamp": "2026-10-23T12:00:00Z"
    }
    q_res = qm.quarantine_transaction(
        tx=tx_block,
        reason_codes=["ORIGIN_TOR", "IMPOSSIBLE_TRAVEL"],
        risk_score=95
    )
    in_quarantine = any(r["transaction_id"] == "tx_f5_block_1" for r in db.get_all_quarantined_transactions())
    in_main = any(r["transaction_id"] == "tx_f5_block_1" for r in db.get_all_main_transactions())
    passed_block = (
        q_res["http_status"] == 202
        and in_quarantine is True
        and in_main is False
        and q_res["quarantine_record"]["status"] == "QUARANTINED"
    )
    results.append({
        "feature": "FEATURE_5_QUARANTINE_SYSTEM",
        "test_case": "BLOCK decision -> in quarantine table, NOT main table, HTTP 202",
        "input": tx_block,
        "expected_output": {"http_status": 202, "in_quarantine": True, "in_main": False},
        "actual_output": {
            "http_status": q_res["http_status"],
            "in_quarantine": in_quarantine,
            "in_main": in_main,
            "quarantine_record": q_res["quarantine_record"]
        },
        "passed": passed_block,
        "notes": "BLOCK transaction is written exclusively to fraud-quarantine and returns HTTP 202."
    })

    # Test Case 2: APPROVE decision -> verify record in main table, NOT quarantine
    tx_approve = {
        "transaction_id": "tx_f5_approve_1",
        "source_account": "acc_f5_2",
        "amount": 25.0,
        "decision": "APPROVE",
        "status": "APPROVED",
        "timestamp": "2026-10-23T12:05:00Z"
    }
    db.log_transaction(tx_approve)
    app_in_main = any(r["transaction_id"] == "tx_f5_approve_1" for r in db.get_all_main_transactions())
    app_in_quar = any(r["transaction_id"] == "tx_f5_approve_1" for r in db.get_all_quarantined_transactions())
    passed_approve = app_in_main is True and app_in_quar is False
    results.append({
        "feature": "FEATURE_5_QUARANTINE_SYSTEM",
        "test_case": "APPROVE decision -> in main table, NOT quarantine",
        "input": tx_approve,
        "expected_output": {"in_main": True, "in_quarantine": False},
        "actual_output": {"in_main": app_in_main, "in_quarantine": app_in_quar},
        "passed": passed_approve,
        "notes": "APPROVE transaction is stored in main table only."
    })

    # Test Case 3: Release API call -> verify auth check + status changes from QUARANTINED to RELEASED
    unauth_res = qm.release_transaction("tx_f5_block_1", analyst_notes="Attempt without key", auth_token=None)
    auth_res = qm.release_transaction(
        "tx_f5_block_1",
        analyst_notes="Verified legitimate travel with cardholder",
        auth_token="test-secret-key"
    )
    passed_release = (
        unauth_res["http_status"] == 401
        and auth_res["http_status"] == 200
        and auth_res["status"] == "RELEASED"
        and auth_res["record"]["analyst_notes"] == "Verified legitimate travel with cardholder"
    )
    results.append({
        "feature": "FEATURE_5_QUARANTINE_SYSTEM",
        "test_case": "Release API call changes status from QUARANTINED to RELEASED (with auth verification)",
        "input": {"transaction_id": "tx_f5_block_1", "analyst_notes": "Verified legitimate travel with cardholder"},
        "expected_output": {"unauth_http_status": 401, "auth_http_status": 200, "status": "RELEASED"},
        "actual_output": {"unauth_response": unauth_res, "auth_response": auth_res},
        "passed": passed_release,
        "notes": "Unauthenticated release rejected with 401; authenticated release updates status to RELEASED."
    })

    # Test Case 4: Quarantine count alarm -> mock insert 101 records, verify CloudWatch metric fires
    last_metric = None
    for idx in range(1, 102):
        res_i = qm.quarantine_transaction(
            tx={
                "transaction_id": f"tx_f5_wave_{idx}",
                "source_account": f"acc_wave_{idx}",
                "amount": 500.0,
                "timestamp": "2026-10-23T13:00:00Z"
            },
            reason_codes=["ORIGIN_TOR"],
            risk_score=90
        )
        last_metric = res_i["cloudwatch_metric"]

    passed_alarm = (
        last_metric is not None
        and last_metric["value"] == 101
        and last_metric["alarm_fired"] is True
        and last_metric["alarm_state"] == "ALARM"
    )
    results.append({
        "feature": "FEATURE_5_QUARANTINE_SYSTEM",
        "test_case": "Quarantine count alarm -> mock insert 101 records, verify CloudWatch metric fires",
        "input": {"inserted_quarantined_records": 101, "threshold": 100},
        "expected_output": {"value": 101, "alarm_fired": True, "alarm_state": "ALARM"},
        "actual_output": last_metric,
        "passed": passed_alarm,
        "notes": "101 active quarantined transactions exceed threshold 100 and fire CloudWatch alarm."
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_5_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 5 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    print("--- Running Feature 1-4 Regression Checks ---")
    run_feature_1_tests()
    run_feature_2_tests()
    run_feature_3_tests()
    run_feature_4_tests()
    print("--- Running Feature 5 Unit Tests ---")
    run_feature_5_tests()
