"""
Unit Tests for Feature 1: Transaction Origin & Source Tracing
Writes structured JSON test report to test_results/feature_1_{timestamp}.json
"""

import os
import sys
import json
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.origin_tracer import OriginTracer
from src.rule_engine import RuleEngine


def run_feature_1_tests():
    tracer = OriginTracer()
    rule_engine = RuleEngine()
    results = []

    # Test Case 1: VPN IP -> expect ORIGIN_VPN flag + score bump (+20)
    tx_vpn = {
        "transaction_id": "tx_f1_vpn",
        "source_account": "acc_f1_1",
        "amount": 50.0,
        "txn_type": "CREDIT",
        "origin_ip": "198.51.100.50",  # NL VPN IP
        "registered_country": "NL"
    }
    out_vpn = tracer.evaluate(tx_vpn)
    passed_vpn = (
        "ORIGIN_VPN" in out_vpn["flags"]
        and out_vpn["origin"]["is_vpn"] is True
        and out_vpn["risk_points"] == 20
        and out_vpn["force_block"] is False
    )
    results.append({
        "feature": "FEATURE_1_ORIGIN_TRACING",
        "test_case": "VPN IP detection",
        "input": tx_vpn,
        "expected_output": {"flags": ["ORIGIN_VPN"], "risk_points": 20, "force_block": False},
        "actual_output": {
            "flags": out_vpn["flags"],
            "risk_points": out_vpn["risk_points"],
            "force_block": out_vpn["force_block"],
            "origin": out_vpn["origin"]
        },
        "passed": passed_vpn,
        "notes": "VPN IP correctly triggers ORIGIN_VPN and +20 risk score bump."
    })

    # Test Case 2: TOR IP -> expect ORIGIN_TOR flag + BLOCK action
    tx_tor = {
        "transaction_id": "tx_f1_tor",
        "source_account": "acc_f1_2",
        "amount": 40.0,
        "txn_type": "CREDIT",
        "origin_ip": "185.220.101.1",  # DE TOR exit node
        "registered_country": "DE"
    }
    out_tor = tracer.evaluate(tx_tor)
    passed_tor = (
        "ORIGIN_TOR" in out_tor["flags"]
        and out_tor["origin"]["is_tor"] is True
        and out_tor["risk_points"] >= 20
        and out_tor["force_block"] is True
    )
    results.append({
        "feature": "FEATURE_1_ORIGIN_TRACING",
        "test_case": "TOR IP detection + BLOCK action",
        "input": tx_tor,
        "expected_output": {"flags": ["ORIGIN_TOR"], "risk_points": 20, "force_block": True},
        "actual_output": {
            "flags": out_tor["flags"],
            "risk_points": out_tor["risk_points"],
            "force_block": out_tor["force_block"],
            "origin": out_tor["origin"]
        },
        "passed": passed_tor,
        "notes": "TOR exit node triggers ORIGIN_TOR, +20 risk points, and force_block=True."
    })

    # Test Case 3: Mismatched country -> expect GEO_ORIGIN_MISMATCH flag (+10)
    tx_mismatch = {
        "transaction_id": "tx_f1_mismatch",
        "source_account": "acc_f1_3",
        "amount": 75.0,
        "txn_type": "CREDIT",
        "origin_ip": "198.51.100.20",  # GB IP
        "registered_country": "US"
    }
    out_mismatch = tracer.evaluate(tx_mismatch)
    passed_mismatch = (
        "GEO_ORIGIN_MISMATCH" in out_mismatch["flags"]
        and out_mismatch["risk_points"] == 10
        and out_mismatch["force_block"] is False
    )
    results.append({
        "feature": "FEATURE_1_ORIGIN_TRACING",
        "test_case": "Mismatched country detection",
        "input": tx_mismatch,
        "expected_output": {"flags": ["GEO_ORIGIN_MISMATCH"], "risk_points": 10, "force_block": False},
        "actual_output": {
            "flags": out_mismatch["flags"],
            "risk_points": out_mismatch["risk_points"],
            "force_block": out_mismatch["force_block"],
            "origin": out_mismatch["origin"]
        },
        "passed": passed_mismatch,
        "notes": "Cross-border IP (GB vs US registered) triggers GEO_ORIGIN_MISMATCH and +10 risk points."
    })

    # Test Case 4: Clean domestic IP -> no origin flag, no score bump, no regression on base RuleEngine
    tx_clean = {
        "transaction_id": "tx_f1_clean",
        "source_account": "acc_f1_4",
        "amount": 160.0,
        "txn_type": "WIRE",
        "timestamp": "2026-10-01T10:00:00Z",
        "origin_ip": "192.0.2.1",  # US IP
        "registered_country": "US"
    }
    out_clean = tracer.evaluate(tx_clean)
    base_rule = rule_engine.process_transaction(tx_clean)
    passed_clean = (
        out_clean["flags"] == []
        and out_clean["risk_points"] == 0
        and out_clean["force_block"] is False
        and base_rule["rule_score"] == 0.4
        and base_rule["triggered_rules"] == ["CHANNEL_RISK"]
    )
    results.append({
        "feature": "FEATURE_1_ORIGIN_TRACING",
        "test_case": "Clean domestic IP + regression check",
        "input": tx_clean,
        "expected_output": {"flags": [], "risk_points": 0, "base_rule_score": 0.4},
        "actual_output": {
            "flags": out_clean["flags"],
            "risk_points": out_clean["risk_points"],
            "base_rule_score": base_rule["rule_score"],
            "origin": out_clean["origin"]
        },
        "passed": passed_clean,
        "notes": "Clean domestic IP adds 0 risk points and preserves identical base RuleEngine scoring."
    })

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_1_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 1 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    run_feature_1_tests()
