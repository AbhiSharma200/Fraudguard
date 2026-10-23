"""
Feature 1: Transaction Origin & Source Tracing
Captures and enriches transaction origin metadata (IP, geolocation, ISP, VPN/Proxy/TOR status)
and evaluates origin-based fraud rules.
"""

import json
import urllib.request
import urllib.error

# Local deterministic IP -> Geo/Network lookup table for fast, reliable offline/demo execution
LOCAL_IP_GEO_DB = {
    # Clean domestic IPs (US / IN / UK)
    "192.0.2.1": {
        "country": "US",
        "city": "New York",
        "region": "NY",
        "isp": "Verizon Fios",
        "connection_type": "broadband",
        "is_vpn": False,
        "is_proxy": False,
        "is_tor": False,
        "coordinates": {"lat": 40.7128, "lon": -74.0060},
        "timezone": "America/New_York"
    },
    "192.0.2.2": {
        "country": "US",
        "city": "San Francisco",
        "region": "CA",
        "isp": "Comcast Cable",
        "connection_type": "broadband",
        "is_vpn": False,
        "is_proxy": False,
        "is_tor": False,
        "coordinates": {"lat": 37.7749, "lon": -122.4194},
        "timezone": "America/Los_Angeles"
    },
    "192.0.2.3": {
        "country": "US",
        "city": "Chicago",
        "region": "IL",
        "isp": "AT&T Mobility",
        "connection_type": "mobile",
        "is_vpn": False,
        "is_proxy": False,
        "is_tor": False,
        "coordinates": {"lat": 41.8781, "lon": -87.6298},
        "timezone": "America/Chicago"
    },
    "203.0.113.10": {
        "country": "IN",
        "city": "Mumbai",
        "region": "MH",
        "isp": "Reliance Jio",
        "connection_type": "mobile",
        "is_vpn": False,
        "is_proxy": False,
        "is_tor": False,
        "coordinates": {"lat": 19.0760, "lon": 72.8777},
        "timezone": "Asia/Kolkata"
    },
    "198.51.100.20": {
        "country": "GB",
        "city": "London",
        "region": "ENG",
        "isp": "British Telecom",
        "connection_type": "broadband",
        "is_vpn": False,
        "is_proxy": False,
        "is_tor": False,
        "coordinates": {"lat": 51.5074, "lon": -0.1278},
        "timezone": "Europe/London"
    },
    # VPN IPs
    "198.51.100.50": {
        "country": "NL",
        "city": "Amsterdam",
        "region": "NH",
        "isp": "NordVPN / Tefincom S.A.",
        "connection_type": "vpn",
        "is_vpn": True,
        "is_proxy": False,
        "is_tor": False,
        "coordinates": {"lat": 52.3676, "lon": 4.9041},
        "timezone": "Europe/Amsterdam"
    },
    "10.200.0.50": {
        "country": "CH",
        "city": "Zurich",
        "region": "ZH",
        "isp": "ProtonVPN AG",
        "connection_type": "vpn",
        "is_vpn": True,
        "is_proxy": True,
        "is_tor": False,
        "coordinates": {"lat": 47.3769, "lon": 8.5417},
        "timezone": "Europe/Zurich"
    },
    # Proxy IP
    "198.51.100.75": {
        "country": "SG",
        "city": "Singapore",
        "region": "SG",
        "isp": "DigitalOcean Proxy Node",
        "connection_type": "proxy",
        "is_vpn": False,
        "is_proxy": True,
        "is_tor": False,
        "coordinates": {"lat": 1.3521, "lon": 103.8198},
        "timezone": "Asia/Singapore"
    },
    # TOR Exit Nodes
    "185.220.101.1": {
        "country": "DE",
        "city": "Frankfurt",
        "region": "HE",
        "isp": "Tor Exit Node / Zwiebelfreunde",
        "connection_type": "tor",
        "is_vpn": False,
        "is_proxy": True,
        "is_tor": True,
        "coordinates": {"lat": 50.1109, "lon": 8.6821},
        "timezone": "Europe/Berlin"
    },
    "185.220.101.99": {
        "country": "RO",
        "city": "Bucharest",
        "region": "B",
        "isp": "Tor Exit Relay RO",
        "connection_type": "tor",
        "is_vpn": False,
        "is_proxy": True,
        "is_tor": True,
        "coordinates": {"lat": 44.4268, "lon": 26.1025},
        "timezone": "Europe/Bucharest"
    }
}

DEFAULT_DOMESTIC_PROFILE = {
    "country": "US",
    "city": "New York",
    "region": "NY",
    "isp": "Default Domestic ISP",
    "connection_type": "broadband",
    "is_vpn": False,
    "is_proxy": False,
    "is_tor": False,
    "coordinates": {"lat": 40.7128, "lon": -74.0060},
    "timezone": "America/New_York"
}


