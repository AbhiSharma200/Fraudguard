import joblib
import pandas as pd
from .rule_engine import RuleEngine
from .db_client import DBClient
import os

class FraudRouter:
    def __init__(self, model_path="fraud_model.pkl"):
        # Load ML model
        if os.path.exists(model_path):
            self.ml_model = joblib.load(model_path)
        elif os.path.exists(os.path.join("..", model_path)):
            self.ml_model = joblib.load(os.path.join("..", model_path))
        else:
            self.ml_model = None
            print("Warning: ML model not found. Using Rule Engine only.")

        # Initialize rule engine and DB client
        self.rule_engine = RuleEngine()
        self.db = DBClient()

    def _get_ml_score(self, tx):
        if not self.ml_model:
            return 0.0
            
        # Format for model pipeline
        df = pd.DataFrame([tx])
        
        # Ensure we drop columns the pipeline wasn't trained on
        drop_cols = ["transaction_id", "source_account", "destination_account", "timestamp", "is_suspicious"]
        df_model = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
        
        # Ensure required cols are present
        if 'amount' not in df_model.columns: df_model['amount'] = 0.0
        if 'simulation_step' not in df_model.columns: df_model['simulation_step'] = 0
        if 'txn_type' not in df_model.columns: df_model['txn_type'] = 'UNKNOWN'

        # Predict probability of class 1
        probs = self.ml_model.predict_proba(df_model)
        if probs.shape[1] > 1:
            return float(probs[0][1])
        return 0.0

    def route_transaction(self, tx):
        # 1. Get Rule Score
        rule_result = self.rule_engine.process_transaction(tx)
        rule_score = rule_result["rule_score"]
        
        # 2. Get ML Risk Score
        ml_score = self._get_ml_score(tx)

        # 3. Decision Logic
        # Combine scores or use thresholds
        total_risk = max(rule_score, ml_score)
        
        if total_risk >= 0.8:
            decision = "BLOCK"
        elif total_risk >= 0.4:
            decision = "REVIEW_QUEUE"
        else:
            decision = "ALLOW"

        # 4. Prepare audit log
        audit_record = {
            "transaction_id": tx.get("transaction_id"),
            "amount": tx.get("amount"),
            "rule_score": rule_score,
            "ml_score": ml_score,
            "total_risk": total_risk,
            "decision": decision,
            "triggered_rules": rule_result["triggered_rules"]
        }

        # 5. Persist to DB
        self.db.log_transaction(audit_record)

        return audit_record

if __name__ == "__main__":
    router = FraudRouter()
    
    test_tx = {
        "transaction_id": "tx_test_router_1",
        "source_account": "acc_1",
        "destination_account": "acc_2",
        "txn_type": "WIRE",
        "amount": 250.00,
        "timestamp": "2023-10-01T10:00:00Z",
        "simulation_step": 1
    }
    
    result = router.route_transaction(test_tx)
    print("Routing result:")
    print(result)
