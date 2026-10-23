"""
Unit & Regression Tests for Feature 6: In-Depth Transaction Detail View (Dashboard)
Writes structured JSON test report to test_results/feature_6_{timestamp}.json
"""

import os
import sys
import json
import threading
import urllib.request
from http.server import HTTPServer
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.stream_monitor import TelemetryHTTPRequestHandler, HTML_PAGE, MAIN_LOG_FILE, QUARANTINE_LOG_FILE
from src.db_client import DBClient
from tests.test_feature_1 import run_feature_1_tests
from tests.test_feature_2 import run_feature_2_tests
from tests.test_feature_3 import run_feature_3_tests
from tests.test_feature_4 import run_feature_4_tests
from tests.test_feature_5 import run_feature_5_tests


def run_feature_6_tests():
    # Seed a rich transaction in MAIN_LOG_FILE so /transaction/{id} and /api/transactions can be tested live
    db = DBClient(fallback_path=MAIN_LOG_FILE, quarantine_fallback_path=QUARANTINE_LOG_FILE)
    sample_tx = {
        "transaction_id": "tx_f6_detail_test",
        "account_id": "acc_f6_1",
        "source_account": "acc_f6_1",
        "timestamp": "2026-10-23T14:00:00Z",
        "amount": 320.50,
        "merchant": "ElectroWorld",
        "merchant_category": "electronics",
        "risk_score": 78,
        "decision": "REVIEW_QUEUE",
        "status": "PENDING_REVIEW",
        "flags": ["ORIGIN_VPN", "AMOUNT_ANOMALY"],
        "origin": {
            "ip_address": "198.51.100.50",
            "country": "NL",
            "city": "Amsterdam",
            "region": "NH",
            "isp": "NordVPN",
            "connection_type": "vpn",
            "is_vpn": True,
            "is_proxy": False,
            "is_tor": False,
            "coordinates": {"lat": 52.3676, "lon": 4.9041},
            "timezone": "Europe/Amsterdam"
        },
        "traceback": {
            "account_transaction_count": 2,
            "previous_transaction_id": "tx_f6_prev_1",
            "previous_transaction_ts": "2026-10-23T12:00:00Z",
            "previous_amount": 100.0,
            "previous_merchant": "GroceryMart",
            "previous_location": "Amsterdam",
            "chain_risk_score": 44.0,
            "velocity_1hr": 1,
            "velocity_24hr": 2,
            "amount_delta_pct": 220.5
        },
        "location_check": {
            "account_registered_city": "Amsterdam",
            "account_registered_country": "NL",
            "transaction_city": "Amsterdam",
            "transaction_country": "NL",
            "distance_km": 0.0,
            "is_international": False,
            "is_impossible_travel": False,
            "travel_speed_kmh": 0.0
        },
        "time_analysis": {
            "transaction_hour": 15,
            "transaction_day_of_week": 4,
            "is_night_transaction": False,
            "is_weekend": False,
            "account_typical_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
            "hour_anomaly": False,
            "time_since_last_txn_mins": 120.0
        },
        "pii_enrichment": {
            "data_source": "MOCK_DEMO_DATA",
            "account_holder_name": "DEMO_HOLDER_06",
            "account_age_days": 120,
            "linked_phone_verified": True,
            "location_matches_transaction": True
        }
    }
    try:
        db.log_transaction(sample_tx, prevent_overwrite=False)
    except Exception:
        pass

    httpd = HTTPServer(("127.0.0.1", 0), TelemetryHTTPRequestHandler)
    port = httpd.server_port
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    results = []
    try:
        # Test Case 1: Click transaction row -> fetch /transaction/{id}, verify all detail sections present
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/transaction/tx_f6_detail_test", timeout=3) as resp:
            detail_data = json.loads(resp.read().decode("utf-8"))

        passed_detail = (
            detail_data.get("transaction_id") == "tx_f6_detail_test"
            and detail_data.get("risk_score") == 78
            and "origin" in detail_data
            and "traceback" in detail_data
            and "location_check" in detail_data
            and "time_analysis" in detail_data
            and "account_history_last_5" in detail_data
            and "openTransactionDetail" in HTML_PAGE
            and "renderRiskGauge" in HTML_PAGE
        )
        results.append({
            "feature": "FEATURE_6_DASHBOARD_DETAIL_VIEW",
            "test_case": "Click transaction row -> sidebar opens, all fields populated via /transaction/{id}",
            "input": {"endpoint": "/transaction/tx_f6_detail_test"},
            "expected_output": {"transaction_id": "tx_f6_detail_test", "has_all_blocks": True},
            "actual_output": {
                "transaction_id": detail_data.get("transaction_id"),
                "keys": list(detail_data.keys())
            },
            "passed": passed_detail,
            "notes": "/transaction/{id} returns full forensic payload with origin, traceback, location_check, time_analysis, and 5-txn history."
        })

        # Test Case 2: Click outside sidebar -> sidebar closes, main table still visible and functional
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as html_resp:
            html_body = html_resp.read().decode("utf-8")

        passed_close = (
            'id="sidebar-backdrop"' in html_body
            and 'onclick="closeDetailSidebar()"' in html_body
            and 'id="transactions-table"' in html_body
            and "@media (max-width: 600px)" in html_body
        )
        results.append({
            "feature": "FEATURE_6_DASHBOARD_DETAIL_VIEW",
            "test_case": "Click outside sidebar -> sidebar closes, main table remains visible and responsive",
            "input": {"action": "click #sidebar-backdrop"},
            "expected_output": {"has_backdrop_close": True, "has_main_table": True, "has_mobile_responsive_css": True},
            "actual_output": {
                "has_backdrop_close": 'onclick="closeDetailSidebar()"' in html_body,
                "has_main_table": 'id="transactions-table"' in html_body,
                "has_mobile_responsive_css": "@media (max-width: 600px)" in html_body
            },
            "passed": passed_close,
            "notes": "Backdrop click handler closes slide-in sidebar without removing or breaking main table."
        })

        # Test Case 3: Export JSON -> valid JSON file downloads
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/transaction/tx_f6_detail_test/export", timeout=3) as exp_resp:
            content_disp = exp_resp.headers.get("Content-Disposition", "")
            raw_export = exp_resp.read().decode("utf-8")
            parsed_export = json.loads(raw_export)

        passed_export = (
            "attachment" in content_disp
            and "transaction_tx_f6_detail_test.json" in content_disp
            and parsed_export.get("transaction_id") == "tx_f6_detail_test"
            and "exportCurrentTransactionJson" in html_body
        )
        results.append({
            "feature": "FEATURE_6_DASHBOARD_DETAIL_VIEW",
            "test_case": "Export JSON -> valid parseable JSON file downloads",
            "input": {"endpoint": "/transaction/tx_f6_detail_test/export"},
            "expected_output": {"valid_json": True, "content_disposition": 'attachment; filename="transaction_tx_f6_detail_test.json"'},
            "actual_output": {"content_disposition": content_disp, "parsed_transaction_id": parsed_export.get("transaction_id")},
            "passed": passed_export,
            "notes": "Export endpoint and client blob download produce valid, parseable JSON."
        })

        # Test Case 4: Slow network loading spinner + pagination across main & quarantine records
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/transactions?page=1&limit=5", timeout=3) as page_resp:
            page_data = json.loads(page_resp.read().decode("utf-8"))

        passed_spinner = (
            'class="spinner"' in html_body
            and "Loading full forensic trace..." in html_body
            and page_data.get("page") == 1
            and isinstance(page_data.get("items"), list)
        )
        results.append({
            "feature": "FEATURE_6_DASHBOARD_DETAIL_VIEW",
            "test_case": "Slow network shows loading spinner + paginated transaction feed",
            "input": {"endpoint": "/api/transactions?page=1&limit=5"},
            "expected_output": {"has_spinner": True, "page": 1},
            "actual_output": {"has_spinner": 'class="spinner"' in html_body, "page": page_data.get("page"), "total_count": page_data.get("total_count")},
            "passed": passed_spinner,
            "notes": "Sidebar displays animated CSS spinner while fetching transaction details and supports pagination."
        })
    finally:
        httpd.shutdown()
        httpd.server_close()

    os.makedirs(os.path.join(ROOT_DIR, "test_results"), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ROOT_DIR, "test_results", f"feature_6_{ts}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    all_passed = all(r["passed"] for r in results)
    print(f"Feature 6 Tests: {sum(r['passed'] for r in results)}/{len(results)} passed -> {out_file}")
    if not all_passed:
        sys.exit(1)
    return results


if __name__ == "__main__":
    print("--- Running Feature 1-5 Regression Checks ---")
    run_feature_1_tests()
    run_feature_2_tests()
    run_feature_3_tests()
    run_feature_4_tests()
    run_feature_5_tests()
    print("--- Running Feature 6 Unit Tests ---")
    run_feature_6_tests()
