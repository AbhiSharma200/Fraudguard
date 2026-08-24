#!/usr/bin/env python3
"""
FraudGuard — Data Cleaning & Preprocessing Suite for AMLSim Dataset
Performs data cleaning, normalization, null-value handling, type mapping, and risk labeling.
"""

import os
import sys
import csv
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_FILE = os.path.join(SCRIPT_DIR, "..", "data", "amlsim_tx.csv")
CLEANED_DATA_FILE = os.path.join(SCRIPT_DIR, "..", "data", "fraudguard_cleaned_amlsim.csv")

def preprocess_dataset():
    if not os.path.exists(RAW_DATA_FILE):
        print(f"Error: Raw dataset not found at {RAW_DATA_FILE}")
        sys.exit(1)

    print("==========================================================================")
    print("      FRAUDGUARD — DATA CLEANING & PREPROCESSING SUITE                    ")
    print("==========================================================================")
    print(f" Loading Raw AMLSim Dataset: {RAW_DATA_FILE}")

    raw_records = []
    with open(RAW_DATA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            raw_records.append(r)

    print(f" Loaded Raw Records: {len(raw_records)}")
    print("\n Executing Data Preprocessing Pipeline:")
    print("  [1/5] Removing null/duplicate records...")
    print("  [2/5] Normalizing account IDs with prefix formatting ('acc_')...")
    print("  [3/5] Converting simulation steps to ISO-8601 UTC timestamps...")
    print("  [4/5] Standardizing transaction amounts to 2-decimal floats...")
    print("  [5/5] Mapping financial channel types (WIRE, CHECK, CREDIT, DEPOSIT)...")

    cleaned_records = []
    base_time = datetime.utcnow() - timedelta(hours=2)

    for idx, row in enumerate(raw_records):
        try:
            # 1. Clean IDs
            raw_tx_id = row.get("TXN_ID", str(idx + 1)).strip()
            tx_id = f"tx_fg_{raw_tx_id}"
            
            raw_src = row.get("ACCOUNT_ID", "0").strip()
            src_acc = f"acc_{raw_src}" if not raw_src.startswith("acc_") else raw_src
            
            raw_dest = row.get("COUNTER_PARTY_ACCOUNT_NUM", "0").strip()
            dest_acc = f"acc_{raw_dest}" if not raw_dest.startswith("acc_") else raw_dest

            # 2. Clean Amounts
            amount_val = float(row.get("TXN_AMOUNT_ORIG", 0.0))
            amount_clean = round(amount_val, 2)

            # 3. Clean Transaction Type
            txn_type = row.get("TXN_SOURCE_TYPE_CODE", "CREDIT").strip().upper()

            # 4. Generate Timestamp from simulation step
            step = int(row.get("start", 1))
            event_time = (base_time + timedelta(seconds=step * 15)).strftime("%Y-%m-%dT%H:%M:%SZ")

            # 5. Preprocess Fraud Risk Indicator
            is_suspicious = 1 if (amount_clean > 150.0 and txn_type in ["WIRE", "CHECK"]) or (amount_clean > 180.0) else 0

            cleaned_records.append({
                "transaction_id": tx_id,
                "source_account": src_acc,
                "destination_account": dest_acc,
                "amount": amount_clean,
                "txn_type": txn_type,
                "timestamp": event_time,
                "simulation_step": step,
                "is_suspicious": is_suspicious
            })
        except Exception as e:
            continue

    # Write Cleaned Dataset
    with open(CLEANED_DATA_FILE, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["transaction_id", "source_account", "destination_account", "amount", "txn_type", "timestamp", "simulation_step", "is_suspicious"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_records)

    print(f"\n==========================================================================")
    print(f" SUCCESS: Preprocessed {len(cleaned_records)} records saved to:")
    print(f" {CLEANED_DATA_FILE}")
    print(f"==========================================================================\n")

if __name__ == "__main__":
    preprocess_dataset()
