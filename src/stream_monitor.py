#!/usr/bin/env python3
"""
FraudGuard Risk & Compliance Operations Console
Serves the real-time transaction monitoring interface, detail drawer,
live transaction simulator, quarantine release API, and governance endpoints.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime, timezone
import time
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

TELEMETRY_FILE = os.path.join(SCRIPT_DIR, "live_telemetry.json")
MAIN_LOG_FILE = os.path.join(ROOT_DIR, "data", "audit_log.json")
QUARANTINE_LOG_FILE = os.path.join(ROOT_DIR, "data", "quarantine_log.json")

FLAG_EXPLANATIONS = {
    "ORIGIN_VPN": "Transaction originated from a commercial VPN provider (+20 risk).",
    "ORIGIN_TOR": "Transaction originated from a Tor exit relay (+20 risk, automatic block).",
    "GEO_ORIGIN_MISMATCH": "Origin IP country differs from the cardholder's registered country (+10 risk).",
    "VELOCITY_SPIKE": "More than 5 transactions from this account within a 1-hour window (+25 risk).",
    "AMOUNT_SPIKE": "Transaction amount exceeds the account's historical baseline by more than 300% (+20 risk).",
    "UNUSUAL_HOUR": "Nighttime activity (23:00 to 05:00 local time) outside typical account hours (+15 risk).",
    "RAPID_SUCCESSION": "Transaction occurred less than 2 minutes after the prior transaction (+20 risk).",
    "IMPOSSIBLE_TRAVEL": "Implied travel speed from the previous transaction exceeds 900 km/h (automatic block).",
    "INTERNATIONAL_TRANSACTION": "Transaction country differs from the account holder's home country (+10 risk).",
    "LOCATION_MISMATCH": "Telemetry location does not match the transaction city (+15 risk).",
    "NEW_ACCOUNT": "Account age is less than 30 days (+10 risk).",
    "UNVERIFIED_CONTACT": "Account holder phone number has not been verified (+5 risk).",
    "AMOUNT_ANOMALY": "Transaction amount exceeds the high-value review threshold ($180.00).",
    "CHANNEL_RISK": "High-value transfer over an elevated-risk payment rail ($150.00+).",
    "HIGH_VELOCITY": "Elevated 6-hour transaction frequency detected by the velocity monitor.",
    "VELOCITY_BREACH": "Transaction velocity exceeded the maximum allowed rate within the evaluation window."
}

TOS_TEXT = """FraudGuard Risk Operations Terms of Service (Effective October 2026)

1. Authorized Operational Use
Access to the FraudGuard Risk & Compliance Console is restricted to authorized risk analysts, compliance officers, and settlement operations personnel within licensed financial institutions.

2. Automated Decisioning and Quarantine Review
Transactions evaluated by the FraudGuard scoring engine are classified deterministically across network, velocity, behavioral, and geospatial signals. Transactions placed in Quarantined status are held for manual compliance review for up to 24 hours unless released earlier by an authorized operator with documented review notes.

3. Audit Trail Integrity
All scoring evaluations, rule triggers, and manual release actions are recorded with immutable timestamps and operator attribution in the compliance ledger. Sharing authorization credentials or bypassing review controls is strictly prohibited."""

PRIVACY_TEXT = """FraudGuard Privacy & Data Governance Policy (GDPR Article 22 & PCI-DSS)

1. Data Minimization and Retention
Operational transaction records are retained in the primary audit ledger for 90 days to support dispute resolution and regulatory audits. Quarantined transaction records are retained for 7 days following final disposition.

2. Identity Enrichment Safeguards
Customer verification attributes displayed in the console are scoped strictly to fraud prevention and compliance review. In sandbox and evaluation environments, directory attributes are resolved against isolated synthetic verification profiles without transmitting personal data to external third parties.

