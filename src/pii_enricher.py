"""
Feature 7: PII Enrichment Layer (Simulated — Demo Safe)
Uses MOCK_DEMO_DATA ONLY from data/mock_pii_store.json or src/mock_pii_store.json (20 fake demo profiles).
Evaluates LOCATION_MISMATCH (+15), NEW_ACCOUNT (<30d, +10), and UNVERIFIED_CONTACT (+5).
"""

import os
import json
from typing import Any, Dict, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CANDIDATE_PII_STORES = [
    os.path.join(SCRIPT_DIR, "mock_pii_store.json"),
    os.path.join(SCRIPT_DIR, "..", "data", "mock_pii_store.json"),
    os.path.join("/var/task", "mock_pii_store.json"),
    os.path.join("/var/task", "data", "mock_pii_store.json"),
    "data/mock_pii_store.json",
    "mock_pii_store.json",
]

EMBEDDED_FALLBACK_PII_PROFILES: Dict[str, Dict[str, Any]] = {
    "acc_1": {
        "account_holder_name": "DEMO_HOLDER_01 (MOCK)",
        "account_age_days": 450,
        "linked_phone_verified": True,
        "social_profile_risk_score": 0.05,
        "device_fingerprint": "fp_demo_ios_001",
        "registered_city": "New York",
        "registered_country": "US",
        "last_known_location": {
            "source": "SIMULATED_CELL_TOWER",
            "city": "New York",
            "lat": 40.7128,
            "lon": -74.006,
            "accuracy_meters": 50,
            "timestamp": "2026-10-23T10:00:00Z"
        }
    },
    "acc_2": {
        "account_holder_name": "DEMO_HOLDER_02 (MOCK)",
        "account_age_days": 12,
        "linked_phone_verified": True,
        "social_profile_risk_score": 0.35,
        "device_fingerprint": "fp_demo_and_002",
        "registered_city": "New York",
        "registered_country": "US",
        "last_known_location": {
            "source": "SIMULATED_CELL_TOWER",
            "city": "New York",
            "lat": 40.7128,
            "lon": -74.006,
            "accuracy_meters": 65,
            "timestamp": "2026-10-23T10:00:00Z"
        }
    },
    "acc_3": {
        "account_holder_name": "DEMO_HOLDER_03 (MOCK)",
        "account_age_days": 180,
        "linked_phone_verified": False,
        "social_profile_risk_score": 0.65,
        "device_fingerprint": "fp_demo_web_003",
        "registered_city": "Chicago",
        "registered_country": "US",
        "last_known_location": {
            "source": "SIMULATED_CELL_TOWER",
            "city": "Chicago",
            "lat": 41.8781,
            "lon": -87.6298,
            "accuracy_meters": 80,
            "timestamp": "2026-10-23T10:00:00Z"
        }
    },
    "acc_4": {
        "account_holder_name": "DEMO_HOLDER_04 (MOCK)",
        "account_age_days": 5,
        "linked_phone_verified": False,
        "social_profile_risk_score": 0.85,
        "device_fingerprint": "fp_demo_emu_004",
        "registered_city": "Mumbai",
        "registered_country": "IN",
        "last_known_location": {
            "source": "SIMULATED_CELL_TOWER",
            "city": "Mumbai",
            "lat": 19.076,
            "lon": 72.8777,
            "accuracy_meters": 100,
            "timestamp": "2026-10-23T10:00:00Z"
        }
    },
    "acc_10": {
        "account_holder_name": "DEMO_HOLDER_10 (MOCK)",
        "account_age_days": 14,
        "linked_phone_verified": False,
        "social_profile_risk_score": 0.78,
        "device_fingerprint": "fp_demo_tor_010",
        "registered_city": "Frankfurt",
        "registered_country": "DE",
        "last_known_location": {
            "source": "SIMULATED_CELL_TOWER",
            "city": "Frankfurt",
            "lat": 50.1109,
            "lon": 8.6821,
            "accuracy_meters": 90,
            "timestamp": "2026-10-23T10:00:00Z"
        }
    }
}


class PIIEnricher:
    def __init__(self, store_path: Optional[str] = None):
        self.store_path = store_path
        self.profiles = self._load_store()

    def _load_store(self) -> Dict[str, Any]:
        paths = [self.store_path] if self.store_path else list(CANDIDATE_PII_STORES)
        for p in paths:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict) and loaded:
                            return loaded
                except Exception:
                    continue
        return dict(EMBEDDED_FALLBACK_PII_PROFILES)

    def get_profile(self, account_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not account_id:
            return None
        return self.profiles.get(str(account_id))

    def evaluate(self, tx: Dict[str, Any], origin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Enriches transaction with `pii_enrichment` block (always `data_source: MOCK_DEMO_DATA`).
        Evaluates LOCATION_MISMATCH (+15), NEW_ACCOUNT (+10), UNVERIFIED_CONTACT (+5).
        """
        account_id = tx.get("account_id") or tx.get("source_account") or tx.get("user_id")
        profile = tx.get("mock_pii_override") or self.get_profile(account_id)

        if not profile:
            return {
                "pii_enrichment": {
                    "data_source": "MOCK_DEMO_DATA",
                    "enrichment_status": "NOT_FOUND",
                    "account_holder_name": "DEMO_UNREGISTERED (MOCK)",
                    "account_age_days": None,
                    "linked_phone_verified": None,
                    "social_profile_risk_score": 0.0,
                    "device_fingerprint": "unknown",
                    "last_known_location": None,
                    "location_matches_transaction": True
                },
                "flags": [],
                "risk_points": 0,
                "profile": None
            }

        orig = origin or tx.get("origin") or {}
        tx_city = (
            tx.get("transaction_city")
            or orig.get("city")
            or tx.get("location")
            or (profile.get("last_known_location") or {}).get("city")
            or "New York"
        )
        last_loc = dict(profile.get("last_known_location") or {})
        last_loc["source"] = "SIMULATED_CELL_TOWER"
        cell_city = last_loc.get("city", "New York")

        if tx.get("location_matches_transaction") is not None:
            loc_matches = bool(tx["location_matches_transaction"])
        else:
            loc_matches = str(cell_city).strip().lower() == str(tx_city).strip().lower()

        account_age = int(profile.get("account_age_days", 365))
        phone_verified = bool(profile.get("linked_phone_verified", True))

        flags = []
        risk_points = 0

        if not loc_matches:
            flags.append("LOCATION_MISMATCH")
            risk_points += 15

        if account_age < 30:
            flags.append("NEW_ACCOUNT")
            risk_points += 10

        if not phone_verified:
            flags.append("UNVERIFIED_CONTACT")
            risk_points += 5

        pii_enrichment = {
            "data_source": "MOCK_DEMO_DATA",
            "enrichment_status": "FOUND",
            "account_holder_name": str(profile.get("account_holder_name", "DEMO_HOLDER (MOCK)")),
            "account_age_days": account_age,
            "linked_phone_verified": phone_verified,
            "social_profile_risk_score": float(profile.get("social_profile_risk_score", 0.0)),
            "device_fingerprint": str(profile.get("device_fingerprint", "fp_demo_default")),
            "last_known_location": last_loc,
            "location_matches_transaction": loc_matches
        }

        return {
            "pii_enrichment": pii_enrichment,
            "flags": flags,
            "risk_points": risk_points,
            "profile": profile
        }
