#!/usr/bin/env python3
"""
FraudGuard — Real-Time Transaction Streaming Engine
Streams preprocessed transactions enriched with scenarios that exercise ALL 7
Fraud Intelligence feature paths (Origin Tracing, Traceback, Time-Span Analysis,
Impossible Travel Location Check, Quarantine Engine, Dashboard Detail, Mock PII Enrichment).
"""

import os
import sys
import time
import json
import csv
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

DATA_FILE = os.path.join(ROOT_DIR, "data", "fraudguard_cleaned_amlsim.csv")

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_curated_demo_scenarios() -> List[Dict[str, Any]]:
    """
    Curated sequence of transactions that systematically exercise all 7 features
    and guarantee APPROVED, PENDING_REVIEW (REVIEW_QUEUE), and QUARANTINED (BLOCK) records.
    """
    base_ts = datetime(2026, 10, 23, 14, 0, 0, tzinfo=timezone.utc)
    return [
        # 1. Clean domestic transaction -> APPROVE (APPROVED)
        {
            "transaction_id": "tx_fg_demo_001",
            "source_account": "acc_1",
            "destination_account": "acc_20",
            "merchant": "WholeFoods Market",
            "merchant_category": "grocery",
            "amount": 42.50,
            "txn_type": "CREDIT",
            "origin_ip": "192.0.2.1",  # New York broadband
            "transaction_city": "New York",
            "transaction_country": "US",
            "timestamp": base_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "simulation_step": 1
        },
        # 2. Soft fraud: VPN IP (+20) + New account <30d acc_2 (+10) + Unusual night hour 2am (+15) -> REVIEW_QUEUE (45 pts)
        {
            "transaction_id": "tx_fg_demo_002",
            "source_account": "acc_2",
            "destination_account": "acc_15",
            "merchant": "LuxuryWatch Co",
            "merchant_category": "jewelry",
            "amount": 135.00,
            "txn_type": "CREDIT",
            "origin_ip": "198.51.100.50",  # Amsterdam VPN
            "transaction_city": "New York",
            "transaction_country": "US",
            "registered_country": "US",
            "local_hour": 2,
            "account_typical_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
            "timestamp": (base_ts + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "simulation_step": 2
        },
        # 3. Hard fraud: TOR Exit Node IP + High Wire Amount -> BLOCK & QUARANTINE
        {
            "transaction_id": "tx_fg_demo_003",
            "source_account": "acc_10",
            "destination_account": "acc_99",
            "merchant": "CryptoVault Exchange",
            "merchant_category": "crypto_exchange",
            "amount": 950.00,
            "txn_type": "WIRE",
            "origin_ip": "185.220.101.1",  # Frankfurt TOR exit node
            "transaction_city": "Frankfurt",
            "transaction_country": "DE",
            "timestamp": (base_ts + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "simulation_step": 3
        },
        # 4. Baseline Mumbai transaction for acc_4 before Impossible Travel
        {
            "transaction_id": "tx_fg_demo_004",
            "source_account": "acc_4",
            "destination_account": "acc_12",
            "merchant": "Mumbai Electronics",
            "merchant_category": "electronics",
            "amount": 60.00,
            "txn_type": "CREDIT",
            "origin_ip": "203.0.113.10",  # Mumbai IP
            "transaction_city": "Mumbai",
            "transaction_country": "IN",
            "timestamp": (base_ts + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "simulation_step": 4
        },
        # 5. Impossible Travel (Mumbai -> London in 1 minute!) + Rapid Succession + PII Mismatch -> BLOCK & QUARANTINE
        {
            "transaction_id": "tx_fg_demo_005",
            "source_account": "acc_4",
            "destination_account": "acc_18",
            "merchant": "London Gold Bullion",
            "merchant_category": "precious_metals",
            "amount": 600.00,  # +900% amount spike vs $60
            "txn_type": "WIRE",
            "origin_ip": "198.51.100.20",  # London IP
            "transaction_city": "London",
            "transaction_country": "GB",
            "timestamp": (base_ts + timedelta(minutes=16)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "simulation_step": 5
        }
    ]


def load_cleaned_dataset(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        return []
    transactions = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(row)
    return transactions


def run_replay(interval: float = 0.2, test_mode: bool = False) -> None:
    try:
        from src.router_function import FraudRouter
    except ImportError:
        from router_function import FraudRouter

    router = FraudRouter(model_path=os.path.join(ROOT_DIR, "fraud_model.pkl"))

    curated = get_curated_demo_scenarios()
    csv_rows = load_cleaned_dataset(DATA_FILE)

    sent_count = 0
    suspicious_count = 0
    ts_suffix = int(time.time())

    # Stream curated 7-feature scenarios first
    for idx, payload in enumerate(curated, start=1):
        sent_count += 1
        tx = dict(payload)
        tx["transaction_id"] = f"{payload['transaction_id']}_{ts_suffix}_{idx}"
        result = router.route_transaction(tx)
        decision = result["decision"]
        if decision in ("BLOCK", "REVIEW_QUEUE"):
            suspicious_count += 1
        _write_telemetry(result, sent_count, suspicious_count, interval)
        print(f" [{sent_count:04d}] {result['timestamp']} | {result['transaction_id']} | Amt: ${result['amount']:>8.2f} | Score: {result['risk_score']:>3d}/100 | Decision: {decision} | Flags: {result['flags']}")
        if test_mode and sent_count >= 5:
            return
        time.sleep(interval)

    # Continue with CSV stream if not in short test mode
    for row in csv_rows[:15]:
        sent_count += 1
        tx = {
            "transaction_id": f"{row.get('transaction_id', 'tx')}_{ts_suffix}_{sent_count}",
            "source_account": row.get("source_account", "acc_1"),
            "destination_account": row.get("destination_account", "acc_2"),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "amount": float(row.get("amount", 50.0)),
            "txn_type": row.get("txn_type", "CREDIT"),
            "simulation_step": int(row.get("simulation_step", 1))
        }
        result = router.route_transaction(tx)
        if result["decision"] in ("BLOCK", "REVIEW_QUEUE"):
            suspicious_count += 1
        _write_telemetry(result, sent_count, suspicious_count, interval)
        if test_mode and sent_count >= 10:
            break
        time.sleep(interval)


def _write_telemetry(last_event: Dict[str, Any], sent_count: int, suspicious_count: int, interval: float) -> None:
    telemetry_file = os.path.join(SCRIPT_DIR, "live_telemetry.json")
    with open(telemetry_file, "w", encoding="utf-8") as tf:
        json.dump({
            "last_event": last_event,
            "sent_count": sent_count,
            "fraud_count": suspicious_count,
            "fraud_rate_pct": round((suspicious_count / max(1, sent_count)) * 100.0, 1),
            "tps": round(1.0 / max(0.05, interval), 1),
            "updated_at": datetime.now(timezone.utc).strftime("%H:%M:%S")
        }, tf, indent=2)


if __name__ == "__main__":
    test_flag = "--test-mode" in sys.argv
    run_replay(interval=0.05 if test_flag else 0.5, test_mode=test_flag)
