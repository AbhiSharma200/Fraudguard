#!/usr/bin/env python3
"""
FraudGuard — Side-by-Side Dataset Comparison Tool (Unprocessed vs Preprocessed)
"""

import os
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(SCRIPT_DIR, "..", "data", "amlsim_tx.csv")
CLEANED_FILE = os.path.join(SCRIPT_DIR, "..", "data", "fraudguard_cleaned_amlsim.csv")

# Color formatting
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def compare():
    print(f"\n{CYAN}{BOLD}========================================================================================={RESET}")
    print(f"{CYAN}{BOLD}          FRAUDGUARD DATASET COMPARISON: UNPROCESSED vs PREPROCESSED                    {RESET}")
    print(f"{CYAN}{BOLD}========================================================================================={RESET}\n")

    raw_data = list(csv.DictReader(open(RAW_FILE, mode="r", encoding="utf-8"))) if os.path.exists(RAW_FILE) else []
    clean_data = list(csv.DictReader(open(CLEANED_FILE, mode="r", encoding="utf-8"))) if os.path.exists(CLEANED_FILE) else []

    print(f"{YELLOW}{BOLD}--- 1. RAW / UNPROCESSED DATASET SAMPLE (data/amlsim_tx.csv) ---{RESET}")
    print(f" Raw Headers: {list(raw_data[0].keys()) if raw_data else 'None'}\n")
    print(f" {'TXN_ID':<8} | {'ACCOUNT_ID':<12} | {'COUNTER_PARTY':<14} | {'TYPE':<7} | {'AMOUNT':<8} | {'START':<6}")
    print(f" -----------------------------------------------------------------------------")
    for r in raw_data[:5]:
        print(f" {r.get('TXN_ID',''):<8} | {r.get('ACCOUNT_ID',''):<12} | {r.get('COUNTER_PARTY_ACCOUNT_NUM',''):<14} | {r.get('TXN_SOURCE_TYPE_CODE',''):<7} | {r.get('TXN_AMOUNT_ORIG',''):<8} | {r.get('start',''):<6}")

    print(f"\n{GREEN}{BOLD}--- 2. PREPROCESSED DATASET SAMPLE (data/fraudguard_cleaned_amlsim.csv) ---{RESET}")
    print(f" Cleaned Headers: {list(clean_data[0].keys()) if clean_data else 'None'}\n")
    print(f" {'transaction_id':<15} | {'source_account':<14} | {'destination_account':<20} | {'txn_type':<7} | {'amount':<8} | {'timestamp':<20} | {'is_suspicious':<13}")
    print(f" --------------------------------------------------------------------------------------------------------------------")
    for c in clean_data[:5]:
        status = f"{RED}1 (SUSPICIOUS){RESET}" if c.get('is_suspicious') == '1' else f"{GREEN}0 (ALLOWED){RESET}"
        print(f" {c.get('transaction_id',''):<15} | {c.get('source_account',''):<14} | {c.get('destination_account',''):<20} | {c.get('txn_type',''):<7} | {c.get('amount',''):<8} | {c.get('timestamp',''):<20} | {status}")

    print(f"\n{BOLD}Key Preprocessing Transformations Applied:{RESET}")
    print(" 1. Formatted transaction IDs with 'tx_fg_' prefix and account IDs with 'acc_' prefix.")
    print(" 2. Converted raw numeric simulation steps into standard ISO-8601 UTC timestamps.")
    print(" 3. Normalized monetary amounts to 2 decimal places.")
    print(" 4. Generated ground-truth risk flags ('is_suspicious') based on high-risk wire/check heuristics.\n")

if __name__ == "__main__":
    compare()