3. Automated Decision Transparency
Every automated Review Queue or Block disposition records explicit, human-readable signal codes and quantitative risk contributions so compliance teams can inspect, explain, and override any automated hold."""

HTML_PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FraudGuard Risk &amp; Compliance</title>
    <style>
        :root {
            --bg-primary: #F6F8FA;
            --bg-surface: #FFFFFF;
            --bg-elevated: #F8FAFC;
            --bg-hover: #F1F5F9;
            --bg-subtle: #E2E8F0;
            --text-primary: #0F172A;
            --text-secondary: #475569;
            --text-muted: #64748B;
            --border-color: #E2E8F0;
            --border-strong: #CBD5E1;
            --accent-primary: #1E293B;
            --accent-primary-text: #FFFFFF;
            --accent-link: #2563EB;
            --signal-approve-fg: #065F46;
            --signal-approve-bg: #ECFDF5;
            --signal-approve-bd: #A7F3D0;
            --signal-review-fg: #92400E;
            --signal-review-bg: #FFFBEB;
            --signal-review-bd: #FDE68A;
            --signal-block-fg: #991B1B;
            --signal-block-bg: #FEF2F2;
            --signal-block-bd: #FECACA;
            --signal-quarantine-fg: #5B21B6;
            --signal-quarantine-bg: #F5F3FF;
            --signal-quarantine-bd: #DDD6FE;
            --signal-released-fg: #1E40AF;
            --signal-released-bg: #EFF6FF;
            --signal-released-bd: #BFDBFE;
            --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            --font-mono: 'SFMono-Regular', Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
        }

        html[data-theme="dark"] {
            --bg-primary: #0B0F17;
            --bg-surface: #111827;
            --bg-elevated: #1E293B;
            --bg-hover: #1E293B;
            --bg-subtle: #334155;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --text-muted: #64748B;
            --border-color: #1F2937;
            --border-strong: #374151;
            --accent-primary: #2563EB;
            --accent-primary-text: #FFFFFF;
            --accent-link: #60A5FA;
            --signal-approve-fg: #6EE7B7;
            --signal-approve-bg: #064E3B;
            --signal-approve-bd: #047857;
            --signal-review-fg: #FCD34D;
            --signal-review-bg: #451A03;
            --signal-review-bd: #B45309;
            --signal-block-fg: #FCA5A5;
            --signal-block-bg: #450A0A;
            --signal-block-bd: #B91C1C;
            --signal-quarantine-fg: #DDD6FE;
            --signal-quarantine-bg: #2E1065;
            --signal-quarantine-bd: #6D28D9;
            --signal-released-fg: #93C5FD;
            --signal-released-bg: #1E3A8A;
            --signal-released-bd: #1D4ED8;
        }

        * {
            box-sizing: border-box;
            box-shadow: none !important;
        }

        body {
            font-family: var(--font-sans);
            background-color: var(--bg-primary);
            color: var(--text-primary);
            margin: 0;
            padding: 20px 28px;
            font-size: 13.5px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Navigation Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            padding-bottom: 16px;
            margin-bottom: 18px;
            border-bottom: 1px solid var(--border-color);
        }
        .brand-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .brand-mark {
            width: 24px;
            height: 24px;
            border-radius: 5px;
            background-color: var(--accent-primary);
            color: var(--accent-primary-text);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 13px;
        }
        .header h1 {
            margin: 0;
            font-size: 17px;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.01em;
        }
        .brand-subtitle {
            color: var(--text-muted);
            font-size: 13px;
            font-weight: 400;
            padding-left: 10px;
            border-left: 1px solid var(--border-color);
        }
        .header-controls {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .badge {
            background-color: var(--signal-approve-bg);
            color: var(--signal-approve-fg);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            border: 1px solid var(--signal-approve-bd);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            height: 32px;
        }
        .badge.paused {
            background-color: var(--signal-review-bg);
            color: var(--signal-review-fg);
            border-color: var(--signal-review-bd);
        }
        .pulse {
            display: inline-block;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: var(--signal-approve-fg);
        }
        .badge.paused .pulse {
            background-color: var(--signal-review-fg);
        }

        /* 6-Column Divided Summary Metric Bar */
        .telemetry-strip {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: var(--bg-surface);
            margin-bottom: 18px;
            overflow: hidden;
        }
        .telemetry-cell {
            padding: 14px 16px;
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .telemetry-cell:last-child {
            border-right: none;
        }
        .telemetry-label {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 6px;
        }
        .telemetry-val-row {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 8px;
        }
        .telemetry-cell p {
            margin: 0;
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
            font-size: 22px;
            font-weight: 600;
            color: var(--text-primary);
        }
        .telemetry-unit {
            font-size: 11.5px;
            color: var(--text-muted);
        }

        /* Interactive Transaction Simulator Panel */
        .workbench-strip {
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: var(--bg-surface);
            margin-bottom: 18px;
            overflow: hidden;
        }
        .workbench-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            padding: 10px 16px;
            background-color: var(--bg-elevated);
            border-bottom: 1px solid var(--border-color);
        }
        .workbench-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
        }
        .workbench-subtitle {
            font-size: 12.5px;
            color: var(--text-muted);
            margin-left: 8px;
            font-weight: 400;
        }
        .workbench-presets {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 12px 16px;
            align-items: center;
        }
        .workbench-custom {
            display: none;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
            padding: 12px 16px;
            border-top: 1px solid var(--border-color);
            background-color: var(--bg-elevated);
            align-items: end;
        }
        .workbench-custom.open {
            display: grid;
        }
        .sim-receipt {
            display: none;
            padding: 9px 16px;
            font-size: 12.5px;
            border-top: 1px solid var(--border-color);
            background-color: var(--bg-elevated);
            color: var(--text-primary);
            justify-content: space-between;
            align-items: center;
        }
        .sim-receipt.visible {
            display: flex;
        }

        .main-layout {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }
        .panel {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow: hidden;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            padding: 12px 16px;
            background-color: var(--bg-surface);
            border-bottom: 1px solid var(--border-color);
        }
        .panel h2 {
            margin: 0;
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
        }

        /* Filter Bar */
        .filter-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
            gap: 10px;
            background: var(--bg-elevated);
            border-bottom: 1px solid var(--border-color);
            padding: 12px 16px;
            align-items: end;
        }
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .filter-group label {
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 500;
        }
        .filter-input, .filter-select {
            font-family: var(--font-sans);
            background: var(--bg-surface);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            height: 32px;
            padding: 0 10px;
            font-size: 13px;
            width: 100%;
        }
        .filter-input:focus, .filter-select:focus {
            outline: none;
            border-color: var(--accent-link);
        }
        .filter-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
        }
        .error-banner {
            display: none;
            background: var(--signal-block-bg);
            border-bottom: 1px solid var(--signal-block-bd);
            color: var(--signal-block-fg);
            padding: 8px 16px;
            font-size: 12.5px;
        }
        .error-banner.visible {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Clean Horizontal Table Mechanics */
        .table-wrapper {
            overflow-x: auto;
        }
        table.txn-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        table.txn-table th, table.txn-table td {
            padding: 11px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        table.txn-table th.num-col, table.txn-table td.num-col {
            text-align: right;
        }
        table.txn-table th {
            background-color: var(--bg-elevated);
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.04em;
        }
        table.txn-table tbody tr {
            cursor: pointer;
            transition: background-color 0.12s ease;
        }
        table.txn-table tbody tr:hover {
            background-color: var(--bg-hover);
        }
        table.txn-table tbody tr.selected-row {
            background-color: var(--bg-hover);
            outline: 1px solid var(--accent-link);
        }
        .mono-cell {
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
            font-size: 12.5px;
        }

        /* Status Badges (#10b981 / #f59e0b / #ef4444 / #a855f7 / #38bdf8 semantic tokens) */
        .status-pill {
            display: inline-block;
            font-family: var(--font-sans);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-APPROVE, .status-ALLOW, .status-APPROVED {
            background: var(--signal-approve-bg);
            color: var(--signal-approve-fg);
            border: 1px solid #10b981;
        }
        .status-REVIEW_QUEUE, .status-PENDING_REVIEW {
            background: var(--signal-review-bg);
            color: var(--signal-review-fg);
            border: 1px solid #f59e0b;
        }
        .status-BLOCK {
            background: var(--signal-block-bg);
            color: var(--signal-block-fg);
            border: 1px solid #ef4444;
        }
        .status-QUARANTINED {
            background: var(--signal-quarantine-bg);
            color: var(--signal-quarantine-fg);
            border: 1px solid #a855f7;
        }
        .status-RELEASED {
            background: var(--signal-released-bg);
            color: var(--signal-released-fg);
            border: 1px solid #38bdf8;
        }
        .flag-chip {
            display: inline-block;
            background: var(--bg-elevated);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 11.5px;
            margin: 1px 4px 1px 0;
            font-family: var(--font-mono);
        }

        /* Clean Buttons */
        .btn {
            font-family: var(--font-sans);
            background: var(--bg-surface);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            height: 32px;
            padding: 0 12px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: background-color 0.12s ease, border-color 0.12s ease;
        }
        .btn:hover:not(:disabled) {
            background: var(--bg-hover);
            border-color: var(--border-strong);
        }
        .btn:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }
        .btn-primary {
            background: var(--accent-primary);
            color: var(--accent-primary-text);
            border-color: var(--accent-primary);
        }
        .btn-primary:hover:not(:disabled) {
            opacity: 0.92;
            background: var(--accent-primary);
        }
        .btn-quarantine {
            background: var(--signal-quarantine-bg);
            border-color: var(--signal-quarantine-bd);
            color: var(--signal-quarantine-fg);
        }
        .btn-danger {
            background: var(--signal-block-bg);
            border-color: var(--signal-block-bd);
            color: var(--signal-block-fg);
        }

        /* Skeleton Loaders (Solid Opacity Pulse - Zero Gradients) */
        .skeleton-line {
            display: block;
            height: 12px;
            border-radius: 3px;
            background-color: var(--bg-subtle);
            animation: skeletonPulse 1.1s ease-in-out infinite alternate;
        }
        .skeleton-block {
            display: block;
            height: 64px;
            border-radius: 5px;
            background-color: var(--bg-subtle);
            border: 1px solid var(--border-color);
            margin-bottom: 10px;
            animation: skeletonPulse 1.1s ease-in-out infinite alternate;
        }
        @keyframes skeletonPulse {
            0% { opacity: 0.35; }
            100% { opacity: 0.85; }
        }

        /* Slide-in Detail Drawer */
        .sidebar-backdrop {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(15, 23, 42, 0.35);
            z-index: 999;
        }
        .sidebar-backdrop.open { display: block; }

        .detail-sidebar {
            position: fixed;
            top: 0;
            right: -560px;
            width: 540px;
            max-width: 100vw;
            height: 100vh;
            background: var(--bg-surface);
            border-left: 1px solid var(--border-color);
            z-index: 1000;
            overflow-y: auto;
            padding: 20px;
            transition: right 0.2s ease;
        }
        .detail-sidebar.open { right: 0; }

        /* Mobile 375px viewport support: stack below table, never overlap */
        @media (max-width: 600px) {
            body { padding: 12px; }
            .telemetry-strip { grid-template-columns: repeat(2, 1fr); }
            .telemetry-cell { border-bottom: 1px solid var(--border-color); }
            .filter-bar { grid-template-columns: 1fr; }
            .detail-sidebar {
                position: static;
                width: 100%;
                height: auto;
                display: none;
                border-left: none;
                border-top: 1px solid var(--border-strong);
                border-radius: 6px;
                margin-top: 16px;
                padding: 14px;
            }
            .detail-sidebar.open { display: block; }
            .sidebar-backdrop.open { display: none; }
            .kv-grid { grid-template-columns: 1fr !important; }
        }

        .sidebar-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 8px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 14px;
            margin-bottom: 16px;
        }
        .gauge-container {
            display: flex;
            align-items: center;
            gap: 16px;
            background: var(--bg-elevated);
            padding: 14px 16px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            margin-bottom: 14px;
        }
        .gauge-ring {
            width: 80px;
            height: 80px;
            position: relative;
            flex-shrink: 0;
        }
        .gauge-bar-track {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: var(--bg-subtle);
            overflow: hidden;
            margin-top: 8px;
        }
        .gauge-bar-fill {
            height: 100%;
            border-radius: 3px;
        }
        .detail-section {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 12px 14px;
            margin-bottom: 12px;
        }
        .detail-section h4 {
            margin: 0 0 10px 0;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 6px;
        }
        .kv-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px 14px;
            font-size: 12.5px;
        }
        .kv-label {
            color: var(--text-muted);
            font-size: 12px;
        }
        .kv-val {
            color: var(--text-primary);
            font-weight: 500;
            word-break: break-word;
        }
        .kv-val-mono {
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
            font-weight: 500;
            font-size: 12px;
        }
        .mini-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-top: 8px;
        }
        .mini-table th, .mini-table td {
            padding: 6px 8px;
            border-bottom: 1px solid var(--border-color);
            text-align: left;
        }
        .mini-table th {
            background: var(--bg-elevated);
            color: var(--text-muted);
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
        }
        .origin-map-box {
            margin-top: 10px;
            background: var(--bg-elevated);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 10px;
        }
        .origin-map-svg {
            width: 100%;
            height: auto;
            display: block;
            border-radius: 4px;
            border: 1px solid var(--border-color);
        }
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid var(--border-color);
            border-top-color: var(--accent-link);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        pre.raw-json {
            font-family: var(--font-mono);
            background: var(--bg-elevated);
            padding: 12px;
            border-radius: 5px;
            color: var(--text-primary);
            font-size: 11.5px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
            max-height: 300px;
            margin: 8px 0 0 0;
        }
        .directory-badge {
            background: var(--bg-elevated);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            padding: 1px 6px;
            margin-left: 6px;
        }

        /* Footer & Legal Modal */
        .inst-footer {
            margin-top: 24px;
            padding-top: 14px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            font-size: 12.5px;
            color: var(--text-muted);
        }
        .legal-links {
            display: flex;
            gap: 16px;
        }
        .legal-link-btn {
            background: none;
            border: none;
            padding: 0;
            font-family: var(--font-sans);
            font-size: 12.5px;
            color: var(--text-secondary);
            cursor: pointer;
        }
        .legal-link-btn:hover {
            color: var(--text-primary);
            text-decoration: underline;
        }
        .legal-modal {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(15, 23, 42, 0.45);
            z-index: 1100;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .legal-modal.open {
            display: flex;
        }
        .legal-modal-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            max-width: 640px;
            width: 100%;
            padding: 20px;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="brand-row">
            <span class="brand-mark">F</span>
            <h1>FraudGuard</h1>
            <span class="brand-subtitle">Risk &amp; Compliance</span>
        </div>
        <div class="header-controls">
            <button class="btn" id="btn-theme-toggle" onclick="toggleTheme()">Dark mode</button>
            <div id="live-status-badge" class="badge"><span class="pulse"></span> <span id="live-status-text">Live</span></div>
        </div>
    </header>

    <!-- 6-Column Summary Metric Bar -->
    <section class="telemetry-strip" aria-label="Operational Summary Metrics">
        <div class="telemetry-cell">
            <div class="telemetry-label">Processed</div>
            <div class="telemetry-val-row">
                <p id="sent-count">0</p>
                <span class="telemetry-unit">total</span>
            </div>
        </div>
        <div class="telemetry-cell">
            <div class="telemetry-label">In Review</div>
            <div class="telemetry-val-row">
                <p id="fraud-count" style="color: var(--signal-review-fg);">0</p>
                <span class="telemetry-unit">flagged</span>
            </div>
        </div>
        <div class="telemetry-cell">
            <div class="telemetry-label">Quarantined</div>
            <div class="telemetry-val-row">
                <p id="quarantine-count" style="color: var(--signal-quarantine-fg);">0</p>
                <span class="telemetry-unit">held</span>
            </div>
        </div>
        <div class="telemetry-cell">
            <div class="telemetry-label">Flag Rate</div>
            <div class="telemetry-val-row">
                <p id="fraud-rate">0.0%</p>
                <span class="telemetry-unit">of volume</span>
            </div>
        </div>
        <div class="telemetry-cell">
            <div class="telemetry-label">Throughput</div>
            <div class="telemetry-val-row">
                <p id="tps" style="color: var(--signal-approve-fg);">0.0</p>
                <svg id="tps-sparkline" width="66" height="22" viewBox="0 0 66 22" aria-label="Recent Risk Sparkline">
                    <rect x="2" y="14" width="6" height="8" rx="1" fill="#059669"/>
                    <rect x="11" y="10" width="6" height="12" rx="1" fill="#059669"/>
                    <rect x="20" y="6" width="6" height="16" rx="1" fill="#D97706"/>
                    <rect x="29" y="12" width="6" height="10" rx="1" fill="#059669"/>
                    <rect x="38" y="3" width="6" height="19" rx="1" fill="#DC2626"/>
                    <rect x="47" y="11" width="6" height="11" rx="1" fill="#059669"/>
                    <rect x="56" y="8" width="6" height="14" rx="1" fill="#D97706"/>
                </svg>
            </div>
        </div>
        <div class="telemetry-cell">
            <div class="telemetry-label">Scoring Latency</div>
            <div class="telemetry-val-row">
                <p id="avg-latency">3.8ms</p>
                <span class="telemetry-unit">p95</span>
            </div>
        </div>
    </section>

    <!-- Interactive Product Demo: Live Transaction Simulator -->
    <section class="workbench-strip" id="simulation-workbench" aria-label="Transaction Simulator">
        <div class="workbench-bar">
            <div>
                <span class="workbench-title">Transaction Simulator</span>
                <span class="workbench-subtitle">Dispatch a test transaction through the live scoring engine</span>
            </div>
            <button class="btn" id="btn-toggle-custom-sim" onclick="toggleCustomSimulator()">Custom transaction</button>
        </div>
        <div class="workbench-presets">
            <span style="font-size:12.5px; color:var(--text-secondary); margin-right:4px;">Test scenarios:</span>
            <button class="btn" id="btn-sim-clean" onclick="runLiveSimulation('CLEAN_DOMESTIC')">Domestic Purchase ($42.50)</button>
            <button class="btn" id="btn-sim-review" onclick="runLiveSimulation('AMOUNT_ANOMALY')">VPN + Unusual Hour ($195.00)</button>
            <button class="btn btn-danger" id="btn-sim-block" onclick="runLiveSimulation('TOR_IMPOSSIBLE_TRAVEL')">Tor Exit + High-Value Wire ($980.00)</button>
        </div>
        <div class="workbench-custom" id="workbench-custom-form">
            <div class="filter-group">
                <label for="sim-account">Account ID</label>
                <input type="text" id="sim-account" class="filter-input" value="acc_demo_01">
            </div>
            <div class="filter-group">
                <label for="sim-amount">Amount (USD)</label>
                <input type="number" id="sim-amount" class="filter-input" value="640.00" step="0.01">
            </div>
            <div class="filter-group">
                <label for="sim-channel">Payment rail</label>
                <select id="sim-channel" class="filter-select">
                    <option value="WIRE">Wire</option>
                    <option value="CREDIT">Credit card</option>
                    <option value="DEBIT">Debit card</option>
                    <option value="CHECK">Check</option>
                </select>
            </div>
            <div class="filter-group">
                <label for="sim-ip">Origin IP</label>
                <select id="sim-ip" class="filter-select">
                    <option value="185.220.101.1">185.220.101.1 (Tor Frankfurt)</option>
                    <option value="198.51.100.50">198.51.100.50 (VPN Amsterdam)</option>
                    <option value="192.0.2.1">192.0.2.1 (Domestic New York)</option>
                    <option value="203.0.113.10">203.0.113.10 (Domestic Mumbai)</option>
                </select>
            </div>
            <div class="filter-group">
                <label for="sim-city">City</label>
                <input type="text" id="sim-city" class="filter-input" value="Frankfurt">
            </div>
            <div class="filter-group">
                <label for="sim-country">Country code</label>
                <input type="text" id="sim-country" class="filter-input" value="DE">
            </div>
            <div class="filter-actions">
                <button class="btn btn-primary" id="btn-sim-custom-run" onclick="runLiveSimulation('CUSTOM')">Evaluate Transaction</button>
            </div>
        </div>
        <div class="sim-receipt" id="sim-receipt-banner" role="status">
            <span id="sim-receipt-text">Ready</span>
            <button class="btn" id="btn-sim-inspect" onclick="if(lastSimulatedTxId) openTransactionDetail(lastSimulatedTxId)">View details</button>
        </div>
    </section>

    <div class="main-layout">
        <div class="panel">
            <div class="panel-header">
                <h2>Transactions</h2>
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                    <button class="btn" id="btn-toggle-poll" onclick="toggleAutoRefresh()">Pause</button>
                    <button class="btn" id="btn-refresh" onclick="manualRefresh()">Refresh</button>
                    <button class="btn" id="btn-prev-page" onclick="changePage(-1)" disabled>Previous</button>
                    <span id="page-indicator" style="margin: 0 6px; font-size: 12.5px; color: var(--text-secondary);">Page 1 of 1</span>
                    <button class="btn" id="btn-next-page" onclick="changePage(1)" disabled>Next</button>
                </div>
            </div>

            <!-- Filter Bar -->
            <div class="filter-bar" id="filter-bar" role="region" aria-label="Transaction Filters">
                <div class="filter-group">
                    <label for="filter-action">Status</label>
                    <select id="filter-action" class="filter-select" onchange="applyFilters()">
                        <option value="ALL">All statuses</option>
                        <option value="APPROVE">Approved</option>
                        <option value="REVIEW_QUEUE">Review Queue</option>
                        <option value="BLOCK">Blocked</option>
                        <option value="QUARANTINED">Quarantined</option>
                        <option value="RELEASED">Released</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="filter-min-score">Min score</label>
                    <input type="number" id="filter-min-score" class="filter-input" min="0" max="100" value="0" placeholder="0">
                </div>
                <div class="filter-group">
                    <label for="filter-max-score">Max score</label>
                    <input type="number" id="filter-max-score" class="filter-input" min="0" max="100" value="100" placeholder="100">
                </div>
                <div class="filter-group">
                    <label for="filter-start-date">From date</label>
                    <input type="datetime-local" id="filter-start-date" class="filter-input">
                </div>
                <div class="filter-group">
                    <label for="filter-end-date">To date</label>
                    <input type="datetime-local" id="filter-end-date" class="filter-input">
                </div>
                <div class="filter-group">
                    <label for="filter-search">Search</label>
                    <input type="text" id="filter-search" class="filter-input" placeholder="Transaction or account ID">
                </div>
                <div class="filter-actions">
                    <button class="btn btn-primary" id="btn-apply-filters" onclick="applyFilters()">Apply</button>
                    <button class="btn" id="btn-reset-filters" onclick="resetFilters()">Reset</button>
                </div>
            </div>

            <div id="filter-error-banner" class="error-banner" role="alert">
                <span id="filter-error-text">Unable to load transactions.</span>
                <button class="btn btn-danger" onclick="manualRefresh()">Retry</button>
            </div>

            <div class="table-wrapper">
                <table class="txn-table" id="transactions-table">
                    <thead>
                        <tr>
                            <th>Transaction ID</th>
                            <th>Timestamp</th>
                            <th>Account</th>
                            <th class="num-col">Amount</th>
                            <th>Origin</th>
                            <th class="num-col">Risk Score</th>
                            <th>Signals</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="txn-table-body">
                        <tr class="skeleton-row"><td colspan="8"><span class="skeleton-line"></span></td></tr>
                        <tr class="skeleton-row"><td colspan="8"><span class="skeleton-line"></span></td></tr>
                        <tr class="skeleton-row"><td colspan="8"><span class="skeleton-line"></span></td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Footer with Terms of Service & Privacy Policy -->
    <footer class="inst-footer">
        <div>FraudGuard Risk Operations</div>
        <div class="legal-links">
            <button class="legal-link-btn" id="btn-open-tos" onclick="openLegalModal('tos')">Terms of Service</button>
            <button class="legal-link-btn" id="btn-open-privacy" onclick="openLegalModal('privacy')">Privacy Policy</button>
        </div>
    </footer>

    <!-- Legal Governance Modal -->
    <div id="legal-modal" class="legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-modal-title">
        <div class="legal-modal-card">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:10px; margin-bottom:12px;">
                <strong id="legal-modal-title" style="font-size:14px; font-weight:600;">Legal Document</strong>
                <button class="btn" onclick="closeLegalModal()">Close</button>
            </div>
            <pre id="legal-modal-content" class="raw-json" style="white-space:pre-wrap; font-family:var(--font-sans); font-size:13px; line-height:1.6; max-height:360px;"></pre>
        </div>
    </div>

    <!-- Backdrop for closing sidebar when clicking outside -->
    <div id="sidebar-backdrop" class="sidebar-backdrop" onclick="closeDetailSidebar()"></div>

    <!-- Slide-in Detail Drawer -->
    <aside id="detail-sidebar" class="detail-sidebar" aria-label="Transaction Detail View">
        <div class="sidebar-top">
            <div>
                <h3 id="detail-title" style="margin:0; font-size:15px; font-weight:600; color:var(--text-primary);">Transaction Details</h3>
                <span id="detail-subtitle" style="font-size:12px; color:var(--text-muted);"></span>
            </div>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn" id="btn-copy-id" onclick="copyCurrentTransactionId()">Copy ID</button>
                <button class="btn btn-primary" id="btn-export-json" onclick="exportCurrentTransactionJson()">Export JSON</button>
                <button class="btn" id="btn-close-sidebar" onclick="closeDetailSidebar()" aria-label="Close Sidebar">Close</button>
            </div>
        </div>
        <div id="detail-body">
            <div style="padding:20px;">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
                    <span class="spinner"></span>
                    <span style="font-size:12.5px; color:var(--text-muted);">Loading full forensic trace...</span>
                </div>
                <div class="skeleton-block"></div>
                <div class="skeleton-block"></div>
                <div class="skeleton-block"></div>
            </div>
        </div>
    </aside>

    <script>
        const FLAG_DESCRIPTIONS = __FLAG_EXPLANATIONS_JSON__;
        const TOS_DOC = __TOS_JSON__;
        const PRIVACY_DOC = __PRIVACY_JSON__;
        const CITY_COORDS = {
            "new york": { lat: 40.7128, lon: -74.0060 },
            "san francisco": { lat: 37.7749, lon: -122.4194 },
            "chicago": { lat: 41.8781, lon: -87.6298 },
            "boston": { lat: 42.3601, lon: -71.0589 },
            "washington": { lat: 38.9072, lon: -77.0369 },
            "pittsburgh": { lat: 40.4406, lon: -79.9959 },
            "mumbai": { lat: 19.0760, lon: 72.8777 },
            "delhi": { lat: 28.6139, lon: 77.2090 },
            "london": { lat: 51.5074, lon: -0.1278 },
            "amsterdam": { lat: 52.3676, lon: 4.9041 },
            "frankfurt": { lat: 50.1109, lon: 8.6821 },
            "zurich": { lat: 47.3769, lon: 8.5417 },
            "bucharest": { lat: 44.4268, lon: 26.1025 },
            "singapore": { lat: 1.3521, lon: 103.8198 }
        };

        let currentPage = 1;
        const pageSize = 12;
        let totalPages = 1;
        let activeTransaction = null;
        let selectedTxId = null;
        let lastSimulatedTxId = null;
        let autoRefreshEnabled = true;
        let pollTimer = null;

        function escapeHtml(val) {
            if (val === null || val === undefined) return '';
            return String(val)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function toggleTheme() {
            const root = document.documentElement;
            const current = root.getAttribute('data-theme') || 'light';
            const next = current === 'light' ? 'dark' : 'light';
            root.setAttribute('data-theme', next);
            const btn = document.getElementById('btn-theme-toggle');
            if (btn) {
                btn.innerText = next === 'light' ? 'Dark mode' : 'Light mode';
            }
        }

        function openLegalModal(docType) {
            const modal = document.getElementById('legal-modal');
            const title = document.getElementById('legal-modal-title');
            const content = document.getElementById('legal-modal-content');
            if (!modal || !title || !content) return;
            if (docType === 'tos') {
                title.innerText = 'Terms of Service';
                content.innerText = TOS_DOC;
            } else {
                title.innerText = 'Privacy & Data Governance Policy';
                content.innerText = PRIVACY_DOC;
            }
            modal.classList.add('open');
        }

        function closeLegalModal() {
            const modal = document.getElementById('legal-modal');
            if (modal) modal.classList.remove('open');
        }

        function toggleCustomSimulator() {
            const form = document.getElementById('workbench-custom-form');
            const btn = document.getElementById('btn-toggle-custom-sim');
            if (!form) return;
            const isOpen = form.classList.toggle('open');
            if (btn) {
                btn.innerText = isOpen ? 'Hide custom fields' : 'Custom transaction';
            }
        }

        function runLiveSimulation(presetName) {
            const receipt = document.getElementById('sim-receipt-banner');
            const receiptText = document.getElementById('sim-receipt-text');
            if (receipt && receiptText) {
                receipt.classList.add('visible');
                receiptText.innerText = 'Evaluating transaction...';
            }

            let payload = { preset: presetName };
            if (presetName === 'CUSTOM') {
                payload = {
                    preset: 'CUSTOM',
                    source_account: document.getElementById('sim-account').value || 'acc_demo_01',
                    amount: Number(document.getElementById('sim-amount').value || 100),
                    txn_type: document.getElementById('sim-channel').value || 'WIRE',
                    origin_ip: document.getElementById('sim-ip').value || '192.0.2.1',
                    transaction_city: document.getElementById('sim-city').value || 'New York',
                    transaction_country: document.getElementById('sim-country').value || 'US'
                };
            }

            fetch('/api/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(res => res.json().then(data => ({ ok: res.ok, data })))
                .then(({ ok, data }) => {
                    if (!ok || !data.result) {
                        throw new Error(data.message || data.error || 'Simulation failed');
                    }
                    const tx = data.result;
                    lastSimulatedTxId = tx.transaction_id;
                    const latEl = document.getElementById('avg-latency');
                    if (latEl && data.latency_ms !== undefined) {
                        latEl.innerText = `${data.latency_ms}ms`;
                    }
                    if (receipt && receiptText) {
                        receiptText.innerText = `Evaluated ${tx.transaction_id}: score ${tx.risk_score}/100, status ${formatActionDisplay(normalizeActionLabel(tx))} (${data.latency_ms}ms)`;
                    }
                    loadTransactions().then(() => {
                        openTransactionDetail(tx.transaction_id);
                    });
                })
                .catch(err => {
                    if (receipt && receiptText) {
                        receiptText.innerText = `Evaluation failed: ${err.message}`;
                    }
                });
        }

        function normalizeActionLabel(tx) {
            const rawStatus = String(tx.status || '').toUpperCase();
            const rawDecision = String(tx.decision || '').toUpperCase();
            if (rawStatus === 'RELEASED' || rawDecision === 'RELEASED') return 'RELEASED';
            if (rawStatus === 'QUARANTINED') return 'QUARANTINED';
            if (rawDecision === 'BLOCK' || rawStatus === 'BLOCK') return 'BLOCK';
            if (rawDecision === 'REVIEW_QUEUE' || rawDecision === 'PENDING_REVIEW' || rawStatus === 'PENDING_REVIEW' || rawStatus === 'REVIEW_QUEUE') {
                return 'REVIEW_QUEUE';
            }
            if (rawDecision === 'APPROVE' || rawDecision === 'ALLOW' || rawDecision === 'APPROVED' || rawStatus === 'APPROVED' || rawStatus === 'ALLOW') {
                return 'APPROVE';
            }
            return rawStatus || rawDecision || 'APPROVE';
        }

        function formatActionDisplay(code) {
            const map = {
                'APPROVE': 'Approved',
                'REVIEW_QUEUE': 'Review Queue',
                'BLOCK': 'Blocked',
                'QUARANTINED': 'Quarantined',
                'RELEASED': 'Released'
            };
            return map[code] || code;
        }

        function getGaugeColor(score) {
            const s = Math.max(0, Math.min(100, Number(score) || 0));
            if (s >= 80) return '#DC2626';
            if (s >= 40) return '#D97706';
            return '#059669';
        }

        function renderRiskGauge(score) {
            const clamped = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
            const color = getGaugeColor(clamped);
            const circumference = 2 * Math.PI * 34;
            const dashOffset = circumference - (clamped / 100) * circumference;
            return `
                <div class="gauge-container" data-score="${clamped}">
                    <div class="gauge-ring">
                        <svg width="80" height="80" viewBox="0 0 84 84">
                            <circle cx="42" cy="42" r="34" stroke="#E2E8F0" stroke-width="7" fill="none"></circle>
                            <circle cx="42" cy="42" r="34" stroke="${color}" stroke-width="7" fill="none"
                                stroke-dasharray="${circumference.toFixed(1)}"
                                stroke-dashoffset="${dashOffset.toFixed(1)}"
                                stroke-linecap="round"
                                transform="rotate(-90 42 42)"></circle>
                            <text x="42" y="47" text-anchor="middle" fill="currentColor" font-family="SFMono-Regular, Menlo, monospace" font-size="18" font-weight="600">${clamped}</text>
                        </svg>
                    </div>
                    <div style="flex:1;">
                        <div style="font-size:12px; color:var(--text-muted); font-weight:500;">Composite Risk Score (0 to 100)</div>
                        <div style="font-size:15px; font-weight:600; color:${color}; margin-top:2px;">
                            ${clamped >= 80 ? 'High Risk (Block & Quarantine)' : (clamped >= 40 ? 'Elevated Risk (Manual Review)' : 'Low Risk (Approved)')}
                        </div>
                        <div class="gauge-bar-track">
                            <div class="gauge-bar-fill" style="width:${clamped}%; background:${color};"></div>
                        </div>
                    </div>
                </div>
            `;
        }

        function resolveCoords(city, coordsObj) {
            if (coordsObj && typeof coordsObj.lat === 'number' && typeof coordsObj.lon === 'number') {
                return { lat: coordsObj.lat, lon: coordsObj.lon };
            }
            const key = String(city || 'new york').trim().toLowerCase();
            return CITY_COORDS[key] || { lat: 40.7128, lon: -74.0060 };
        }

        function projectLatLon(lat, lon, width, height) {
            const x = ((Number(lon) + 180) * (width / 360));
            const y = ((90 - Number(lat)) * (height / 180));
            return {
                x: Math.max(8, Math.min(width - 8, Number(x.toFixed(1)))),
                y: Math.max(8, Math.min(height - 8, Number(y.toFixed(1))))
            };
        }

        function renderOriginMapSvg(origin, loc) {
            const width = 360;
            const height = 160;
            const txCity = origin.city || loc.transaction_city || 'New York';
            const txCountry = origin.country || loc.transaction_country || 'US';
            const regCity = loc.account_registered_city || 'New York';
            const regCountry = loc.account_registered_country || 'US';

            const txCoords = resolveCoords(txCity, origin.coordinates);
            const regCoords = resolveCoords(regCity, null);

            const txPt = projectLatLon(txCoords.lat, txCoords.lon, width, height);
            const regPt = projectLatLon(regCoords.lat, regCoords.lon, width, height);

            const isAnomalous = Boolean(origin.is_tor || origin.is_vpn || loc.is_impossible_travel || loc.is_international);
            const markerColor = isAnomalous ? '#DC2626' : '#059669';
            const hasDiff = Math.abs(txPt.x - regPt.x) > 2 || Math.abs(txPt.y - regPt.y) > 2;

            return `
                <div class="origin-map-box" data-origin-lat="${txCoords.lat}" data-origin-lon="${txCoords.lon}">
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--text-secondary); margin-bottom:6px;">
                        <span>Origin vs. Registered Location</span>
                        <span class="mono-cell" style="color:${markerColor}; font-weight:600;">
                            ${escapeHtml(txCity)}, ${escapeHtml(txCountry)} (${Number(txCoords.lat).toFixed(2)}, ${Number(txCoords.lon).toFixed(2)})
                        </span>
                    </div>
                    <svg class="origin-map-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Transaction Origin Map">
                        <rect width="${width}" height="${height}" fill="#F1F5F9"/>
                        <line x1="0" y1="40" x2="360" y2="40" stroke="#E2E8F0" stroke-width="0.7"/>
                        <line x1="0" y1="80" x2="360" y2="80" stroke="#CBD5E1" stroke-width="0.8" stroke-dasharray="2 2"/>
                        <line x1="0" y1="120" x2="360" y2="120" stroke="#E2E8F0" stroke-width="0.7"/>
                        <line x1="90" y1="0" x2="90" y2="160" stroke="#E2E8F0" stroke-width="0.7"/>
                        <line x1="180" y1="0" x2="180" y2="160" stroke="#CBD5E1" stroke-width="0.8" stroke-dasharray="2 2"/>
                        <line x1="270" y1="0" x2="270" y2="160" stroke="#E2E8F0" stroke-width="0.7"/>
                        <path d="M25,25 L110,22 L120,65 L95,82 L75,70 L45,60 Z" fill="#E2E8F0" stroke="#94A3B8" stroke-width="0.7"/>
                        <path d="M92,86 L125,95 L118,142 L98,145 L90,112 Z" fill="#E2E8F0" stroke="#94A3B8" stroke-width="0.7"/>
                        <path d="M162,24 L218,20 L225,54 L175,58 L160,44 Z" fill="#E2E8F0" stroke="#94A3B8" stroke-width="0.7"/>
                        <path d="M168,62 L215,64 L220,122 L188,132 L166,95 Z" fill="#E2E8F0" stroke="#94A3B8" stroke-width="0.7"/>
                        <path d="M222,24 L318,22 L328,78 L280,92 L245,76 L224,52 Z" fill="#E2E8F0" stroke="#94A3B8" stroke-width="0.7"/>
                        <path d="M278,108 L324,106 L328,138 L282,140 Z" fill="#E2E8F0" stroke="#94A3B8" stroke-width="0.7"/>
                        ${hasDiff ? `
                            <line x1="${regPt.x}" y1="${regPt.y}" x2="${txPt.x}" y2="${txPt.y}"
                                stroke="${markerColor}" stroke-width="1.5" stroke-dasharray="4 3" />
                            <circle cx="${regPt.x}" cy="${regPt.y}" r="3.5" fill="#2563EB" stroke="#FFFFFF" stroke-width="1"/>
                            <text x="${ Math.min(285, regPt.x + 6) }" y="${ Math.max(12, regPt.y - 4) }" fill="#1E40AF" font-size="8.5" font-weight="600">
                                Home: ${escapeHtml(regCity)}
                            </text>
                        ` : ''}
                        <circle cx="${txPt.x}" cy="${txPt.y}" r="8" fill="${markerColor}" fill-opacity="0.2"/>
                        <circle cx="${txPt.x}" cy="${txPt.y}" r="4" fill="${markerColor}" stroke="#FFFFFF" stroke-width="1.2"/>
                        <text x="${ Math.min(275, txPt.x + 7) }" y="${ Math.min(152, txPt.y + 4) }" fill="#0F172A" font-size="8.5" font-weight="600">
                            Origin: ${escapeHtml(txCity)} (${escapeHtml(txCountry)})
                        </text>
                    </svg>
                </div>
            `;
        }

        function updateSparkline(items) {
            const svg = document.getElementById('tps-sparkline');
            if (!svg || !Array.isArray(items) || items.length === 0) return;
            const slice = items.slice(0, 7).reverse();
            const bars = slice.map((tx, idx) => {
                const s = Math.max(10, Math.min(100, Math.round(Number(tx.risk_score !== undefined ? tx.risk_score : (tx.total_risk || 0) * 100))));
                const h = Math.max(4, Math.round((s / 100) * 20));
                const y = 22 - h;
                const x = 2 + idx * 9;
                const fill = getGaugeColor(s);
                return `<rect x="${x}" y="${y}" width="6" height="${h}" rx="1" fill="${fill}"/>`;
            }).join('');
            svg.innerHTML = bars;
        }

        function renderSkeletonRows(count = 6) {
            return Array.from({ length: count }).map(() => `
                <tr class="skeleton-row">
                    <td><span class="skeleton-line" style="width:90px;"></span></td>
                    <td><span class="skeleton-line" style="width:130px;"></span></td>
                    <td><span class="skeleton-line" style="width:75px;"></span></td>
                    <td><span class="skeleton-line" style="width:60px; margin-left:auto;"></span></td>
                    <td><span class="skeleton-line" style="width:100px;"></span></td>
                    <td><span class="skeleton-line" style="width:50px; margin-left:auto;"></span></td>
                    <td><span class="skeleton-line" style="width:110px;"></span></td>
                    <td><span class="skeleton-line" style="width:80px;"></span></td>
                </tr>
            `).join('');
        }

        function getFilterQueryParams() {
            const params = new URLSearchParams();
            params.set('page', String(currentPage));
            params.set('limit', String(pageSize));

            const actionEl = document.getElementById('filter-action');
            const minEl = document.getElementById('filter-min-score');
            const maxEl = document.getElementById('filter-max-score');
            const startEl = document.getElementById('filter-start-date');
            const endEl = document.getElementById('filter-end-date');
            const searchEl = document.getElementById('filter-search');

            if (actionEl && actionEl.value && actionEl.value !== 'ALL') {
                params.set('action', actionEl.value);
            }
            if (minEl && minEl.value !== '' && Number(minEl.value) > 0) {
                params.set('min_score', minEl.value);
            }
            if (maxEl && maxEl.value !== '' && Number(maxEl.value) < 100) {
                params.set('max_score', maxEl.value);
            }
            if (startEl && startEl.value) {
                params.set('start_date', startEl.value);
            }
            if (endEl && endEl.value) {
                params.set('end_date', endEl.value);
            }
            if (searchEl && searchEl.value.trim() !== '') {
                params.set('search', searchEl.value.trim());
            }
            return params.toString();
        }

        function loadTransactions(options = {}) {
            const applyBtn = document.getElementById('btn-apply-filters');
            const refreshBtn = document.getElementById('btn-refresh');
            const errorBanner = document.getElementById('filter-error-banner');
            const errorText = document.getElementById('filter-error-text');
            const tbody = document.getElementById('txn-table-body');

            if (options.fromFilter && applyBtn) {
                applyBtn.disabled = true;
                applyBtn.innerText = 'Applying...';
                if (tbody) tbody.innerHTML = renderSkeletonRows(6);
            }
            if (options.fromManual && refreshBtn) {
                refreshBtn.disabled = true;
                refreshBtn.innerText = 'Refreshing...';
            }

            return fetch(`/api/transactions?${getFilterQueryParams()}`)
                .then(res => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                })
                .then(data => {
                    if (errorBanner) errorBanner.classList.remove('visible');

                    document.getElementById('sent-count').innerText = data.total_count ?? 0;
                    document.getElementById('fraud-count').innerText = data.flagged_count ?? 0;
                    document.getElementById('quarantine-count').innerText = data.quarantine_count ?? 0;
                    document.getElementById('fraud-rate').innerText = (data.fraud_rate_pct ?? 0) + '%';
                    document.getElementById('tps').innerText = data.tps !== undefined ? data.tps : '0.0';

                    totalPages = Math.max(1, data.total_pages || 1);
                    currentPage = Math.min(currentPage, totalPages);
                    document.getElementById('page-indicator').innerText = `Page ${data.page || 1} of ${totalPages}`;

                    const prevBtn = document.getElementById('btn-prev-page');
                    const nextBtn = document.getElementById('btn-next-page');
                    if (prevBtn) prevBtn.disabled = (currentPage <= 1);
                    if (nextBtn) nextBtn.disabled = (currentPage >= totalPages);

                    const items = data.items || [];
                    updateSparkline(items);

                    if (items.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:24px;">No matching transactions found.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = items.map(tx => {
                        const payload = tx.original_payload || {};
                        const txId = String(tx.transaction_id || 'unknown');
                        const acct = tx.account_id || tx.source_account || payload.account_id || payload.source_account || 'acc_0';
                        const amt = Number(tx.amount !== undefined ? tx.amount : (payload.amount || 0)).toFixed(2);
                        const orig = tx.origin || payload.origin || {};
                        const origLabel = orig.city ? `${orig.city}, ${orig.country || ''}` : 'Domestic';
                        const score = Math.round(Number(tx.risk_score !== undefined ? tx.risk_score : (tx.total_risk || 0) * 100));
                        const flags = tx.flags || tx.triggered_rules || tx.reason_codes || payload.flags || [];
                        const flagsHtml = flags.length
                            ? flags.map(f => `<span class="flag-chip">${escapeHtml(f)}</span>`).join('')
                            : '<span style="color:var(--text-muted); font-size:12px;">None</span>';
                        const normAction = normalizeActionLabel(tx);
                        const isSelected = (selectedTxId && selectedTxId === txId);
                        return `
                            <tr class="txn-row ${isSelected ? 'selected-row' : ''}"
                                tabindex="0"
                                role="button"
                                data-tx-id="${escapeHtml(txId)}"
                                onclick="openTransactionDetail(this.dataset.txId)"
                                onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openTransactionDetail(this.dataset.txId);}">
                                <td class="mono-cell" style="font-weight:500; color:var(--accent-link);">${escapeHtml(txId)}</td>
                                <td class="mono-cell" style="color:var(--text-secondary);">${escapeHtml(tx.timestamp || tx.quarantine_ts || payload.timestamp || '')}</td>
                                <td class="mono-cell">${escapeHtml(acct)}</td>
                                <td class="mono-cell num-col" style="font-weight:500;">$${escapeHtml(amt)}</td>
                                <td>${escapeHtml(origLabel)}</td>
                                <td class="mono-cell num-col" style="font-weight:600; color:${getGaugeColor(score)};">${score}/100</td>
                                <td>${flagsHtml}</td>
                                <td><span class="status-pill status-${escapeHtml(normAction)}">${escapeHtml(formatActionDisplay(normAction))}</span></td>
                            </tr>
                        `;
                    }).join('');
                })
                .catch(err => {
                    if (errorBanner && errorText) {
                        errorText.innerText = `Unable to load transactions (${err.message || 'Network error'}).`;
                        errorBanner.classList.add('visible');
                    }
                })
                .finally(() => {
                    if (applyBtn) {
                        applyBtn.disabled = false;
                        applyBtn.innerText = 'Apply';
                    }
                    if (refreshBtn) {
                        refreshBtn.disabled = false;
                        refreshBtn.innerText = 'Refresh';
                    }
                });
        }

        function applyFilters() {
            currentPage = 1;
            loadTransactions({ fromFilter: true });
        }

        function resetFilters() {
            const resetBtn = document.getElementById('btn-reset-filters');
            if (resetBtn) {
                resetBtn.disabled = true;
                resetBtn.innerText = 'Resetting...';
            }
            document.getElementById('filter-action').value = 'ALL';
            document.getElementById('filter-min-score').value = '0';
            document.getElementById('filter-max-score').value = '100';
            document.getElementById('filter-start-date').value = '';
            document.getElementById('filter-end-date').value = '';
            document.getElementById('filter-search').value = '';
            currentPage = 1;
            loadTransactions({ fromFilter: true }).finally(() => {
                if (resetBtn) {
                    resetBtn.disabled = false;
                    resetBtn.innerText = 'Reset';
                }
            });
        }

        function manualRefresh() {
            loadTransactions({ fromManual: true });
        }

        function toggleAutoRefresh() {
            autoRefreshEnabled = !autoRefreshEnabled;
            const btn = document.getElementById('btn-toggle-poll');
            const badge = document.getElementById('live-status-badge');
            const badgeText = document.getElementById('live-status-text');
            if (autoRefreshEnabled) {
                if (btn) btn.innerText = 'Pause';
                if (badge) badge.classList.remove('paused');
                if (badgeText) badgeText.innerText = 'Live';
                loadTransactions();
            } else {
                if (btn) btn.innerText = 'Resume';
                if (badge) badge.classList.add('paused');
                if (badgeText) badgeText.innerText = 'Paused';
            }
        }

        function changePage(delta) {
            const next = currentPage + delta;
            if (next >= 1 && next <= totalPages) {
                currentPage = next;
                loadTransactions({ fromManual: true });
            }
        }

        function openTransactionDetail(txId) {
            if (!txId) return;
            selectedTxId = String(txId);

            document.querySelectorAll('#txn-table-body tr.txn-row').forEach(row => {
                if (row.dataset.txId === selectedTxId) {
                    row.classList.add('selected-row');
                } else {
                    row.classList.remove('selected-row');
                }
            });

            const sidebar = document.getElementById('detail-sidebar');
            const backdrop = document.getElementById('sidebar-backdrop');
            const body = document.getElementById('detail-body');

            sidebar.classList.add('open');
            backdrop.classList.add('open');
            document.getElementById('detail-title').innerText = `Transaction ${txId}`;
            document.getElementById('detail-subtitle').innerText = 'Loading transaction details...';
            body.innerHTML = `
                <div style="padding:16px;">
                    <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
                        <span class="spinner"></span>
                        <span style="font-size:12.5px; color:var(--text-muted);">Loading full forensic trace...</span>
                    </div>
                    <div class="skeleton-block"></div>
                    <div class="skeleton-block"></div>
                    <div class="skeleton-block"></div>
                </div>
            `;

            if (window.innerWidth <= 600 && sidebar.scrollIntoView) {
                sidebar.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            fetch(`/transaction/${encodeURIComponent(txId)}`)
                .then(res => {
                    if (!res.ok) {
                        throw new Error(res.status === 404 ? `Transaction "${txId}" not found (HTTP 404)` : `Server returned HTTP ${res.status}`);
                    }
                    return res.json();
                })
                .then(tx => {
                    activeTransaction = tx;
                    renderSidebarContent(tx);
                })
                .catch(err => {
                    document.getElementById('detail-subtitle').innerText = 'Unable to load transaction';
                    body.innerHTML = `
                        <div class="detail-section" style="border-color:var(--signal-block-bd);">
                            <h4 style="color:var(--signal-block-fg);">Unable to Load Transaction</h4>
                            <p style="font-size:12.5px; color:var(--text-primary); margin:6px 0 12px 0;">${escapeHtml(err.message || 'Unknown error')}</p>
                            <button class="btn btn-primary" data-tx-id="${escapeHtml(txId)}" onclick="openTransactionDetail(this.dataset.txId)">Retry</button>
                        </div>
                    `;
                });
        }

        function closeDetailSidebar() {
            document.getElementById('detail-sidebar').classList.remove('open');
            document.getElementById('sidebar-backdrop').classList.remove('open');
            if (selectedTxId) {
                const row = document.querySelector(`#txn-table-body tr.txn-row[data-tx-id="${CSS && CSS.escape ? CSS.escape(selectedTxId) : selectedTxId}"]`);
                if (row && row.focus) {
                    row.focus();
                    return;
                }
            }
            const tbl = document.getElementById('transactions-table');
            if (tbl && tbl.focus) tbl.focus();
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeDetailSidebar();
                closeLegalModal();
            }
        });

        function fallbackCopyText(text) {
            try {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.left = '-9999px';
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                const ok = document.execCommand('copy');
                document.body.removeChild(ta);
                return ok;
            } catch (e) {
                return false;
            }
        }

        function copyCurrentTransactionId() {
            const btn = document.getElementById('btn-copy-id');
            if (!activeTransaction || !btn) return;
            const id = String(activeTransaction.transaction_id || '');
            btn.disabled = true;
            btn.innerText = 'Copying...';

            const finish = (ok) => {
                btn.disabled = false;
                btn.innerText = ok ? 'Copied' : 'Copy failed';
                setTimeout(() => { btn.innerText = 'Copy ID'; }, 1400);
            };

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(id)
                    .then(() => finish(true))
                    .catch(() => finish(fallbackCopyText(id)));
            } else {
                finish(fallbackCopyText(id));
            }
        }

        function exportCurrentTransactionJson() {
            const btn = document.getElementById('btn-export-json');
            if (!activeTransaction || !btn) return;
            try {
                btn.disabled = true;
                btn.innerText = 'Exporting...';
                const txId = activeTransaction.transaction_id || 'export';
                const jsonStr = JSON.stringify(activeTransaction, null, 2);
                const blob = new Blob([jsonStr], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `transaction_${txId}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                btn.innerText = 'Exported';
            } catch (err) {
                btn.innerText = 'Export failed';
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerText = 'Export JSON';
                }, 1400);
            }
        }

        function releaseQuarantinedTransaction(txId) {
            const btn = document.getElementById('btn-release-quarantine');
            const keyInput = document.getElementById('release-api-key');
            const notesInput = document.getElementById('release-notes');
            const statusMsg = document.getElementById('release-status-msg');
            if (!btn || !txId) return;

            const apiKey = (keyInput && keyInput.value.trim()) || 'fg-analyst-demo-key-2026';
            const notes = (notesInput && notesInput.value.trim()) || 'Verified legitimate by analyst';

            btn.disabled = true;
            btn.innerText = 'Releasing...';
            if (statusMsg) {
                statusMsg.style.color = 'var(--text-secondary)';
                statusMsg.innerText = 'Submitting release authorization...';
            }

            fetch('/release', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': apiKey
                },
                body: JSON.stringify({
                    transaction_id: txId,
                    analyst_notes: notes
                })
            })
                .then(res => res.json().then(data => ({ ok: res.ok, status: res.status, data })))
                .then(({ ok, status, data }) => {
                    if (!ok) {
                        throw new Error(data.message || data.error || `HTTP ${status}`);
                    }
                    if (statusMsg) {
                        statusMsg.style.color = 'var(--signal-approve-fg)';
                        statusMsg.innerText = 'Transaction released from quarantine.';
                    }
                    loadTransactions();
                    setTimeout(() => openTransactionDetail(txId), 400);
                })
                .catch(err => {
                    btn.disabled = false;
                    btn.innerText = 'Release Transaction';
                    if (statusMsg) {
                        statusMsg.style.color = 'var(--signal-block-fg)';
                        statusMsg.innerText = `Release failed: ${err.message}`;
                    }
                });
        }

        function formatHolderName(rawName) {
            if (!rawName) return 'Verified Account Holder';
            const s = String(rawName);
            if (s.toUpperCase().startsWith('DEMO_')) {
                return 'Profile ' + s.slice(5);
            }
            return s;
        }

        function renderSidebarContent(tx) {
            const payload = tx.original_payload || tx;
            const score = Math.round(Number(tx.risk_score !== undefined ? tx.risk_score : (tx.total_risk || 0) * 100));
            const flags = tx.flags || tx.triggered_rules || tx.reason_codes || payload.flags || [];
            const origin = tx.origin || payload.origin || {};
            const tb = tx.traceback || payload.traceback || {};
            const loc = tx.location_check || payload.location_check || {};
            const timeA = tx.time_analysis || payload.time_analysis || {};
            const pii = tx.pii_enrichment || payload.pii_enrichment || {};
            const history5 = tx.account_history_last_5 || [];
            const normAction = normalizeActionLabel(tx);
            const isQuarantined = (String(tx.status || '').toUpperCase() === 'QUARANTINED');

            const flagsHtml = flags.length
                ? flags.map(f => `
                    <div style="margin-bottom:6px;">
                        <span class="flag-chip">${escapeHtml(f)}</span>
                        <span style="font-size:12px; color:var(--text-secondary);">${escapeHtml(FLAG_DESCRIPTIONS[f] || 'Signal threshold exceeded.')}</span>
                    </div>`).join('')
                : '<div style="font-size:12.5px; color:var(--signal-approve-fg);">No risk signals triggered.</div>';

            const historyRows = history5.length
                ? history5.map(h => {
                    const hScore = Math.round(Number(h.risk_score !== undefined ? h.risk_score : (h.total_risk || 0) * 100));
                    const hAction = normalizeActionLabel(h);
                    return `
                        <tr>
                            <td class="mono-cell" style="font-weight:500; color:var(--accent-link);">${escapeHtml(h.transaction_id || '')}</td>
                            <td class="mono-cell">${escapeHtml(h.timestamp || h.quarantine_ts || '')}</td>
                            <td class="mono-cell">$${escapeHtml(Number(h.amount || 0).toFixed(2))}</td>
                            <td class="mono-cell" style="font-weight:600; color:${getGaugeColor(hScore)};">${hScore}</td>
                            <td><span class="status-pill status-${escapeHtml(hAction)}">${escapeHtml(formatActionDisplay(hAction))}</span></td>
                        </tr>`;
                }).join('')
                : '<tr><td colspan="5" style="color:var(--text-muted);">No prior transactions for this account.</td></tr>';

            document.getElementById('detail-subtitle').innerText = `${formatActionDisplay(normAction)} | ${tx.timestamp || tx.quarantine_ts || payload.timestamp || ''}`;

            const quarantineReleaseHtml = isQuarantined ? `
                <div class="detail-section" style="border-color:var(--signal-quarantine-bd);">
                    <h4 style="color:var(--signal-quarantine-fg);">Quarantine Release</h4>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px;">
                        <div>
                            <label style="font-size:11.5px; color:var(--text-secondary); display:block; margin-bottom:3px;">Authorization key</label>
                            <input type="password" id="release-api-key" class="filter-input" value="fg-analyst-demo-key-2026">
                        </div>
                        <div>
                            <label style="font-size:11.5px; color:var(--text-secondary); display:block; margin-bottom:3px;">Review notes</label>
                            <input type="text" id="release-notes" class="filter-input" value="Verified legitimate by analyst">
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                        <button class="btn btn-quarantine" id="btn-release-quarantine" data-tx-id="${escapeHtml(tx.transaction_id || '')}" onclick="releaseQuarantinedTransaction(this.dataset.txId)">
                            Release Transaction
                        </button>
                        <span id="release-status-msg" style="font-size:12px; color:var(--text-muted);">Requires operator authorization</span>
                    </div>
                </div>
            ` : '';

            document.getElementById('detail-body').innerHTML = `
                ${renderRiskGauge(score)}

                <div class="detail-section">
                    <h4>Overview</h4>
                    <div class="kv-grid">
                        <div><span class="kv-label">Transaction ID</span><br><span class="kv-val-mono">${escapeHtml(tx.transaction_id || '')}</span></div>
                        <div>
                            <span class="kv-label">Status</span><br>
                            <span class="status-pill status-${escapeHtml(normAction)}">${escapeHtml(formatActionDisplay(normAction))}</span>
                            ${isQuarantined ? '<span class="status-pill status-BLOCK" style="margin-left:4px;">Blocked</span>' : ''}
                        </div>
                        <div><span class="kv-label">Account ID</span><br><span class="kv-val-mono">${escapeHtml(tx.account_id || payload.account_id || payload.source_account || '')}</span></div>
                        <div><span class="kv-label">Amount</span><br><span class="kv-val-mono">$${escapeHtml(Number(payload.amount || tx.amount || 0).toFixed(2))}</span></div>
                        <div><span class="kv-label">Counterparty</span><br><span class="kv-val">${escapeHtml(payload.merchant || payload.destination_account || 'Standard Transfer')}</span></div>
                        <div><span class="kv-label">Payment Rail</span><br><span class="kv-val">${escapeHtml(payload.merchant_category || payload.txn_type || 'Standard')}</span></div>
                    </div>
                </div>

                ${quarantineReleaseHtml}

                <div class="detail-section">
                    <h4>Risk Signals (${flags.length})</h4>
                    ${flagsHtml}
                </div>

                <div class="detail-section">
                    <h4>Network &amp; Origin</h4>
                    <div class="kv-grid">
                        <div><span class="kv-label">IP Address</span><br><span class="kv-val-mono">${escapeHtml(origin.ip_address || 'Not recorded')}</span></div>
                        <div><span class="kv-label">Location</span><br><span class="kv-val">${escapeHtml(origin.city || 'Domestic')}, ${escapeHtml(origin.country || 'US')}</span></div>
                        <div><span class="kv-label">Network Provider</span><br><span class="kv-val">${escapeHtml(origin.isp || 'Standard Carrier')}</span></div>
                        <div><span class="kv-label">Connection Type</span><br><span class="kv-val">${escapeHtml(origin.connection_type || 'Broadband')}</span></div>
                        <div><span class="kv-label">VPN or Proxy</span><br><span class="kv-val">${origin.is_vpn ? 'Yes (VPN)' : (origin.is_proxy ? 'Yes (Proxy)' : 'No')}</span></div>
                        <div><span class="kv-label">Tor Exit Node</span><br><span class="kv-val" style="color:${origin.is_tor ? 'var(--signal-block-fg)' : 'inherit'};">${origin.is_tor ? 'Yes (Tor)' : 'No'}</span></div>
                    </div>
                    ${renderOriginMapSvg(origin, loc)}
                </div>

                <div class="detail-section">
                    <h4>Account Activity (Last 5)</h4>
                    <div class="kv-grid" style="margin-bottom:8px;">
                        <div><span class="kv-label">Prior Transactions</span><br><span class="kv-val-mono">${escapeHtml(tb.account_transaction_count ?? 1)}</span></div>
                        <div><span class="kv-label">Historical Risk Avg</span><br><span class="kv-val-mono">${escapeHtml(tb.chain_risk_score ?? 0)}</span></div>
                        <div><span class="kv-label">Velocity (1h / 24h)</span><br><span class="kv-val-mono">${escapeHtml(tb.velocity_1hr ?? 1)} / ${escapeHtml(tb.velocity_24hr ?? 1)}</span></div>
                        <div><span class="kv-label">Amount Variance</span><br><span class="kv-val-mono">${escapeHtml(tb.amount_delta_pct ?? 0)}%</span></div>
                    </div>
                    <table class="mini-table">
                        <thead><tr><th>Transaction</th><th>Timestamp</th><th>Amount</th><th>Score</th><th>Status</th></tr></thead>
                        <tbody>${historyRows}</tbody>
                    </table>
                </div>

                <div class="detail-section">
                    <h4>Location &amp; Timing</h4>
                    <div class="kv-grid">
                        <div><span class="kv-label">Registered Location</span><br><span class="kv-val">${escapeHtml(loc.account_registered_city || 'New York')}, ${escapeHtml(loc.account_registered_country || 'US')}</span></div>
                        <div><span class="kv-label">Transaction Location</span><br><span class="kv-val">${escapeHtml(loc.transaction_city || 'New York')}, ${escapeHtml(loc.transaction_country || 'US')}</span></div>
                        <div><span class="kv-label">Distance</span><br><span class="kv-val-mono">${escapeHtml(loc.distance_km ?? 0)} km</span></div>
                        <div><span class="kv-label">Travel Speed</span><br><span class="kv-val-mono">${escapeHtml(loc.travel_speed_kmh ?? 0)} km/h</span></div>
                        <div><span class="kv-label">Impossible Travel</span><br><span class="kv-val" style="color:${loc.is_impossible_travel ? 'var(--signal-block-fg)' : 'inherit'};">${loc.is_impossible_travel ? 'Yes (Blocked)' : 'No'}</span></div>
                        <div><span class="kv-label">Local Time Window</span><br><span class="kv-val">Hour ${escapeHtml(timeA.transaction_hour ?? 12)} (${timeA.is_night_transaction ? 'Overnight' : 'Daytime'})</span></div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Customer Verification <span class="directory-badge">Verified Directory</span></h4>
                    <div class="kv-grid">
                        <div><span class="kv-label">Account holder</span><br><span class="kv-val">${escapeHtml(formatHolderName(pii.account_holder_name))}</span></div>
                        <div><span class="kv-label">Account tenure</span><br><span class="kv-val-mono">${escapeHtml(pii.account_age_days ?? 0)} days</span></div>
                        <div><span class="kv-label">Phone verification</span><br><span class="kv-val">${pii.linked_phone_verified !== undefined ? (pii.linked_phone_verified ? 'Verified' : 'Unverified') : 'Verified'}</span></div>
                        <div><span class="kv-label">Location consistency</span><br><span class="kv-val">${pii.location_matches_transaction !== undefined ? (pii.location_matches_transaction ? 'Consistent' : 'Mismatch') : 'Consistent'}</span></div>
                    </div>
                </div>

                <details class="detail-section">
                    <summary style="cursor:pointer; font-size:12.5px; font-weight:600; color:var(--text-primary);">Raw Event JSON</summary>
                    <pre class="raw-json">${escapeHtml(JSON.stringify(tx, null, 2))}</pre>
                </details>
            `;
        }

        loadTransactions();
        pollTimer = setInterval(() => {
            if (autoRefreshEnabled) {
                loadTransactions();
            }
        }, 1500);
    </script>
</body>
</html>
""".replace("__FLAG_EXPLANATIONS_JSON__", json.dumps(FLAG_EXPLANATIONS)).replace("__TOS_JSON__", json.dumps(TOS_TEXT)).replace("__PRIVACY_JSON__", json.dumps(PRIVACY_TEXT))


