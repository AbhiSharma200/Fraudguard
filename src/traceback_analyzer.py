"""
Feature 2: Transaction Traceback (Full Audit Chain)
Links every transaction to its complete history chain for that account,
computes 1h/24h velocity windows without double-counting, rolling 5-txn
chain_risk_score, and amount_delta_pct.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

VELOCITY_1HR_SPIKE_THRESHOLD = 5
VELOCITY_SPIKE_POINTS = 25
AMOUNT_SPIKE_PCT_THRESHOLD = 300.0
AMOUNT_SPIKE_POINTS = 20
CHAIN_SCORE_WINDOW_SIZE = 5


def parse_iso_timestamp(ts_str: Optional[Any]) -> datetime:
    if not ts_str:
        return datetime.now(timezone.utc)
    try:
        clean = str(ts_str).strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _extract_record_ts(record: Dict[str, Any]) -> Optional[str]:
    return (
        record.get("timestamp")
        or (record.get("original_payload") or {}).get("timestamp")
        or record.get("quarantine_ts")
    )


def _extract_record_amount(record: Dict[str, Any]) -> float:
    raw = record.get("amount")
    if raw is None and isinstance(record.get("original_payload"), dict):
        raw = record["original_payload"].get("amount")
    return float(raw) if raw is not None else 0.0


class TracebackAnalyzer:
    def __init__(self, db_client: Optional[Any] = None) -> None:
        self.db_client = db_client
        # In-memory fallback index if db_client is not provided
        self._local_history: Dict[str, List[Dict[str, Any]]] = {}

    def _get_account_history(self, account_id: Optional[str], current_tx_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve prior transactions for account_id sorted oldest -> newest,
        explicitly excluding current_tx_id to prevent double-counting.
        """
        if not account_id:
            return []

        records: List[Dict[str, Any]] = []
        if self.db_client and hasattr(self.db_client, "get_account_transactions"):
            records = self.db_client.get_account_transactions(account_id)
        else:
            records = list(self._local_history.get(account_id, []))

        # Deduplicate by transaction_id and exclude current transaction_id
        seen_ids = set()
        filtered = []
        for r in records:
            tid = r.get("transaction_id")
            if current_tx_id and tid == current_tx_id:
                continue
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)
            filtered.append(r)

        filtered.sort(key=lambda r: parse_iso_timestamp(_extract_record_ts(r)))
        return filtered

    def record_in_local_history(self, account_id: Optional[str], tx_record: Dict[str, Any]) -> None:
        if not account_id:
            return
        if account_id not in self._local_history:
            self._local_history[account_id] = []
        tid = tx_record.get("transaction_id")
        if tid and any(x.get("transaction_id") == tid for x in self._local_history[account_id]):
            return
        self._local_history[account_id].append(tx_record)

    def evaluate(
        self,
        tx: Dict[str, Any],
        current_risk_score: Optional[float] = None,
        prior_records: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Computes the `traceback` block and evaluates VELOCITY_SPIKE and AMOUNT_SPIKE flags.
        """
        tx_id = tx.get("transaction_id")
        account_id = tx.get("account_id") or tx.get("source_account") or tx.get("user_id")
        raw_amt = tx.get("amount", 0.0)
        amount = float(raw_amt) if raw_amt is not None else 0.0
        tx_time = parse_iso_timestamp(tx.get("timestamp"))

        if prior_records is not None:
            # Exclude current_tx_id if accidentally present in prior_records
            history = [
                r for r in prior_records
                if not (tx_id and r.get("transaction_id") == tx_id)
            ]
            history.sort(key=lambda r: parse_iso_timestamp(_extract_record_ts(r)))
        else:
            history = self._get_account_history(account_id, current_tx_id=tx_id)

        prior_count = len(history)
        account_tx_count = prior_count + 1

        # Velocity windows: count prior transactions within window + 1 (current txn, counted once)
        one_hr_ago = tx_time - timedelta(hours=1)
        twenty_four_hr_ago = tx_time - timedelta(hours=24)

        prior_1hr = sum(
            1 for r in history
            if one_hr_ago <= parse_iso_timestamp(_extract_record_ts(r)) <= tx_time
        )
        prior_24hr = sum(
            1 for r in history
            if twenty_four_hr_ago <= parse_iso_timestamp(_extract_record_ts(r)) <= tx_time
        )

        velocity_1hr = prior_1hr + 1
        velocity_24hr = prior_24hr + 1

        # Filter out future-skewed records when selecting chronological predecessor
        prior_chronological = [
            r for r in history
            if parse_iso_timestamp(_extract_record_ts(r)) <= tx_time
        ]

        if prior_count == 0:
            prev_tx_id = None
            prev_tx_ts = None
            prev_amount = 0.0
            prev_merchant = ""
            prev_location = ""
            amount_delta_pct = 0.0
            chain_scores = [float(current_risk_score)] if current_risk_score is not None else [0.0]
            chain_risk_score = round(sum(chain_scores) / len(chain_scores), 2)
            last_tx = None
        else:
            last_tx = prior_chronological[-1] if prior_chronological else history[-1]
            orig_payload = last_tx.get("original_payload") if isinstance(last_tx.get("original_payload"), dict) else {}
            prev_tx_id = last_tx.get("transaction_id")
            prev_tx_ts = _extract_record_ts(last_tx)
            prev_amount = _extract_record_amount(last_tx)
            prev_merchant = (
                last_tx.get("merchant")
                or orig_payload.get("merchant")
                or last_tx.get("merchant_category")
                or last_tx.get("destination_account")
                or orig_payload.get("destination_account")
                or ""
            )
            prev_location = (
                last_tx.get("location")
                or (last_tx.get("origin", {}) or {}).get("city")
                or (orig_payload.get("origin", {}) or {}).get("city")
                or last_tx.get("transaction_city")
                or orig_payload.get("transaction_city")
                or ""
            )

            # Compute % change vs previous amount and vs historical average
            delta_prev = ((amount - prev_amount) / prev_amount * 100.0) if prev_amount > 0 else 0.0
            avg_amount = sum(_extract_record_amount(r) for r in history) / prior_count
            delta_avg = ((amount - avg_amount) / avg_amount * 100.0) if avg_amount > 0 else 0.0
            amount_delta_pct = round(max(delta_prev, delta_avg), 2)

            # Rolling average of last 5 scores
            historical_scores = [
                float(r.get("risk_score", r.get("total_risk", 0.0)))
                for r in history
            ]
            if current_risk_score is not None:
                window_scores = (historical_scores + [float(current_risk_score)])[-CHAIN_SCORE_WINDOW_SIZE:]
            else:
                window_scores = historical_scores[-CHAIN_SCORE_WINDOW_SIZE:]
            chain_risk_score = round(sum(window_scores) / len(window_scores), 2) if window_scores else 0.0

        flags: List[str] = []
        risk_points = 0

        if velocity_1hr > VELOCITY_1HR_SPIKE_THRESHOLD:
            flags.append("VELOCITY_SPIKE")
            risk_points += VELOCITY_SPIKE_POINTS

        if amount_delta_pct > AMOUNT_SPIKE_PCT_THRESHOLD:
            flags.append("AMOUNT_SPIKE")
            risk_points += AMOUNT_SPIKE_POINTS

        traceback_block = {
            "account_transaction_count": account_tx_count,
            "previous_transaction_id": prev_tx_id,
            "previous_transaction_ts": prev_tx_ts,
            "previous_amount": round(prev_amount, 2),
            "previous_merchant": prev_merchant,
            "previous_location": prev_location,
            "chain_risk_score": chain_risk_score,
            "velocity_1hr": velocity_1hr,
            "velocity_24hr": velocity_24hr,
            "amount_delta_pct": amount_delta_pct
        }

        return {
            "traceback": traceback_block,
            "flags": flags,
            "risk_points": risk_points,
            "previous_record": last_tx,
            "history_last_5": history[-CHAIN_SCORE_WINDOW_SIZE:]
        }