class OriginTracer:
    def __init__(self, allow_external_api=False, api_timeout=1.0):
        self.allow_external_api = allow_external_api
        self.api_timeout = api_timeout

    @staticmethod
    def extract_ip(tx, event_headers=None):
        """Extract origin IP from transaction payload or Lambda event headers."""
        if isinstance(tx.get("origin"), dict) and tx["origin"].get("ip_address"):
            return str(tx["origin"]["ip_address"]).strip()
        if tx.get("origin_ip"):
            return str(tx["origin_ip"]).strip()
        if tx.get("ip_address"):
            return str(tx["ip_address"]).strip()
        if event_headers and isinstance(event_headers, dict):
            xff = event_headers.get("x-forwarded-for") or event_headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return "192.0.2.1"

    def lookup_ip(self, ip_address, pre_populated_origin=None):
        """
        Look up IP metadata in local deterministic table, pre-populated origin dict,
        or optional ip-api.com fallback.
        """
        if pre_populated_origin and isinstance(pre_populated_origin, dict):
            merged = dict(DEFAULT_DOMESTIC_PROFILE)
            merged["ip_address"] = ip_address
            for k, v in pre_populated_origin.items():
                if v is not None:
                    merged[k] = v
            if "coordinates" not in merged or not isinstance(merged["coordinates"], dict):
                merged["coordinates"] = dict(DEFAULT_DOMESTIC_PROFILE["coordinates"])
            return merged

        if ip_address in LOCAL_IP_GEO_DB:
            record = dict(LOCAL_IP_GEO_DB[ip_address])
            record["ip_address"] = ip_address
            record["coordinates"] = dict(record["coordinates"])
            return record

        if self.allow_external_api:
            try:
                url = f"http://ip-api.com/json/{ip_address}?fields=status,countryCode,regionName,city,lat,lon,timezone,isp,mobile,proxy"
                req = urllib.request.Request(url, headers={"User-Agent": "FraudGuard/1.0"})
                with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "success":
                        is_proxy = bool(data.get("proxy", False))
                        is_mobile = bool(data.get("mobile", False))
                        conn_type = "proxy" if is_proxy else ("mobile" if is_mobile else "broadband")
                        return {
                            "ip_address": ip_address,
                            "country": data.get("countryCode", "US"),
                            "city": data.get("city", "Unknown"),
                            "region": data.get("regionName", "Unknown"),
                            "isp": data.get("isp", "Unknown ISP"),
                            "connection_type": conn_type,
                            "is_vpn": False,
                            "is_proxy": is_proxy,
                            "is_tor": False,
                            "coordinates": {
                                "lat": float(data.get("lat", 0.0)),
                                "lon": float(data.get("lon", 0.0))
                            },
                            "timezone": data.get("timezone", "UTC")
                        }
            except Exception:
                pass

        # Default clean domestic fallback
        fallback = dict(DEFAULT_DOMESTIC_PROFILE)
        fallback["ip_address"] = ip_address
        fallback["coordinates"] = dict(DEFAULT_DOMESTIC_PROFILE["coordinates"])
        return fallback

    def evaluate(self, tx, event_headers=None, registered_country=None):
        """
        Enriches transaction with `origin` block and evaluates origin risk rules.
        Returns:
          {
            "origin": { ... },
            "flags": [...],
            "risk_points": int,       # 0-100 scale addition
            "force_block": bool
          }
        """
        ip_address = self.extract_ip(tx, event_headers=event_headers)
        pre_origin = tx.get("origin") if isinstance(tx.get("origin"), dict) else None
        origin = self.lookup_ip(ip_address, pre_populated_origin=pre_origin)

        # Ensure connection_type consistency with boolean flags
        if origin.get("is_tor"):
            origin["connection_type"] = "tor"
        elif origin.get("is_vpn"):
            origin["connection_type"] = "vpn"
        elif origin.get("is_proxy"):
            origin["connection_type"] = "proxy"

        flags = []
        risk_points = 0
        force_block = False

        # Check TOR first (HIGH RISK +20 and automatic BLOCK)
        if origin.get("is_tor"):
            flags.append("ORIGIN_TOR")
            risk_points += 20
            force_block = True

        # Check VPN (HIGH RISK +20)
        if origin.get("is_vpn"):
            flags.append("ORIGIN_VPN")
            risk_points += 20

        # Check cross-border mismatch (IP country != card/account registered country) -> +10
        acct_country = registered_country or tx.get("registered_country") or tx.get("card_registered_country")
        if acct_country and origin.get("country") and origin["country"].upper() != acct_country.upper():
            flags.append("GEO_ORIGIN_MISMATCH")
            risk_points += 10

        return {
            "origin": origin,
            "flags": flags,
            "risk_points": risk_points,
            "force_block": force_block
        }
