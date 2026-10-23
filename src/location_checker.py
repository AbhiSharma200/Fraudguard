"""
Feature 4: Account Holder Location vs Transaction Location
Computes Haversine distance between registered location and transaction origin,
evaluates international status, and calculates physical travel speed from the
previous transaction to detect impossible travel (> 900 km/h -> automatic BLOCK).
"""

import math
from typing import Any, Dict, List, Optional, Tuple

EARTH_RADIUS_KM = 6371.0
IMPOSSIBLE_TRAVEL_SPEED_KMH = 900.0
IMPOSSIBLE_TRAVEL_POINTS = 40
INTERNATIONAL_TXN_POINTS = 10
MIN_EFFECTIVE_HOURS = 1.0 / 3600.0  # 1 second floor for simultaneous (0-minute) cross-city transactions

CITY_COORDINATES: Dict[str, Dict[str, Any]] = {
    "new york": {"lat": 40.7128, "lon": -74.0060, "country": "US"},
    "san francisco": {"lat": 37.7749, "lon": -122.4194, "country": "US"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "country": "US"},
    "boston": {"lat": 42.3601, "lon": -71.0589, "country": "US"},
    "washington": {"lat": 38.9072, "lon": -77.0369, "country": "US"},
    "pittsburgh": {"lat": 40.4406, "lon": -79.9959, "country": "US"},  # ~500km from New York
    "mumbai": {"lat": 19.0760, "lon": 72.8777, "country": "IN"},
    "delhi": {"lat": 28.6139, "lon": 77.2090, "country": "IN"},
    "london": {"lat": 51.5074, "lon": -0.1278, "country": "GB"},
    "amsterdam": {"lat": 52.3676, "lon": 4.9041, "country": "NL"},
    "frankfurt": {"lat": 50.1109, "lon": 8.6821, "country": "DE"},
    "zurich": {"lat": 47.3769, "lon": 8.5417, "country": "CH"},
    "bucharest": {"lat": 44.4268, "lon": 26.1025, "country": "RO"},
    "singapore": {"lat": 1.3521, "lon": 103.8198, "country": "SG"},
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two lat/lon points."""
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(EARTH_RADIUS_KM * c, 2)


def resolve_coordinates(
    city: Optional[str] = None,
    coords_dict: Optional[Dict[str, Any]] = None,
    default_city: str = "New York"
) -> Tuple[float, float]:
    if city:
        key = str(city).strip().lower()
        if key in CITY_COORDINATES:
            return CITY_COORDINATES[key]["lat"], CITY_COORDINATES[key]["lon"]
    if isinstance(coords_dict, dict) and "lat" in coords_dict and "lon" in coords_dict:
        return float(coords_dict["lat"]), float(coords_dict["lon"])
    fallback = CITY_COORDINATES.get(default_city.lower(), CITY_COORDINATES["new york"])
    return fallback["lat"], fallback["lon"]


class LocationChecker:
    def evaluate(
        self,
        tx: Dict[str, Any],
        origin: Optional[Dict[str, Any]] = None,
        previous_record: Optional[Dict[str, Any]] = None,
        time_since_last_txn_mins: Optional[float] = None,
        pii_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Computes `location_check` block and evaluates IMPOSSIBLE_TRAVEL and INTERNATIONAL_TRANSACTION.
        """
        orig = origin or tx.get("origin") or {}
        tx_city = tx.get("transaction_city") or orig.get("city") or tx.get("location") or "New York"
        tx_country = (
            tx.get("transaction_country")
            or orig.get("country")
            or CITY_COORDINATES.get(str(tx_city).lower(), {}).get("country")
            or "US"
        )
        tx_coords = tx.get("coordinates") or orig.get("coordinates")
        tx_lat, tx_lon = resolve_coordinates(tx_city, tx_coords)

        # Account registered city & country
        reg_city = (
            tx.get("account_registered_city")
            or (pii_profile or {}).get("registered_city")
            or ((pii_profile or {}).get("last_known_location") or {}).get("city")
            or "New York"
        )
        reg_country = (
            tx.get("account_registered_country")
            or tx.get("registered_country")
            or (pii_profile or {}).get("registered_country")
            or CITY_COORDINATES.get(str(reg_city).lower(), {}).get("country")
            or "US"
        )
        reg_coords = tx.get("account_registered_coordinates")
        reg_lat, reg_lon = resolve_coordinates(reg_city, reg_coords)

        distance_km = haversine_km(reg_lat, reg_lon, tx_lat, tx_lon)
        is_international = str(tx_country).upper() != str(reg_country).upper()

        # Travel speed vs previous transaction (including simultaneous 0-minute delta across cities)
        travel_speed_kmh = 0.0
        is_impossible_travel = False

        prev_loc_source = previous_record or tx.get("previous_transaction")
        if prev_loc_source and time_since_last_txn_mins is not None and time_since_last_txn_mins >= 0:
            prev_orig = (
                prev_loc_source.get("origin")
                or (prev_loc_source.get("original_payload") or {}).get("origin")
                or {}
            )
            prev_city = (
                prev_loc_source.get("transaction_city")
                or (prev_loc_source.get("location_check") or {}).get("transaction_city")
                or (prev_loc_source.get("original_payload") or {}).get("transaction_city")
                or prev_orig.get("city")
                or prev_loc_source.get("location")
            )
            prev_coords = prev_loc_source.get("coordinates") or prev_orig.get("coordinates")
            if prev_city or prev_coords:
                prev_lat, prev_lon = resolve_coordinates(prev_city, prev_coords)
                travel_dist_km = haversine_km(prev_lat, prev_lon, tx_lat, tx_lon)
                if travel_dist_km > 0:
                    hours = float(time_since_last_txn_mins) / 60.0
                    effective_hours = max(hours, MIN_EFFECTIVE_HOURS)
                    travel_speed_kmh = round(travel_dist_km / effective_hours, 2)
                    if travel_speed_kmh > IMPOSSIBLE_TRAVEL_SPEED_KMH:
                        is_impossible_travel = True

        flags: List[str] = []
        risk_points = 0
        force_block = False

        if is_impossible_travel:
            flags.append("IMPOSSIBLE_TRAVEL")
            risk_points += IMPOSSIBLE_TRAVEL_POINTS
            force_block = True

        if is_international:
            flags.append("INTERNATIONAL_TRANSACTION")
            risk_points += INTERNATIONAL_TXN_POINTS

        location_check = {
            "account_registered_city": reg_city,
            "account_registered_country": reg_country,
            "transaction_city": tx_city,
            "transaction_country": tx_country,
            "distance_km": distance_km,
            "is_international": is_international,
            "is_impossible_travel": is_impossible_travel,
            "travel_speed_kmh": travel_speed_kmh
        }

        return {
            "location_check": location_check,
            "flags": flags,
            "risk_points": risk_points,
            "force_block": force_block
        }
