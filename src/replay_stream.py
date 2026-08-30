#!/usr/bin/env python3
"""
FraudGuard — Real-Time Transaction Streaming Engine
Reads preprocessed transaction data and streams real-time event payloads.
"""

import os
import sys
import time
import json
import csv
from datetime import datetime

# Color terminal formatting
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "..", "data", "fraudguard_cleaned_amlsim.csv")

def load_cleaned_dataset(filepath):
    if not os.path.exists(filepath):
        print(f"{RED}Error: Preprocessed dataset file not found at {filepath}{RESET}")
        sys.exit(1)
    
    transactions = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(row)
    return transactions

def print_header():
    print(f"\n{CYAN}{BOLD}========================================================================================={RESET}")
    print(f"{CYAN}{BOLD}    FRAUDGUARD — REAL-TIME TRANSACTION STREAM PRODUCER ENGINE                           {RESET}")
    print(f"{CYAN}{BOLD}========================================================================================={RESET}")
    print(f" Dataset: {BOLD}Preprocessed FraudGuard AML Transaction Stream{RESET}")
    print(f" Ingestion Mode: {GREEN}{BOLD}Real-Time Event Stream (500ms Interval){RESET}\n")

def run_replay(interval=0.5, test_mode=False):
    print_header()
    transactions = load_cleaned_dataset(DATA_FILE)
    print(f" Loaded {BOLD}{len(transactions)}{RESET} preprocessed transaction records.\n")
    print(f"{BOLD}Starting Live Transaction Stream... (Press Ctrl+C to stop){RESET}\n")
    
    sent_count = 0
    suspicious_count = 0

    try:
        # Initialize Fraud Router
        try:
            from .router_function import FraudRouter
            router = FraudRouter(model_path="fraud_model.pkl")
            print(f" {GREEN}Fraud Router Initialized.{RESET}")
        except ImportError:
            router = None
            print(f" {YELLOW}Warning: Fraud Router not found. Using ground truth labels.{RESET}")

        while True:
            for row in transactions:
                sent_count += 1
                amount = float(row.get("amount", 0.0))
                txn_type = row.get("txn_type", "CREDIT")
                is_suspicious = int(row.get("is_suspicious", 0)) == 1

                payload = {
                    "transaction_id": row.get("transaction_id", f"tx_{sent_count}"),
                    "source_account": row.get("source_account", "acc_0"),
                    "destination_account": row.get("destination_account", "acc_0"),
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "amount": amount,
                    "txn_type": txn_type,
                    "simulation_step": int(row.get("simulation_step", 1))
                }

                # Evaluate using Module 5 (Decision Router)
                if router:
                    result = router.route_transaction(payload)
                    decision = result["decision"]
                    payload["status"] = decision
                else:
                    decision = "BLOCK" if is_suspicious else "ALLOW"
                    payload["status"] = decision

                if decision == "BLOCK" or decision == "REVIEW_QUEUE":
                    suspicious_count += 1
                    status_tag = f"{RED}{BOLD}[ {decision} ]{RESET}"
                else:
                    status_tag = f"{GREEN}[ ALLOWED ]{RESET}"

                print(f" [{sent_count:04d}] {payload['timestamp']} | {payload['transaction_id']} | Sender: {payload['source_account']} -> Receiver: {payload['destination_account']} | Amt: ${payload['amount']:>8.2f} | Type: {payload['txn_type']:<7} | Status: {status_tag}")

                
                # Write to telemetry file for FraudGuard Frontend
                telemetry_file = os.path.join(SCRIPT_DIR, "live_telemetry.json")
                with open(telemetry_file, "w") as tf:
                    json.dump({
                        "last_event": payload,
                        "sent_count": sent_count,
                        "fraud_count": suspicious_count,
                        "fraud_rate_pct": round((suspicious_count / sent_count) * 100, 1),
                        "tps": round(1 / interval, 1),
                        "updated_at": datetime.now().strftime("%H:%M:%S")
                    }, tf)

                if test_mode and sent_count >= 10:
                    print(f"\n{GREEN}{BOLD}Test mode completed successfully (10 events processed).{RESET}")
                    return

                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Replay stream stopped by user.{RESET}")
        print(f" Total Events Streamed: {sent_count} | Suspicious Events: {suspicious_count}\n")

if __name__ == "__main__":
    test_flag = "--test-mode" in sys.argv
    run_replay(interval=0.5, test_mode=test_flag)
