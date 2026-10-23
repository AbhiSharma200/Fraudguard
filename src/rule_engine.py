"""
Module 2: Base Business Rule Engine for FraudGuard
Evaluates deterministic transaction rules (Amount Anomaly, Channel Risk, 6h Velocity)
with timezone-aware UTC normalization and safe type coercion.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

try:
    from src.traceback_analyzer import parse_iso_timestamp
except ImportError:
    from traceback_analyzer import parse_iso_timestamp

AMOUNT_ANOMALY_THRESHOLD = 180.00
AMOUNT_ANOMALY_WEIGHT = 0.4
CHANNEL_RISK_TYPES = {"WIRE", "CHECK"}
CHANNEL_RISK_AMOUNT_THRESHOLD = 150.00
CHANNEL_RISK_WEIGHT = 0.4
VELOCITY_WINDOW_HOURS = 6
VELOCITY_MAX_TXNS = 5
VELOCITY_WEIGHT = 0.8


class RuleEngine:
    def __init__(self) -> None:
        # Store recent transactions to calculate velocity.
        # Format: { 'account_id': [timestamp1, timestamp2, ...] }
        self.transaction_history: Dict[str, List[datetime]] = {}

    def process_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a single transaction payload against business rules.
        Returns a dictionary with rule scores and triggered rules.
        """
        transaction_id = tx.get("transaction_id")
        source_account = (
            tx.get("source_account")
            or tx.get("account_id")
            or tx.get("user_id")
            or "unknown"
        )
        txn_type = str(tx.get("txn_type") or "UNKNOWN").upper()
        raw_amt = tx.get("amount", 0.0)
        amount = float(raw_amt) if raw_amt is not None else 0.0
        timestamp_str = tx.get("timestamp")

        triggered_rules: List[str] = []
        rule_score = 0.0

        # Always normalize to timezone-aware UTC datetime to prevent naive/aware comparison errors
        tx_time = parse_iso_timestamp(timestamp_str)

        # Rule 1: Amount Anomaly Rule (amount > 180.00)
        if amount > AMOUNT_ANOMALY_THRESHOLD:
            triggered_rules.append("AMOUNT_ANOMALY")
            rule_score += AMOUNT_ANOMALY_WEIGHT

        # Rule 2: Channel Risk Rule (WIRE/CHECK and amount > 150.00)
        if txn_type in CHANNEL_RISK_TYPES and amount > CHANNEL_RISK_AMOUNT_THRESHOLD:
            triggered_rules.append("CHANNEL_RISK")
            rule_score += CHANNEL_RISK_WEIGHT

        # Rule 3: Velocity Rule (same source_account > 5 attempts in 6 hours)
        if source_account and source_account != "unknown":
            if source_account not in self.transaction_history:
                self.transaction_history[source_account] = []

            # Add current transaction time (timezone-aware UTC)
            self.transaction_history[source_account].append(tx_time)

            # Filter out transactions older than 6 hours (or future-skewed beyond tx_time)
            six_hours_ago = tx_time - timedelta(hours=VELOCITY_WINDOW_HOURS)
            self.transaction_history[source_account] = [
                t for t in self.transaction_history[source_account]
                if six_hours_ago <= t <= tx_time
            ]

            if len(self.transaction_history[source_account]) > VELOCITY_MAX_TXNS:
                triggered_rules.append("HIGH_VELOCITY")
                rule_score += VELOCITY_WEIGHT

        return {
            "transaction_id": transaction_id,
            "rule_score": min(rule_score, 1.0),
            "triggered_rules": triggered_rules
        }


if __name__ == "__main__":
    engine = RuleEngine()
    print(engine.process_transaction({
        "transaction_id": "tx_test_1",
        "source_account": "acc_1",
        "txn_type": "WIRE",
        "amount": 160.00,
        "timestamp": "2023-10-01T10:00:00Z"
    }))
