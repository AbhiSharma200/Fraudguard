"""
Unit & Regression Tests for Feature 7: PII Enrichment Layer (Simulated — Demo Safe)
Writes structured JSON test report to test_results/feature_7_{timestamp}.json
"""

import os
import sys
import json
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.pii_enricher import PIIEnricher
from tests.test_feature_1 import run_feature_1_tests
from tests.test_feature_2 import run_feature_2_tests
from tests.test_feature_3 import run_feature_3_tests
from tests.test_feature_4 import run_feature_4_tests
from tests.test_feature_5 import run_feature_5_tests
from tests.test_feature_6 import run_feature_6_tests


def run_feature_7_tests():
    enricher = PIIEnricher()
    results = []

    # Test Case 1: Known account (acc_1), location match (New York) -> no PII flags
    tx_match = {
        "transaction_id": "tx_f7_match",
        "source_account": "acc_1",
        "transaction_city": "New York"
    }
    out_match = enricher.evaluate(tx_match)
    passed_match = (
        out_match["pii_enrichment"]["data_source"] == "MOCK_DEMO_DATA"
        and out_match["pii_enrichment"]["enrichment_status"] == "FOUND"
        and out_match["pii_enrichment"]["location_matches_transaction"] is True
        and out_match["flags"] == []
        and out_match["risk_points"] == 0
    )
    results.append({
        "feature": "FEATURE_7_PII_ENRICHMENT",
        "test_case": "Known account, location match -> no PII flags",
        "input": tx_match,
        "expected_output": {"data_source": "MOCK_DEMO_DATA", "flags": [], "risk_points": 0},
        "actual_output": {
            "pii_enrichment": out_match["pii_enrichment"],
            "flags": out_match["flags"],
            "risk_points": out_match["risk_points"]
        },
        "passed": passed_match,
        "notes": "acc_1 (450d old, phone verified, New York) matches transaction city with 0 risk points."
    })

    # Test Case 2: New account (< 30 days, acc_2 is 12 days old) -> NEW_ACCOUNT flag (+10)
    tx_new = {
        "transaction_id": "tx_f7_new",
        "source_account": "acc_2",
        "transaction_city": "New York"
    }
    out_new = enricher.evaluate(tx_new)
    passed_new = (
        out_new["pii_enrichment"]["data_source"] == "MOCK_DEMO_DATA"
        and out_new["pii_enrichment"]["account_age_days"] == 12
        and out_new["flags"] == ["NEW_ACCOUNT"]
        and out_new["risk_points"] == 10
    )
    results.append({
        "feature": "FEATURE_7_PII_ENRICHMENT",
        "test_case": "New account (< 30 days) -> NEW_ACCOUNT flag (+10)",
        "input": tx_new,
        "expected_output": {"flags": ["NEW_ACCOUNT"], "risk_points": 10},
        "actual_output": {
            "pii_enrichment": out_new["pii_enrichment"],
            "flags": out_new["flags"],
            "risk_points": out_new["risk_points"]
        },
        "passed": passed_new,
        "notes": "acc_2 (12 days < 30 days) triggers NEW_ACCOUNT (+10 risk)."
    })

    # Test Case 3: Phone unverified + location mismatch (acc_3: Chicago cell tower, unverified phone, tx in London) -> both flags stack
    tx_stack = {
        "transaction_id": "tx_f7_stack",
        "source_account": "acc_3",
        "transaction_city": "London"
    }
    out_stack = enricher.evaluate(tx_stack)
    passed_stack = (
        out_stack["pii_enrichment"]["data_source"] == "MOCK_DEMO_DATA"
        and "LOCATION_MISMATCH" in out_stack["flags"]
        and "UNVERIFIED_CONTACT" in out_stack["flags"]
        and out_stack["risk_points"] == 20  # 15 + 5
    )
    results.append({
        "feature": "FEATURE_7_PII_ENRICHMENT",
        "test_case": "Phone unverified + location mismatch -> both flags stack (+20)",
        "input": tx_stack,
        "expected_output": {"flags": ["LOCATION_MISMATCH", "UNVERIFIED_CONTACT"], "risk_points": 20},
        "actual_output": {
            "pii_enrichment": out_stack["pii_enrichment"],
            "flags": out_stack["flags"],
            "risk_points": out_stack["risk_points"]
        },
        "passed": passed_stack,
        "notes": "Location mismatch (+15) and unverified phone (+5) stack cleanly to +20 risk points."
    })

    # Test Case 4: Unknown account_id -> gracefully return enrichment_status: NOT_FOUND, continue scoring
    tx_unknown = {
        "transaction_id": "tx_f7_unknown",
        "source_account": "acc_999_nonexistent",
        "transaction_city": "New York"
    }
    out_unk = enricher.evaluate(tx_unknown)
    passed_unk = (
        out_unk["pii_enrichment"]["data_source"] == "MOCK_DEMO_DATA"
        and out_unk["pii_enrichment"]["enrichment_status"] == "NOT_FOUND"
        and out_unk["flags"] == []
        and out_unk["risk_points"] == 0
    )
    results.append({
        "feature": "FEATURE_7_PII_ENRICHMENT",
        "test_case": "Unknown account_id -> gracefully return enrichment_status: NOT_FOUND",
        "input": tx_unknown,
        "expected_output": {"enrichment_status": "NOT_FOUND", "data_source": "MOCK_DEMO_DATA", "flags": []},
        "actual_output": {
            "pii_enrichment": out_unk["pii_enrichment"],
            "flags": out_unk["flags"]
        },
        "passed": passed_unk,
        "notes": "Unknown account returns enrichment_status=NOT_FOUND and data_source=MOCK_DEMO_DATA without crashing."
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_7_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 7 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    print("--- Running Feature 1-6 Regression Checks ---")
    run_feature_1_tests()
    run_feature_2_tests()
    run_feature_3_tests()
    run_feature_4_tests()
    run_feature_5_tests()
    run_feature_6_tests()
    print("--- Running Feature 7 Unit Tests ---")
    run_feature_7_tests()
