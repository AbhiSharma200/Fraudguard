#!/usr/bin/env python3
"""
FraudGuard — Real-Time Fraud Detection & Risk Scoring System Dashboard
Host a live web dashboard showing real-time transaction streaming telemetry and JSON payload inspection.
URL: http://localhost:8080
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TELEMETRY_FILE = os.path.join(SCRIPT_DIR, "live_telemetry.json")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FraudGuard — Real-Time Fraud Detection & Risk Scoring System</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent-green: #10b981;
            --accent-blue: #3b82f6;
            --accent-red: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
            color: var(--accent-blue);
        }
        .badge {
            background-color: rgba(16, 185, 129, 0.2);
            color: var(--accent-green);
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 600;
            border: 1px solid var(--accent-green);
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .kpi-card {
            background-color: var(--card-bg);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        .kpi-card h3 {
            margin: 0 0 8px 0;
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
        }
        .kpi-card p {
            margin: 0;
            font-size: 28px;
            font-weight: bold;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }
        .panel {
            background-color: var(--card-bg);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            padding: 20px;
        }
        .panel h2 {
            margin: 0 0 16px 0;
            font-size: 18px;
            color: var(--accent-blue);
        }
        pre {
            background-color: #090d16;
            padding: 16px;
            border-radius: 6px;
            color: #38bdf8;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
        }
        .pulse {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
            margin-right: 8px;
        }
        .footer {
            margin-top: 32px;
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            border-top: 1px solid var(--border-color);
            padding-top: 16px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>FraudGuard — Real-Time Fraud Detection & Risk Scoring System</h1>
            <p style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 14px;">Live Digital Payments Ingestion & Risk Scoring Dashboard</p>
        </div>
        <div class="badge"><span class="pulse"></span> LIVE PAYMENTS STREAMING</div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <h3>Total Transactions</h3>
            <p id="sent-count">45</p>
        </div>
        <div class="kpi-card">
            <h3>Flagged Suspicious</h3>
            <p id="fraud-count" style="color: var(--accent-red);">12</p>
        </div>
        <div class="kpi-card">
            <h3>Fraud Risk Rate</h3>
            <p id="fraud-rate">26.7%</p>
        </div>
        <div class="kpi-card">
            <h3>Processing Speed (TPS)</h3>
            <p id="tps" style="color: var(--accent-green);">2.0</p>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Real-Time Transaction Payload Inspector</h2>
            <pre id="json-inspector">{
  "transaction_id": "tx_fg_10",
  "source_account": "acc_4",
  "destination_account": "acc_26",
  "timestamp": "2026-08-23T19:22:45Z",
  "amount": 151.13,
  "txn_type": "WIRE",
  "status": "SUSPICIOUS"
}</pre>
        </div>
        <div class="panel">
            <h2>System Overview</h2>
            <p style="font-size: 14px; line-height: 1.6; color: var(--text-muted);">
                <strong>Application:</strong> FraudGuard Digital Payment Security<br>
                <strong>Stream Pipeline:</strong> Preprocessed Financial Transaction Ingestion<br>
                <strong>Format:</strong> JSON Schema Validated<br>
                <strong>Risk Scoring:</strong> Active Micro-Batch Decisioning
            </p>
        </div>
    </div>

    <div class="footer">
        FraudGuard — Real-Time Fraud Detection & Risk Scoring System
    </div>

    <script>
        function updateTelemetry() {
            fetch('/api/telemetry')
                .then(res => res.json())
                .then(data => {
                    if (data && data.sent_count) {
                        document.getElementById('sent-count').innerText = data.sent_count;
                        document.getElementById('fraud-count').innerText = data.fraud_count;
                        document.getElementById('fraud-rate').innerText = data.fraud_rate_pct + '%';
                        document.getElementById('tps').innerText = data.tps;
                        document.getElementById('json-inspector').innerText = JSON.stringify(data.last_event, null, 2);
                    }
                })
                .catch(err => console.log('Waiting for active stream data...'));
        }
        setInterval(updateTelemetry, 500);
    </script>
</body>
</html>
"""

class TelemetryHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/telemetry':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            if os.path.exists(TELEMETRY_FILE):
                with open(TELEMETRY_FILE, 'r') as tf:
                    self.wfile.write(tf.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"status": "waiting"}).encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))

    def log_message(self, format, *args):
        pass

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, TelemetryHTTPRequestHandler)
    print(f"\n==========================================================================")
    print(f" FraudGuard Dashboard Server Running at: http://localhost:{port}")
    print(f"==========================================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
