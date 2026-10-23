"""
Module 5: FraudGuard Decision Orchestration & Routing Engine
Integrates:
  - Base RuleEngine (Module 2)
  - ML Risk Model (Module 4)
  - Feature 1: OriginTracer
  - Feature 2: TracebackAnalyzer
  - Feature 3: TimeSpanAnalyzer
  - Feature 4: LocationChecker
  - Feature 5: QuarantineManager
  - Feature 7: PIIEnricher
"""

import os
import json
import math
import time
import logging
from typing import Any, Dict, List, Optional

try:
    import joblib
except ImportError:
    joblib = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from src.rule_engine import RuleEngine
    from src.db_client import DBClient
    from src.origin_tracer import OriginTracer
    from src.traceback_analyzer import TracebackAnalyzer
    from src.time_analyzer import TimeSpanAnalyzer
    from src.location_checker import LocationChecker
    from src.quarantine_manager import QuarantineManager
    from src.pii_enricher import PIIEnricher
except ImportError:
    from rule_engine import RuleEngine
    from db_client import DBClient
    from origin_tracer import OriginTracer
    from traceback_analyzer import TracebackAnalyzer
    from time_analyzer import TimeSpanAnalyzer
    from location_checker import LocationChecker
    from quarantine_manager import QuarantineManager
    from pii_enricher import PIIEnricher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCK_SCORE_THRESHOLD = 80
REVIEW_SCORE_THRESHOLD = 40
FORCE_BLOCK_MIN_SCORE = 85

logger = logging.getLogger("fraudguard.router")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


