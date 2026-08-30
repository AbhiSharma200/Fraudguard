from datetime import datetime, timedelta

class RuleEngine:
    def __init__(self):
        # Store recent transactions to calculate velocity. 
        # Format: { 'account_id': [timestamp1, timestamp2, ...] }
        self.transaction_history = {}

    def process_transaction(self, tx):
        """
        Evaluates a single transaction payload against business rules.
        Returns a dictionary with rule scores and triggered rules.
        """
        transaction_id = tx.get("transaction_id")
        source_account = tx.get("source_account")
        txn_type = tx.get("txn_type")
        amount = tx.get("amount", 0.0)
        timestamp_str = tx.get("timestamp")

        triggered_rules = []
        rule_score = 0.0

        if timestamp_str:
            tx_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            tx_time = datetime.utcnow()

        # Rule 1: Amount Anomaly Rule (amount > 180.00)
        if amount > 180.00:
            triggered_rules.append("AMOUNT_ANOMALY")
            rule_score += 0.4

        # Rule 2: Channel Risk Rule (WIRE/CHECK and amount > 150.00)
        if txn_type in ["WIRE", "CHECK"] and amount > 150.00:
            triggered_rules.append("CHANNEL_RISK")
            rule_score += 0.4

        # Rule 3: Velocity Rule (same source_account > 5 attempts in 6 hours)
        if source_account:
            if source_account not in self.transaction_history:
                self.transaction_history[source_account] = []
            
            # Add current transaction time
            self.transaction_history[source_account].append(tx_time)

            # Filter out transactions older than 6 hours
            six_hours_ago = tx_time - timedelta(hours=6)
            self.transaction_history[source_account] = [
                t for t in self.transaction_history[source_account]
                if t >= six_hours_ago
            ]

            if len(self.transaction_history[source_account]) > 5:
                triggered_rules.append("HIGH_VELOCITY")
                rule_score += 0.8

        return {
            "transaction_id": transaction_id,
            "rule_score": min(rule_score, 1.0),
            "triggered_rules": triggered_rules
        }

if __name__ == "__main__":
    engine = RuleEngine()
    
    # Test cases
    print(engine.process_transaction({
        "transaction_id": "tx_test_1",
        "source_account": "acc_1",
        "txn_type": "WIRE",
        "amount": 160.00,
        "timestamp": "2023-10-01T10:00:00Z"
    }))