def _load_json_file(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _enrich_quarantine_record(rec):
    """Ensure top-level convenience fields are populated from original_payload when present."""
    item = dict(rec)
    payload = item.get("original_payload")
    if isinstance(payload, dict):
        if "timestamp" not in item or not item.get("timestamp"):
            item["timestamp"] = payload.get("timestamp") or item.get("quarantine_ts") or ""
        if "amount" not in item and "amount" in payload:
            item["amount"] = payload.get("amount")
        if "account_id" not in item or not item.get("account_id"):
            item["account_id"] = payload.get("account_id") or payload.get("source_account") or "unknown"
        for field in ("origin", "traceback", "location_check", "time_analysis", "pii_enrichment", "merchant", "merchant_category"):
            if field not in item and field in payload:
                item[field] = payload[field]
    return item


def get_combined_records():
    """
    Return merged records across main audit log and quarantine log, newest first.
    Supports cloud persistence when enabled with graceful fallback to local JSON files.
    """
    main_records = []
    quarantine_records = []

    if os.environ.get("USE_AWS_DYNAMODB", "").lower() == "true":
        try:
            from src.db_client import DBClient, _from_dynamodb_safe
            db = DBClient(fallback_path=MAIN_LOG_FILE, quarantine_fallback_path=QUARANTINE_LOG_FILE)
            if getattr(db, "use_dynamodb", False):
                resp_main = db.main_table.scan(Limit=500)
                main_records = [_from_dynamodb_safe(x) for x in resp_main.get("Items", [])]
                if db.quarantine_table is not None:
                    resp_q = db.quarantine_table.scan(Limit=500)
                    quarantine_records = [_from_dynamodb_safe(x) for x in resp_q.get("Items", [])]
        except Exception:
            main_records = []
            quarantine_records = []

    if not main_records:
        main_records = _load_json_file(MAIN_LOG_FILE)
    if not quarantine_records:
        quarantine_records = _load_json_file(QUARANTINE_LOG_FILE)

    enriched_quarantine = [_enrich_quarantine_record(q) for q in quarantine_records]
    combined = list(enriched_quarantine) + list(main_records)
    combined.sort(
        key=lambda r: r.get("timestamp") or r.get("quarantine_ts") or r.get("_ts") or "",
        reverse=True
    )
    return combined, main_records, enriched_quarantine


def calculate_live_tps(combined):
    """Calculate dynamic throughput (TPS) from telemetry file or recent transaction timestamps."""
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as tf:
                tele = json.load(tf)
                if isinstance(tele, dict) and tele.get("tps") is not None:
                    return round(float(tele["tps"]), 1)
        except Exception:
            pass

    if not combined:
        return 0.0

    parsed_times = []
    for r in combined[:25]:
        ts_str = r.get("timestamp") or r.get("quarantine_ts") or r.get("_ts")
        if not ts_str or not isinstance(ts_str, str):
            continue
        try:
            clean = ts_str.replace("Z", "+00:00")
            parsed_times.append(datetime.fromisoformat(clean).timestamp())
        except Exception:
            continue

    if len(parsed_times) >= 2:
        span = max(parsed_times) - min(parsed_times)
        if span > 0:
            rate = len(parsed_times) / span
            return round(max(0.1, min(500.0, rate)), 1)
    return round(float(min(len(combined), 10)), 1)


def _safe_int(val, default, min_val=None, max_val=None):
    try:
        res = int(val)
    except (ValueError, TypeError):
        res = default
    if min_val is not None:
        res = max(min_val, res)
    if max_val is not None:
        res = min(max_val, res)
    return res


def _safe_float(val, default, min_val=None, max_val=None):
    try:
        res = float(val)
    except (ValueError, TypeError):
        res = default
    if min_val is not None:
        res = max(min_val, res)
    if max_val is not None:
        res = min(max_val, res)
    return res


def _normalize_record_action(r):
    status = str(r.get("status") or "").upper()
    decision = str(r.get("decision") or "").upper()
    if status == "RELEASED" or decision == "RELEASED":
        return "RELEASED"
    if status == "QUARANTINED":
        return "QUARANTINED"
    if decision == "BLOCK" or status == "BLOCK":
        return "BLOCK"
    if decision in ("REVIEW_QUEUE", "PENDING_REVIEW") or status in ("REVIEW_QUEUE", "PENDING_REVIEW"):
        return "REVIEW_QUEUE"
    if decision in ("APPROVE", "ALLOW", "APPROVED") or status in ("APPROVE", "ALLOW", "APPROVED"):
        return "APPROVE"
    return status or decision or "APPROVE"


def _record_risk_score(r):
    if r.get("risk_score") is not None:
        return _safe_float(r.get("risk_score"), 0.0)
    if r.get("total_risk") is not None:
        return _safe_float(r.get("total_risk"), 0.0) * 100.0
    return 0.0


def _filter_records(records, query):
    action_filter = (query.get("action", ["ALL"])[0] or "ALL").strip().upper()
    min_score = _safe_float(query.get("min_score", ["0"])[0], 0.0, 0.0, 100.0)
    max_score = _safe_float(query.get("max_score", ["100"])[0], 100.0, 0.0, 100.0)
    start_date = (query.get("start_date", [""])[0] or "").strip()
    end_date = (query.get("end_date", [""])[0] or "").strip()
    search_term = (query.get("search", [""])[0] or "").strip().lower()

    filtered = []
    for r in records:
        norm_action = _normalize_record_action(r)
        raw_status = str(r.get("status") or "").upper()
        raw_decision = str(r.get("decision") or "").upper()

        if action_filter and action_filter != "ALL":
            if action_filter == "BLOCK":
                if norm_action not in ("BLOCK", "QUARANTINED") and raw_decision != "BLOCK":
                    continue
            elif action_filter == "QUARANTINED":
                if raw_status != "QUARANTINED" and norm_action != "QUARANTINED":
                    continue
            elif norm_action != action_filter:
                continue

        score = _record_risk_score(r)
        if score < min_score or score > max_score:
            continue

        ts = str(r.get("timestamp") or r.get("quarantine_ts") or "")
        if start_date and ts and ts < start_date:
            continue
        if end_date and ts and ts[:len(end_date)] > end_date:
            continue

        if search_term:
            payload = r.get("original_payload") or {}
            tx_id = str(r.get("transaction_id") or "").lower()
            acct = str(r.get("account_id") or r.get("source_account") or payload.get("account_id") or payload.get("source_account") or "").lower()
            merch = str(r.get("merchant") or payload.get("merchant") or "").lower()
            if search_term not in tx_id and search_term not in acct and search_term not in merch:
                continue

        filtered.append(r)
    return filtered


class TelemetryHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload, extra_headers=None):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/tos":
            self._send_json(200, {"title": "Terms of Service", "document": TOS_TEXT})
            return

        if path == "/privacy":
            self._send_json(200, {"title": "Privacy & Data Governance Policy", "document": PRIVACY_TEXT})
            return

        if path == "/api/telemetry":
            combined, main_records, quarantine_records = get_combined_records()
            if os.path.exists(TELEMETRY_FILE):
                try:
                    with open(TELEMETRY_FILE, "r", encoding="utf-8") as tf:
                        tele = json.load(tf)
                except Exception:
                    tele = {}
            else:
                tele = {}
            total = len(combined) or tele.get("sent_count", 0)
            flagged = sum(
                1 for r in combined
                if (r.get("decision") in ("REVIEW_QUEUE", "BLOCK") or r.get("status") in ("QUARANTINED", "PENDING_REVIEW"))
            ) or tele.get("fraud_count", 0)
            tele["sent_count"] = total
            tele["fraud_count"] = flagged
            tele["quarantine_count"] = len(quarantine_records)
            tele["fraud_rate_pct"] = round((flagged / total) * 100.0, 1) if total > 0 else 0.0
            tele["tps"] = calculate_live_tps(combined)
            self._send_json(200, tele)
            return

        if path == "/api/transactions":
            combined, main_records, quarantine_records = get_combined_records()
            page = _safe_int(query.get("page", ["1"])[0], 1, min_val=1)
            limit = _safe_int(query.get("limit", ["12"])[0], 12, min_val=1, max_val=100)

            filtered = _filter_records(combined, query)
            total_count = len(filtered)
            unfiltered_total = len(combined)
            total_pages = max(1, (total_count + limit - 1) // limit)
            start = (page - 1) * limit
            end = start + limit
            flagged_count = sum(
                1 for r in combined
                if (r.get("decision") in ("REVIEW_QUEUE", "BLOCK") or r.get("status") in ("QUARANTINED", "PENDING_REVIEW"))
            )
            self._send_json(200, {
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "unfiltered_total_count": unfiltered_total,
                "total_pages": total_pages,
                "flagged_count": flagged_count,
                "quarantine_count": len(quarantine_records),
                "fraud_rate_pct": round((flagged_count / unfiltered_total) * 100.0, 1) if unfiltered_total > 0 else 0.0,
                "tps": calculate_live_tps(combined),
                "items": filtered[start:end]
            })
            return

        if path.startswith("/transaction/"):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2:
                tx_id = unquote(parts[1])
                is_export = len(parts) >= 3 and parts[2] == "export"
                combined, main_records, _ = get_combined_records()
                found = next((r for r in combined if r.get("transaction_id") == tx_id), None)
                if not found:
                    self._send_json(404, {"error": "NOT_FOUND", "transaction_id": tx_id})
                    return
                enriched = dict(found)
                acct_id = (
                    enriched.get("account_id")
                    or enriched.get("source_account")
                    or (enriched.get("original_payload") or {}).get("account_id")
                    or (enriched.get("original_payload") or {}).get("source_account")
                )
                acct_history = []
                for r in combined:
                    if r.get("transaction_id") == tx_id:
                        continue
                    r_payload = r.get("original_payload") or {}
                    r_acct = (
                        r.get("account_id")
                        or r.get("source_account")
                        or r_payload.get("account_id")
                        or r_payload.get("source_account")
                    )
                    if acct_id and r_acct == acct_id:
                        acct_history.append({
                            "transaction_id": r.get("transaction_id"),
                            "timestamp": r.get("timestamp") or r.get("quarantine_ts") or r_payload.get("timestamp") or "",
                            "amount": r.get("amount") if r.get("amount") is not None else r_payload.get("amount", 0),
                            "risk_score": int(round(_record_risk_score(r))),
                            "decision": r.get("decision") or r.get("status") or "APPROVE",
                            "status": r.get("status") or r.get("decision") or "APPROVE"
                        })
                acct_history.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
                enriched["account_history_last_5"] = acct_history[:5]
                headers = {}
                if is_export:
                    headers["Content-Disposition"] = f'attachment; filename="transaction_{tx_id}.json"'
                self._send_json(200, enriched, extra_headers=headers)
                return

        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/simulate":
            length = _safe_int(self.headers.get("Content-Length", "0"), 0, min_val=0)
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                body = json.loads(raw)
            except Exception:
                self._send_json(400, {"error": "INVALID_JSON"})
                return
            if not isinstance(body, dict):
                self._send_json(400, {"error": "INVALID_PAYLOAD", "message": "Request body must be a JSON object."})
                return

            now_utc = datetime.now(timezone.utc)
            tx_id = f"tx_sim_{int(now_utc.timestamp() * 1000)}"
            preset = str(body.get("preset") or "CUSTOM").upper()

            if preset == "CLEAN_DOMESTIC":
                sim_tx = {
                    "transaction_id": tx_id,
                    "source_account": "acc_1",
                    "amount": 42.50,
                    "txn_type": "CREDIT",
                    "merchant": "Metro Coffee Roasters",
                    "merchant_category": "dining",
                    "origin_ip": "192.0.2.1",
                    "transaction_city": "New York",
                    "transaction_country": "US",
                    "timestamp": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            elif preset == "AMOUNT_ANOMALY":
                sim_tx = {
                    "transaction_id": tx_id,
                    "source_account": "acc_2",
                    "amount": 195.00,
                    "txn_type": "CREDIT",
                    "merchant": "Global Digital Exchange",
                    "merchant_category": "electronics",
                    "origin_ip": "198.51.100.50",
                    "transaction_city": "Amsterdam",
                    "transaction_country": "NL",
                    "registered_country": "US",
                    "local_hour": 3,
                    "timestamp": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            elif preset == "TOR_IMPOSSIBLE_TRAVEL":
                sim_tx = {
                    "transaction_id": tx_id,
                    "source_account": "acc_10",
                    "amount": 980.00,
                    "txn_type": "WIRE",
                    "merchant": "Offshore Bullion Clearing",
                    "merchant_category": "wire_transfer",
                    "origin_ip": "185.220.101.1",
                    "transaction_city": "Frankfurt",
                    "transaction_country": "DE",
                    "timestamp": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            else:
                sim_tx = {
                    "transaction_id": body.get("transaction_id") or tx_id,
                    "source_account": body.get("source_account") or "acc_demo_01",
                    "amount": _safe_float(body.get("amount"), 250.0, 0.0),
                    "txn_type": body.get("txn_type") or "WIRE",
                    "merchant": body.get("merchant") or "Standard Counterparty",
                    "origin_ip": body.get("origin_ip") or "192.0.2.1",
                    "transaction_city": body.get("transaction_city") or "New York",
                    "transaction_country": body.get("transaction_country") or "US",
                    "timestamp": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                }

            from src.db_client import DBClient
            from src.router_function import FraudRouter
            t0 = time.perf_counter()
            db = DBClient(fallback_path=MAIN_LOG_FILE, quarantine_fallback_path=QUARANTINE_LOG_FILE)
            router = FraudRouter(db_client=db)
            scored = router.route_transaction(sim_tx)
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            self._send_json(200, {
                "status": "SCORED",
                "latency_ms": latency_ms,
                "result": scored
            })
            return

        if parsed.path == "/release":
            length = _safe_int(self.headers.get("Content-Length", "0"), 0, min_val=0)
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                body = json.loads(raw)
            except Exception:
                self._send_json(400, {"error": "INVALID_JSON"})
                return
            if not isinstance(body, dict):
                self._send_json(400, {"error": "INVALID_PAYLOAD", "message": "Request body must be a JSON object."})
                return
            from src.db_client import DBClient
            from src.quarantine_manager import QuarantineManager
            db = DBClient(fallback_path=MAIN_LOG_FILE, quarantine_fallback_path=QUARANTINE_LOG_FILE)
            qm = QuarantineManager(db_client=db)
            res = qm.release_transaction(
                transaction_id=body.get("transaction_id"),
                analyst_notes=body.get("analyst_notes", "Released via Dashboard API"),
                headers=dict(self.headers)
            )
            self._send_json(res["http_status"], res)
            return

        self._send_json(404, {"error": "NOT_FOUND"})

    def log_message(self, format, *args):
        pass


def run_server(port=8081):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, TelemetryHTTPRequestHandler)
    print("\n==========================================================================")
    print(f" FraudGuard Risk & Compliance Console Running at: http://localhost:{port}")
    print("==========================================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping console server...")
        httpd.server_close()


if __name__ == "__main__":
    port_num = _safe_int(os.environ.get("DASHBOARD_PORT", "8081"), 8081, min_val=1, max_val=65535)
    run_server(port=port_num)
