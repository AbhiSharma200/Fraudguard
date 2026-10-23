"""
Feature 3: Time-Span Analysis
Detects temporal anomalies (unusual night hours vs account's typical hours,
weekend activity logging, and rapid-succession transactions < 2 minutes apart).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from src.traceback_analyzer import parse_iso_timestamp
except ImportError:
    from traceback_analyzer import parse_iso_timestamp

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# Deterministic timezone offset fallback (hours from UTC) for Windows environments without tzdata
TZ_OFFSET_HOURS = {
    "UTC": 0.0,
    "Etc/UTC": 0.0,
    "Europe/London": 0.0,
    "Europe/Amsterdam": 1.0,
    "Europe/Berlin": 1.0,
    "Europe/Zurich": 1.0,
    "Europe/Bucharest": 2.0,
    "Asia/Kolkata": 5.5,
    "Asia/Singapore": 8.0,
    "America/New_York": -5.0,
    "America/Chicago": -6.0,
    "America/Los_Angeles": -8.0,
}

DEFAULT_TYPICAL_HOURS = list(range(8, 21))  # 08:00 to 20:00 local time
NIGHT_HOURS = {23, 0, 1, 2, 3, 4, 5}
RAPID_SUCCESSION_THRESHOLD_MINS = 2.0
UNUSUAL_HOUR_POINTS = 15
RAPID_SUCCESSION_POINTS = 20


def to_local_datetime(utc_dt: datetime, tz_name: str = "UTC") -> datetime:
    if not tz_name:
        tz_name = "UTC"
    if ZoneInfo is not None:
        try:
            return utc_dt.astimezone(ZoneInfo(tz_name))
        except Exception:
            pass
    offset_hrs = TZ_OFFSET_HOURS.get(tz_name, 0.0)
    tz_obj = timezone(timedelta(hours=offset_hrs))
    return utc_dt.astimezone(tz_obj)


class TimeSpanAnalyzer:
    def evaluate(
        self,
        tx: Dict[str, Any],
        origin: Optional[Dict[str, Any]] = None,
        prior_records: Optional[List[Dict[str, Any]]] = None,
        previous_ts_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Computes `time_analysis` block and evaluates UNUSUAL_HOUR and RAPID_SUCCESSION flags.
        """
        utc_dt = parse_iso_timestamp(tx.get("timestamp"))
        tz_name = (
            tx.get("timezone")
            or (origin or {}).get("timezone")
            or (tx.get("origin") or {}).get("timezone")
            or "UTC"
        )

        # Allow explicit local_hour override if provided, else convert from UTC using tz_name
        if tx.get("local_hour") is not None:
            tx_hour = int(tx["local_hour"]) % 24
            local_dt = to_local_datetime(utc_dt, tz_name)
            tx_dow = local_dt.weekday()
        else:
            local_dt = to_local_datetime(utc_dt, tz_name)
            tx_hour = local_dt.hour
            tx_dow = local_dt.weekday()

        is_night = tx_hour in NIGHT_HOURS
        is_weekend = tx_dow in (5, 6)

        # Learn account_typical_hours from prior_records or explicit field
        if tx.get("account_typical_hours") is not None:
            typical_hours = sorted(list(set(int(h) for h in tx["account_typical_hours"])))
        elif prior_records:
            learned = set()
            for r in prior_records:
                r_ts = r.get("timestamp") or (r.get("original_payload") or {}).get("timestamp")
                if r_ts:
                    r_tz = (r.get("origin") or {}).get("timezone") or tz_name
                    r_local = to_local_datetime(parse_iso_timestamp(r_ts), r_tz)
                    learned.add(r_local.hour)
            typical_hours = sorted(list(learned)) if learned else list(DEFAULT_TYPICAL_HOURS)
        else:
            typical_hours = list(DEFAULT_TYPICAL_HOURS)

        hour_anomaly = tx_hour not in typical_hours

        # Compute time_since_last_txn_mins (guarding against future-skewed timestamps)
        last_ts_str = previous_ts_str
        if not last_ts_str and prior_records:
            chronological_priors = [
                r for r in prior_records
                if parse_iso_timestamp(r.get("timestamp") or (r.get("original_payload") or {}).get("timestamp")) <= utc_dt
            ]
            if chronological_priors:
                last_ts_str = (
                    chronological_priors[-1].get("timestamp")
                    or (chronological_priors[-1].get("original_payload") or {}).get("timestamp")
                )
            else:
                last_ts_str = (
                    prior_records[-1].get("timestamp")
                    or (prior_records[-1].get("original_payload") or {}).get("timestamp")
                )

        if last_ts_str:
            prev_dt = parse_iso_timestamp(last_ts_str)
            raw_diff_seconds = (utc_dt - prev_dt).total_seconds()
            if raw_diff_seconds < 0:
                # Future-dated previous transaction: do not clamp to 0.0 or trigger false RAPID_SUCCESSION
                time_since_last_mins = None
            else:
                time_since_last_mins = round(raw_diff_seconds / 60.0, 2)
        else:
            time_since_last_mins = None

        flags: List[str] = []
        risk_points = 0

        if hour_anomaly and is_night:
            flags.append("UNUSUAL_HOUR")
            risk_points += UNUSUAL_HOUR_POINTS

        if time_since_last_mins is not None and time_since_last_mins < RAPID_SUCCESSION_THRESHOLD_MINS:
            flags.append("RAPID_SUCCESSION")
            risk_points += RAPID_SUCCESSION_POINTS

        time_analysis = {
            "transaction_hour": tx_hour,
            "transaction_day_of_week": tx_dow,
            "is_night_transaction": is_night,
            "is_weekend": is_weekend,
            "account_typical_hours": typical_hours,
            "hour_anomaly": hour_anomaly,
            "time_since_last_txn_mins": time_since_last_mins
        }

        return {
            "time_analysis": time_analysis,
            "flags": flags,
            "risk_points": risk_points
        }
