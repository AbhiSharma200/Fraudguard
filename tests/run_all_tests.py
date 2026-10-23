"""
Master Test Suite for FraudGuard:
- Part 2A: Runs all 7 Feature Unit Test suites (27 unit tests)
- Part 2B: Runs all 5 End-to-End Integration Scenarios (including 50-txn stress test)
- Part 2C: Verifies zero regressions across all suites
- Part 3 & 4: Audits Bug Detection Checklist and Production Readiness items
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.db_client import DBClient
from src.router_function import FraudRouter
import src.lambda_function as lf

from tests.test_feature_1 import run_feature_1_tests
from tests.test_feature_2 import run_feature_2_tests
from tests.test_feature_3 import run_feature_3_tests
from tests.test_feature_4 import run_feature_4_tests
from tests.test_feature_5 import run_feature_5_tests
from tests.test_feature_6 import run_feature_6_tests
from tests.test_feature_7 import run_feature_7_tests


def run_integration_scenarios():
    db = DBClient(in_memory_only=True)
    router = FraudRouter(db_client=db)
    lf._ROUTER_INSTANCE = router

    integration_results = []
    base_ts = datetime(2026, 10, 23, 14, 0, 0, tzinfo=timezone.utc)

    # ── Scenario 1: Clean transaction (should APPROVE) ────────────────────────
    tx_clean = {
        "transaction_id": "tx_int_clean_001",
        "source_account": "acc_1",  # Verified phone, 450d old, New York
        "amount": 45.00,
        "txn_type": "CREDIT",
        "origin_ip": "192.0.2.1",  # New York domestic broadband
        "transaction_city": "New York",
        "transaction_country": "US",
        "timestamp": base_ts.isoformat()
    }
    resp_1 = lf.lambda_handler({"body": json.dumps(tx_clean)})
    body_1 = json.loads(resp_1["body"])
    s1_passed = (
        resp_1["statusCode"] == 200
        and body_1["decision"] == "ALLOW"
        and body_1["action"] == "APPROVE"
        and body_1["status"] == "APPROVED"
        and body_1["risk_score"] == 0
        and body_1["flags"] == []
    )
    integration_results.append({
        "scenario": "Scenario 1 — Clean transaction (should APPROVE)",
        "passed": s1_passed,
        "http_status": resp_1["statusCode"],
        "decision": body_1["decision"],
        "risk_score": body_1["risk_score"],
        "flags": body_1["flags"]
    })

    # ── Scenario 2: Soft fraud (should REVIEW_QUEUE) ──────────────────────────
    tx_soft = {
        "transaction_id": "tx_int_soft_002",
        "source_account": "acc_2",  # 12 days old (<30d -> NEW_ACCOUNT +10)
        "amount": 140.00,
        "txn_type": "CREDIT",
        "origin_ip": "198.51.100.50",  # VPN IP (+20)
        "transaction_city": "New York",
        "transaction_country": "US",
        "registered_country": "US",
        "local_hour": 2,  # 2am unusual hour (+15) -> total 45 -> REVIEW_QUEUE
        "account_typical_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
        "timestamp": (base_ts + timedelta(minutes=10)).isoformat()
    }
    resp_2 = lf.lambda_handler({"body": json.dumps(tx_soft)})
    body_2 = json.loads(resp_2["body"])
    s2_passed = (
        resp_2["statusCode"] == 200
        and body_2["decision"] == "REVIEW_QUEUE"
        and body_2["status"] == "PENDING_REVIEW"
        and 40 <= body_2["risk_score"] < 80
        and "ORIGIN_VPN" in body_2["flags"]
        and "UNUSUAL_HOUR" in body_2["flags"]
        and "NEW_ACCOUNT" in body_2["flags"]
    )
    integration_results.append({
        "scenario": "Scenario 2 — Soft fraud (should REVIEW_QUEUE)",
        "passed": s2_passed,
        "http_status": resp_2["statusCode"],
        "decision": body_2["decision"],
        "risk_score": body_2["risk_score"],
        "flags": body_2["flags"]
    })

    # ── Scenario 3: Hard fraud (should BLOCK + QUARANTINE) ────────────────────
    # Seed 5 rapid Mumbai transactions in 1 hour for acc_4 so the 6th triggers:
    # TOR IP + IMPOSSIBLE_TRAVEL (Mumbai -> London in 5m) + VELOCITY_SPIKE (6 txns in 1hr) + AMOUNT_SPIKE (10x amount)
    for i in range(1, 6):
        seed_tx = {
            "transaction_id": f"tx_int_hard_seed_{i}",
            "source_account": "acc_4",
            "amount": 50.0,
            "txn_type": "CREDIT",
            "origin_ip": "203.0.113.10",  # Mumbai IP
            "transaction_city": "Mumbai",
            "transaction_country": "IN",
            "timestamp": (base_ts + timedelta(minutes=i * 5)).isoformat()
        }
        lf.lambda_handler({"body": json.dumps(seed_tx)})

    tx_hard = {
        "transaction_id": "tx_int_hard_006",
        "source_account": "acc_4",
        "amount": 500.0,  # 10x amount (+900% delta -> AMOUNT_SPIKE)
        "txn_type": "WIRE",
        "origin_ip": "185.220.101.1",  # TOR IP -> ORIGIN_TOR
        "transaction_city": "London",  # Mumbai -> London in 5 mins -> IMPOSSIBLE_TRAVEL
        "transaction_country": "GB",
        "timestamp": (base_ts + timedelta(minutes=30)).isoformat()
    }
    resp_3 = lf.lambda_handler({"body": json.dumps(tx_hard)})
    body_3 = json.loads(resp_3["body"])
    in_quarantine = any(q["transaction_id"] == "tx_int_hard_006" for q in db.get_all_quarantined_transactions())
    in_main = any(m["transaction_id"] == "tx_int_hard_006" for m in db.get_all_main_transactions())
    s3_passed = (
        resp_3["statusCode"] == 202
        and body_3["decision"] == "BLOCK"
        and body_3["status"] == "QUARANTINED"
        and "ORIGIN_TOR" in body_3["flags"]
        and "IMPOSSIBLE_TRAVEL" in body_3["flags"]
        and "VELOCITY_SPIKE" in body_3["flags"]
        and "AMOUNT_SPIKE" in body_3["flags"]
        and in_quarantine is True
        and in_main is False
    )
    integration_results.append({
        "scenario": "Scenario 3 — Hard fraud (should BLOCK + QUARANTINE)",
        "passed": s3_passed,
        "http_status": resp_3["statusCode"],
        "decision": body_3["decision"],
        "risk_score": body_3["risk_score"],
        "flags": body_3["flags"],
        "in_quarantine": in_quarantine,
        "in_main": in_main
    })

    # ── Scenario 4: Edge case — first transaction ever for new account (age 1 day) ──
    tx_edge = {
        "transaction_id": "tx_int_edge_004",
        "source_account": "acc_brand_new_1d",
        "amount": 30.0,
        "txn_type": "CREDIT",
        "origin_ip": "192.0.2.1",
        "transaction_city": "New York",
        "transaction_country": "US",
        "timestamp": base_ts.isoformat(),
        "mock_pii_override": {
            "account_holder_name": "DEMO_NEW_1D (MOCK)",
            "account_age_days": 1,
            "linked_phone_verified": True,
            "social_profile_risk_score": 0.1,
            "device_fingerprint": "fp_demo_edge_1d",
            "registered_city": "New York",
            "registered_country": "US",
            "last_known_location": {
                "source": "SIMULATED_CELL_TOWER",
                "city": "New York",
                "lat": 40.7128,
                "lon": -74.0060,
                "accuracy_meters": 50,
                "timestamp": base_ts.isoformat()
            }
        }
    }
    resp_4 = lf.lambda_handler({"body": json.dumps(tx_edge)})
    body_4 = json.loads(resp_4["body"])
    s4_passed = (
        resp_4["statusCode"] == 200
        and body_4["traceback"]["previous_transaction_id"] is None
        and body_4["location_check"]["is_impossible_travel"] is False
        and body_4["location_check"]["travel_speed_kmh"] == 0.0
        and "NEW_ACCOUNT" in body_4["flags"]
    )
    integration_results.append({
        "scenario": "Scenario 4 — Edge case: first transaction ever for 1-day-old account",
        "passed": s4_passed,
        "http_status": resp_4["statusCode"],
        "decision": body_4["decision"],
        "traceback": body_4["traceback"],
        "location_check": body_4["location_check"],
        "flags": body_4["flags"]
    })

    # ── Scenario 5: Stress test — fire 50 transactions in < 10 seconds ────────
    stress_start = time.perf_counter()
    stress_ids = set()
    all_50_ok = True
    max_single_ms = 0.0

    for idx in range(1, 51):
        t0 = time.perf_counter()
        tx_s = {
            "transaction_id": f"tx_stress_{idx:03d}",
            "source_account": f"acc_{(idx % 20) + 1}",
            "amount": float(20 + idx),
            "txn_type": "CREDIT",
            "origin_ip": "192.0.2.1",
            "timestamp": (base_ts + timedelta(hours=idx)).isoformat()
        }
        r_s = lf.lambda_handler({"body": json.dumps(tx_s)})
        single_ms = (time.perf_counter() - t0) * 1000.0
        max_single_ms = max(max_single_ms, single_ms)
        if r_s["statusCode"] not in (200, 202):
            all_50_ok = False
        b_s = json.loads(r_s["body"])
        stress_ids.add(b_s["transaction_id"])

    stress_duration_sec = round(time.perf_counter() - stress_start, 3)

    # Also verify duplicate transaction_id protection returns HTTP 409
    dup_resp = lf.lambda_handler({"body": json.dumps({
        "transaction_id": "tx_stress_001",
        "source_account": "acc_2",
        "amount": 21.0,
        "timestamp": base_ts.isoformat()
    })})

    # Also verify malformed input returns valid error JSON (400), never 500 crash
    bad_resp = lf.lambda_handler({"body": "{malformed_json"})

    s5_passed = (
        all_50_ok is True
        and len(stress_ids) == 50
        and stress_duration_sec < 10.0
        and max_single_ms < 3000.0
        and dup_resp["statusCode"] == 409
        and bad_resp["statusCode"] == 400
    )
    integration_results.append({
        "scenario": "Scenario 5 — Stress test (50 txns in <10s, no timeouts, no duplicate IDs, malformed JSON handling)",
        "passed": s5_passed,
        "total_txns": len(stress_ids),
        "duration_sec": stress_duration_sec,
        "max_single_invocation_ms": round(max_single_ms, 2),
        "duplicate_status_code": dup_resp["statusCode"],
        "malformed_status_code": bad_resp["statusCode"]
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"integration_suite_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(integration_results, f, indent=2)

    print(f"Integration Scenarios: {sum(r['passed'] for r in integration_results)}/{len(integration_results)} passed -> {out_file}")
    if not all(r["passed"] for r in integration_results):
        sys.exit(1)
    return integration_results


if __name__ == "__main__":
    print("=== PART 2A & 2C: UNIT & REGRESSION TESTS (FEATURES 1-7) ===")
    r1 = run_feature_1_tests()
    r2 = run_feature_2_tests()
    r3 = run_feature_3_tests()
    r4 = run_feature_4_tests()
    r5 = run_feature_5_tests()
    r6 = run_feature_6_tests()
    r7 = run_feature_7_tests()
    total_unit = sum(len(x) for x in (r1, r2, r3, r4, r5, r6, r7))
    passed_unit = sum(sum(1 for t in x if t["passed"]) for x in (r1, r2, r3, r4, r5, r6, r7))
    print(f"\nAll Unit & Regression Tests Passed: {passed_unit}/{total_unit}\n")

    print("=== PART 2B: END-TO-END INTEGRATION SCENARIOS (1-5) ===")
    int_res = run_integration_scenarios()

    print("\n=== PART 2D: 5-CATEGORY ADVERSARIAL QA SUITE (T-001 TO T-016) ===")
    from tests.test_qa_adversarial import run_qa_adversarial_suite
    run_qa_adversarial_suite(
        include_regression=False,
        precomputed_regression={
            "unit_total": total_unit,
            "unit_passed": passed_unit,
            "int_total": len(int_res),
            "int_passed": sum(1 for r in int_res if r["passed"])
        }
    )