class FraudRouter:
    def __init__(
        self,
        model_path: str = "fraud_model.pkl",
        db_client: Optional[Any] = None,
        in_memory_db: bool = False
    ) -> None:
        self.ml_model = self._load_ml_model(model_path)
        self.rule_engine = RuleEngine()
        self.db = db_client if db_client is not None else DBClient(in_memory_only=in_memory_db)
        self.origin_tracer = OriginTracer()
        self.traceback_analyzer = TracebackAnalyzer(db_client=self.db)
        self.time_analyzer = TimeSpanAnalyzer()
        self.location_checker = LocationChecker()
        self.quarantine_manager = QuarantineManager(db_client=self.db)
        self.pii_enricher = PIIEnricher()

    @staticmethod
    def _load_ml_model(model_path: Optional[str]) -> Optional[Any]:
        if joblib is None or not model_path:
            return None
        candidate_paths = [
            model_path,
            os.path.join(SCRIPT_DIR, os.path.basename(model_path)),
            os.path.join(SCRIPT_DIR, "..", os.path.basename(model_path)),
            os.path.join("/var/task", os.path.basename(model_path)),
        ]
        for path in candidate_paths:
            if path and os.path.exists(path):
                try:
                    return joblib.load(path)
                except Exception:
                    continue
        return None

    def _get_ml_score(self, tx: Dict[str, Any]) -> float:
        if not self.ml_model or pd is None:
            return 0.0
        try:
            df = pd.DataFrame([tx])
            drop_cols = [
                "transaction_id", "source_account", "destination_account",
                "timestamp", "is_suspicious", "origin", "traceback",
                "time_analysis", "location_check", "pii_enrichment",
                "mock_pii_override", "account_typical_hours"
            ]
            df_model = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
            if "amount" not in df_model.columns:
                df_model["amount"] = 0.0
            if "simulation_step" not in df_model.columns:
                df_model["simulation_step"] = 0
            if "txn_type" not in df_model.columns:
                df_model["txn_type"] = "UNKNOWN"

            probs = self.ml_model.predict_proba(df_model)
            if probs.shape[1] > 1:
                val = float(probs[0][1])
                return round(val, 4) if math.isfinite(val) else 0.0
        except Exception:
            pass
        return 0.0

    def route_transaction(
        self,
        tx: Dict[str, Any],
        event_headers: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()

        if not isinstance(tx, dict):
            raise ValueError("Transaction payload must be a JSON object.")

        tx_id = tx.get("transaction_id")
        if not tx_id or (isinstance(tx_id, str) and not tx_id.strip()):
            raise ValueError("Missing required field: transaction_id")

        account_id = (
            tx.get("account_id")
            or tx.get("source_account")
            or tx.get("user_id")
            or "acc_unknown"
        )

        # Strict validation & normalization of amount (reject bool, NaN, Inf, <0; default explicit None to 0.0)
        raw_amount = tx.get("amount", 0.0)
        if isinstance(raw_amount, bool):
            raise ValueError("Transaction amount must be a finite non-negative number.")
        if raw_amount is None:
            amount = 0.0
        else:
            try:
                amount = float(raw_amount)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid transaction amount: {raw_amount}") from exc

        if not math.isfinite(amount) or amount < 0.0:
            raise ValueError("Transaction amount must be a finite non-negative number.")

        # Normalized copy of transaction for downstream analyzers
        tx_norm = dict(tx)
        tx_norm["amount"] = amount
        tx_norm["account_id"] = str(account_id)
        if not tx_norm.get("source_account"):
            tx_norm["source_account"] = str(account_id)

        # 1. Base Rule Engine (Module 2)
        rule_result = self.rule_engine.process_transaction(tx_norm)
        base_rule_score = float(rule_result["rule_score"])
        base_rule_points = int(round(base_rule_score * 100))
        all_flags: List[str] = list(rule_result["triggered_rules"])

        # 2. Feature 7: Simulated PII Enrichment (lookup profile first so registered country/city are known)
        prelim_origin = self.origin_tracer.lookup_ip(
            self.origin_tracer.extract_ip(tx_norm, event_headers=event_headers),
            pre_populated_origin=tx_norm.get("origin") if isinstance(tx_norm.get("origin"), dict) else None
        )
        f7_res = self.pii_enricher.evaluate(tx_norm, origin=prelim_origin)
        pii_profile = f7_res["profile"]
        reg_country = (
            tx_norm.get("registered_country")
            or tx_norm.get("account_registered_country")
            or (pii_profile or {}).get("registered_country")
        )

        # 3. Feature 1: Origin & Source Tracing
        f1_res = self.origin_tracer.evaluate(
            tx_norm,
            event_headers=event_headers,
            registered_country=reg_country
        )
        origin_block = f1_res["origin"]

        # Re-evaluate Feature 7 with finalized origin_block
        f7_res = self.pii_enricher.evaluate(tx_norm, origin=origin_block)
        pii_block = f7_res["pii_enrichment"]

        # 4. Feature 2: Transaction Traceback (Full Audit Chain)
        f2_prelim = self.traceback_analyzer.evaluate(tx_norm, current_risk_score=None)
        prev_record = f2_prelim["previous_record"]
        prior_history = f2_prelim["history_last_5"]

        # 5. Feature 3: Time-Span Analysis
        f3_res = self.time_analyzer.evaluate(
            tx_norm,
            origin=origin_block,
            prior_records=prior_history,
            previous_ts_str=f2_prelim["traceback"]["previous_transaction_ts"]
        )
        time_block = f3_res["time_analysis"]

        # 6. Feature 4: Account Holder Location vs Transaction Location
        f4_res = self.location_checker.evaluate(
            tx_norm,
            origin=origin_block,
            previous_record=prev_record,
            time_since_last_txn_mins=time_block["time_since_last_txn_mins"],
            pii_profile=pii_profile
        )
        location_block = f4_res["location_check"]

        # Collect flags in deterministic order without duplicates
        for flag_list in (f1_res["flags"], f2_prelim["flags"], f3_res["flags"], f4_res["flags"], f7_res["flags"]):
            for fl in flag_list:
                if fl not in all_flags:
                    all_flags.append(fl)

        # Compute composite risk score (strict integer 0..100)
        enrichment_points = (
            f1_res["risk_points"]
            + f2_prelim["risk_points"]
            + f3_res["risk_points"]
            + f4_res["risk_points"]
            + f7_res["risk_points"]
        )
        combined_rule_points = int(max(0, min(100, round(base_rule_points + enrichment_points))))
        effective_rule_score = round(combined_rule_points / 100.0, 2)

        # ML telemetry score (recorded for analytics; deterministic rule points govern threshold routing)
        ml_score = self._get_ml_score(tx_norm)

        force_block = bool(f1_res["force_block"] or f4_res["force_block"])
        if force_block:
            risk_score_int = int(max(FORCE_BLOCK_MIN_SCORE, min(100, combined_rule_points)))
        else:
            risk_score_int = int(max(0, min(100, combined_rule_points)))

        total_risk = round(risk_score_int / 100.0, 2)

        # Finalize Feature 2 chain_risk_score with current risk_score_int
        f2_final = self.traceback_analyzer.evaluate(tx_norm, current_risk_score=float(risk_score_int))
        traceback_block = f2_final["traceback"]

        # Decision routing
        if force_block or risk_score_int >= BLOCK_SCORE_THRESHOLD:
            decision = "BLOCK"
            action = "BLOCK"
            status_label = "QUARANTINED"
            http_status = 202
        elif risk_score_int >= REVIEW_SCORE_THRESHOLD:
            decision = "REVIEW_QUEUE"
            action = "REVIEW_QUEUE"
            status_label = "PENDING_REVIEW"
            http_status = 200
        else:
            decision = "ALLOW"
            action = "APPROVE"
            status_label = "APPROVED"
            http_status = 200

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        audit_record: Dict[str, Any] = {
            "transaction_id": str(tx_id),
            "account_id": str(account_id),
            "source_account": str(tx_norm.get("source_account") or account_id),
            "destination_account": tx_norm.get("destination_account") or "acc_merchant",
            "timestamp": tx_norm.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "amount": amount,
            "txn_type": str(tx_norm.get("txn_type") or "CREDIT").upper(),
            "merchant": tx_norm.get("merchant") or tx_norm.get("destination_account") or "General Merchant",
            "merchant_category": tx_norm.get("merchant_category") or tx_norm.get("txn_type") or "retail",
            "transaction_city": location_block["transaction_city"],
            "transaction_country": location_block["transaction_country"],
            "rule_score": effective_rule_score,
            "ml_score": ml_score,
            "total_risk": total_risk,
            "risk_score": int(risk_score_int),
            "decision": decision,
            "action": action,
            "status": status_label,
            "http_status": http_status,
            "triggered_rules": all_flags,
            "flags": all_flags,
            "origin": origin_block,
            "traceback": traceback_block,
            "time_analysis": time_block,
            "location_check": location_block,
            "pii_enrichment": pii_block,
            "execution_ms": elapsed_ms
        }

        # Feature 5: Persist to Quarantine Table ONLY if BLOCK, else Main Table ONLY
        if decision == "BLOCK":
            q_out = self.quarantine_manager.quarantine_transaction(
                tx=audit_record,
                reason_codes=all_flags,
                risk_score=risk_score_int
            )
            audit_record["quarantine_ts"] = q_out["quarantine_record"]["quarantine_ts"]
            audit_record["auto_release_after"] = q_out["quarantine_record"]["auto_release_after"]
        else:
            self.db.log_transaction(audit_record)

        # Structured CloudWatch JSON log satisfying both {"event": "SCORE", "txn_id": ..., "score": ...} and extended fields
        logger.info(json.dumps({
            "event": "SCORE",
            "txn_id": audit_record["transaction_id"],
            "score": int(risk_score_int),
            "transaction_id": audit_record["transaction_id"],
            "account_id": audit_record["account_id"],
            "risk_score": int(risk_score_int),
            "decision": decision,
            "status": status_label,
            "flags": all_flags,
            "execution_ms": elapsed_ms
        }))

        return audit_record


if __name__ == "__main__":
    router = FraudRouter(in_memory_db=True)
    test_tx = {
        "transaction_id": "tx_test_router_1",
        "source_account": "acc_1",
        "destination_account": "acc_2",
        "txn_type": "WIRE",
        "amount": 250.00,
        "timestamp": "2026-10-23T14:00:00Z",
        "simulation_step": 1
    }
    res = router.route_transaction(test_tx)
    print(json.dumps(res, indent=2))
