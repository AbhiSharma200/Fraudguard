# FraudGuard — Interim Review Live Demo Script & Presentation Guide

> **Target Audience:** College Faculty Evaluators (Cloud & Systems Review Panel)  
> **Core Objective:** Demonstrate a working, real-time fraud detection pipeline on **live AWS (`eu-north-1`)** solving pre-settlement payment fraud in **< 30 seconds per step**.  
> **Cloud Stack:** AWS Lambda (`Python 3.12`) -> Amazon DynamoDB (`fraud-detection-transactions` & `fraud-quarantine`) -> Live Analyst Dashboard (`Port 8081`).  

---

## 0. Mandatory Pre-Demo Warm-Up (Run 5 Minutes Before Faculty Arrive)

> [!IMPORTANT]
> **Rule #5: Never demo with a cold Lambda.** Invoke `fraudguard-decision-router` once before the review starts so the `Python 3.12` execution environment, `fraud_model.pkl`, and DynamoDB connections in `eu-north-1` are warm (`< 10 ms` execution).

### Pre-Presentation Checklist & Warm-Up Command (`~10 seconds`)
1. Open **Browser Tab 1**: AWS DynamoDB Console (`eu-north-1`) -> Tables -> `fraud-detection-transactions` (`FraudGuardAuditLog`) and `fraud-quarantine` -> **Explore table items**.
2. Open **Browser Tab 2**: FraudGuard Analyst Dashboard at **`http://localhost:8081`** (or **`http://<ec2-ip>:8081`**).
3. Run the warm-up invocation in PowerShell:

```powershell
# 1. Start the dashboard server on port 8081 (if not already running on EC2)
Start-Process python -ArgumentList "src/live_dashboard.py --port 8081"

# 2. Warm up the AWS Lambda container in eu-north-1 (or local handler)
aws lambda invoke --region eu-north-1 `
  --function-name fraudguard-decision-router `
  --cli-binary-format raw-in-base64-out `
  --payload '{"transaction_id":"tx_warmup_000","account_id":"acc_1","amount":10.0,"txn_type":"PURCHASE","ip_address":"192.0.2.1"}' `
  warmup_out.json
```

---

## 1. Live Demo Script: End-to-End Flow (`Input -> Lambda -> DynamoDB -> Output`)

Every step below is timed to complete in **under 30 seconds** and follows a single, transparent flow that faculty can track across the terminal, DynamoDB console, and live dashboard.

---

### Step 1 (`0:00 – 0:25`) — Scenario A: Clean Domestic Transaction (`APPROVE`)

**What to tell faculty:**  
*"First, we send a normal $42.50 coffee shop purchase from `acc_1` in New York over a residential Verizon Fios IP (`192.0.2.1`). Lambda evaluates all 7 intelligence modules and approves it in under 5 milliseconds."*

#### Command to Run (`< 5 seconds`)
```powershell
aws lambda invoke --region eu-north-1 `
  --function-name fraudguard-decision-router `
  --cli-binary-format raw-in-base64-out `
  --payload file://demo/payloads/1_approve_clean.json `
  response_step1.json ; python -c "import json; r=json.load(open('response_step1.json')); b=json.loads(r['body']); print(json.dumps({k:b[k] for k in ['transaction_id','amount','risk_score','decision','action','status','flags','execution_ms']}, indent=2))"
```
*(Offline / Local Instant Equivalent if Wi-Fi drops)*:
```powershell
python -c "import json, src.lambda_function as lf; res=lf.lambda_handler(json.load(open('demo/payloads/1_approve_clean.json'))); b=json.loads(res['body']); print(json.dumps({k:b[k] for k in ['transaction_id','amount','risk_score','decision','action','status','flags','execution_ms']}, indent=2))"
```

#### Expected Output
```json
{
  "transaction_id": "tx_demo_approve_001",
  "amount": 42.5,
  "risk_score": 0,
  "decision": "ALLOW",
  "action": "APPROVE",
  "status": "APPROVED",
  "flags": [],
  "execution_ms": 4.18
}
```
- **Fallback File:** [`demo/fallbacks/step1_warmup_and_approve.txt`](file:///C:/Users/hp/.gemini/antigravity/scratch/fraudguard-datapipeline/demo/fallbacks/step1_warmup_and_approve.txt)

---

### Step 2 (`0:25 – 0:55`) — Scenario B **[INTERIM REVIEW CENTREPIECE]**: Rule Engine Decision (`AMOUNT_ANOMALY -> REVIEW_QUEUE`)

**What to tell faculty:**  
*"Now we demonstrate our completed core module end-to-end: Input -> AWS Lambda -> Amazon DynamoDB -> Dashboard Output. Account `acc_1` suddenly attempts a $450.00 luxury watch purchase — exceeding our $180.00 anomaly threshold and spiking 958% above their previous $42.50 spend. Watch the Rule Engine trigger `AMOUNT_ANOMALY` and route the transaction to `REVIEW_QUEUE`."*

#### Command to Run (`< 10 seconds`)
```powershell
aws lambda invoke --region eu-north-1 `
  --function-name fraudguard-decision-router `
  --cli-binary-format raw-in-base64-out `
  --payload file://demo/payloads/2_review_amount_anomaly.json `
  response_step2.json ; python -c "import json; r=json.load(open('response_step2.json')); b=json.loads(r['body']); print(json.dumps({k:b[k] for k in ['transaction_id','amount','risk_score','decision','action','status','triggered_rules','traceback','execution_ms']}, indent=2))"
```
*(Offline / Local Instant Equivalent)*:
```powershell
python -c "import json, src.lambda_function as lf; res=lf.lambda_handler(json.load(open('demo/payloads/2_review_amount_anomaly.json'))); b=json.loads(res['body']); print(json.dumps({k:b[k] for k in ['transaction_id','amount','risk_score','decision','action','status','triggered_rules','traceback','execution_ms']}, indent=2))"
```

#### Expected Output
```json
{
  "transaction_id": "tx_demo_review_002",
  "amount": 450.0,
  "risk_score": 60,
  "decision": "REVIEW_QUEUE",
  "action": "REVIEW_QUEUE",
  "status": "PENDING_REVIEW",
  "triggered_rules": [
    "AMOUNT_ANOMALY",
    "AMOUNT_SPIKE"
  ],
  "traceback": {
    "account_transaction_count": 2,
    "previous_transaction_id": "tx_demo_approve_001",
    "previous_transaction_ts": "2026-10-23T14:00:00Z",
    "previous_amount": 42.5,
    "previous_merchant": "Tribeca Coffee Roasters",
    "previous_location": "New York",
    "velocity_1hr": 2,
    "velocity_24hr": 2,
    "amount_delta_pct": 958.82,
    "chain_risk_score": 30.0
  },
  "execution_ms": 4.82
}
```
- **Visual Confirmation (< 5 seconds):** Point to **`http://localhost:8081`** where `tx_demo_review_002` appears with an **AMBER `REVIEW_QUEUE` badge** (`Risk Score: 60`), and refresh the DynamoDB `fraud-detection-transactions` table tab to show the persisted item.
- **Fallback File:** [`demo/fallbacks/step2_amount_anomaly_review_queue.txt`](file:///C:/Users/hp/.gemini/antigravity/scratch/fraudguard-datapipeline/demo/fallbacks/step2_amount_anomaly_review_queue.txt)

---

### Step 3 (`0:55 – 1:25`) — Scenario C **[VISUAL SHOWCASE]**: `BLOCK -> QUARANTINED` (TOR Exit Node + Impossible Travel) & Live DynamoDB Verification

**What to tell faculty:**  
*"Five minutes after the New York purchase, the same account attempts a $980.00 crypto wire transfer from a known TOR Exit Node in Frankfurt, Germany (`185.220.101.1`). Moving 6,201 km in 5 minutes requires traveling at 74,416 km/h. FraudGuard immediately flags `TOR_EXIT_NODE` and `IMPOSSIBLE_TRAVEL`, scores it `100/100`, returns `HTTP 202`, and isolates the payload into our dedicated `fraud-quarantine` DynamoDB table."*

#### Command to Run (`< 15 seconds`)
```powershell
aws lambda invoke --region eu-north-1 `
  --function-name fraudguard-decision-router `
  --cli-binary-format raw-in-base64-out `
  --payload file://demo/payloads/3_block_impossible_travel_tor.json `
  response_step3.json ; python -c "import json; r=json.load(open('response_step3.json')); b=json.loads(r['body']); print('HTTP Status:', r['statusCode']); print(json.dumps({k:b[k] for k in ['transaction_id','amount','risk_score','decision','status','flags','origin','location_check','quarantine_ts','auto_release_after']}, indent=2))"
```
*(Offline / Local Instant Equivalent)*:
```powershell
python -c "import json, src.lambda_function as lf; res=lf.lambda_handler(json.load(open('demo/payloads/3_block_impossible_travel_tor.json'))); b=json.loads(res['body']); print('HTTP Status:', res['statusCode']); print(json.dumps({k:b[k] for k in ['transaction_id','amount','risk_score','decision','status','flags','origin','location_check','quarantine_ts','auto_release_after']}, indent=2))"
```

#### Verify Record in Live DynamoDB `fraud-quarantine` Table (`< 10 seconds`)
Switch to the AWS DynamoDB Console tab (`eu-north-1` -> `fraud-quarantine` -> click **Run**), or run:
```powershell
aws dynamodb get-item --region eu-north-1 `
  --table-name fraud-quarantine `
  --key '{\"transaction_id\": {\"S\": \"tx_demo_block_003\"}}'
```

#### Expected Output
```json
HTTP Status: 202
{
  "transaction_id": "tx_demo_block_003",
  "amount": 980.0,
  "risk_score": 100,
  "decision": "BLOCK",
  "status": "QUARANTINED",
  "flags": [
    "AMOUNT_ANOMALY",
    "CHANNEL_RISK",
    "TOR_EXIT_NODE",
    "VPN_OR_PROXY_DETECTED",
    "FOREIGN_ORIGIN",
    "IMPOSSIBLE_TRAVEL",
    "INTERNATIONAL_TRANSACTION",
    "LOCATION_MISMATCH"
  ],
  "origin": {
    "ip_address": "185.220.101.1",
    "country": "DE",
    "city": "Frankfurt",
    "isp": "Tor Exit Node / Zwiebelfreunde",
    "connection_type": "tor",
    "is_tor": true,
    "coordinates": { "lat": 50.1109, "lon": 8.6821 }
  },
  "location_check": {
    "account_registered_city": "New York",
    "transaction_city": "Frankfurt",
    "distance_km": 6201.36,
    "is_international": true,
    "is_impossible_travel": true,
    "travel_speed_kmh": 74416.32
  },
  "quarantine_ts": "2026-10-23T14:25:00Z",
  "auto_release_after": "2026-10-24T14:25:00Z"
}
```
- **Fallback File:** [`demo/fallbacks/step3_block_quarantine_and_dynamodb.txt`](file:///C:/Users/hp/.gemini/antigravity/scratch/fraudguard-datapipeline/demo/fallbacks/step3_block_quarantine_and_dynamodb.txt)

---

### Step 4 (`1:25 – 1:55`) — Live Dashboard Inspection (`Port 8081`) & Authenticated Quarantine Release (`POST /release`)

**What to tell faculty:**  
*"On our live Analyst Dashboard (`port 8081`), clicking `tx_demo_block_003` opens the slide-in intelligence panel showing the red pulsing SVG map marker in Frankfurt, the 3-step account traceback chain, and the simulated cell-tower mismatch in New York. If the cardholder confirms the transaction via 2FA, an authenticated analyst can release it from quarantine."*

#### Action 1: Click `tx_demo_block_003` Row on `http://localhost:8081` (`< 15 seconds`)
- Point out the **Red `BLOCK / QUARANTINED` Badge** (`100 / 100`).
- Point out the **SVG Origin Map** showing the green marker in New York (`40.71, -74.00`) and the red pulsing marker in Frankfurt (`50.11, 8.68`).
- Point out the **Traceback Mini-Table** linking `tx_demo_approve_001` ($42.50) -> `tx_demo_review_002` ($450.00) -> `tx_demo_block_003` ($980.00).

#### Action 2: Release Quarantined Transaction via Authenticated API (`< 10 seconds`)
```powershell
python -c "import json, src.lambda_function as lf; ev={'httpMethod':'POST','path':'/release','headers':{'X-API-Key':'fg-analyst-demo-key-2026'},'body':open('demo/payloads/4_release_quarantine.json').read()}; res=lf.lambda_handler(ev); print(json.dumps(json.loads(res['body']), indent=2))"
```

#### Expected Output
```json
{
  "http_status": 200,
  "transaction_id": "tx_demo_block_003",
  "status": "RELEASED",
  "record": {
    "transaction_id": "tx_demo_block_003",
    "account_id": "acc_1",
    "quarantine_ts": "2026-10-23T14:25:00Z",
    "status": "RELEASED",
    "risk_score": 100,
    "analyst_notes": "Verified executive travel override with cardholder via 2FA."
  }
}
```
- **Fallback File:** [`demo/fallbacks/step4_dashboard_and_release.txt`](file:///C:/Users/hp/.gemini/antigravity/scratch/fraudguard-datapipeline/demo/fallbacks/step4_dashboard_and_release.txt)

---

## 2. Presentation Slide Content & Talking Points (Max 1–2 Sentences per Slide)

| Slide # | Slide Title | Visual / Bullet Content on Slide | Speaker Talking Point (1–2 Sentences Max) |
|---|---|---|---|
| **Slide 1** | **Problem Statement: Pre-Settlement Fraud Interception** | • Digital payments settle in seconds; batch fraud detection is too late.<br>• Need `< 50 ms` scoring across rules, geo-velocity, and ML before funds leave. | *"Payment fraud costs billions annually because traditional batch reviews happen after money has already moved. FraudGuard intercepts, enriches, and routes transactions in under 50 milliseconds before settlement occurs."* |
| **Slide 2** | **Serverless-First AWS Architecture (`eu-north-1`)** | • **Compute:** AWS Lambda (`Python 3.12`) + Kinesis Stream<br>• **Storage:** DynamoDB (`fraud-detection-transactions` & `fraud-quarantine`)<br>• **UI & Alerts:** EC2 Dashboard (`Port 8081`) + CloudWatch Alarms | *"Our entire pipeline runs serverless on AWS `eu-north-1` using Python 3.12 Lambda and dual on-demand DynamoDB tables with automatic TTL cleanup. Embedding our XGBoost model directly inside Lambda eliminates idle GPU costs and guarantees 100% compatibility with student AWS accounts."* |
| **Slide 3** | **Interim Review Centrepiece: End-to-End Rule & Traceback Flow** | • `Input JSON -> AWS Lambda -> DynamoDB (AccountTimestampIndex GSI) -> Output`<br>• Centrepiece Rule: `AMOUNT_ANOMALY` (`>$180`) + `AMOUNT_SPIKE` (`>300%`) -> `REVIEW_QUEUE` | *"Our completed core module proves the full AWS data lifecycle from transaction ingestion to DynamoDB persistence and live dashboard visualization. When an account jumps from a $42 coffee purchase to a $450 luxury item, our Rule and Traceback engines automatically route it to the amber `REVIEW_QUEUE`."* |
| **Slide 4** | **7 Fraud Intelligence Features & Quarantine Isolation** | • **Origin & Travel:** TOR/VPN Detection + Haversine Impossible Travel (`>900 km/h`)<br>• **Quarantine (`HTTP 202`):** Isolated in `fraud-quarantine` with `X-API-Key` `/release` API<br>• **Demo-Safe PII:** `MOCK_DEMO_DATA` cell-tower vs. IP location correlation | *"Beyond basic rules, FraudGuard enriches every event with 7 intelligence layers — catching TOR exit nodes and 74,000 km/h impossible travel between New York and Frankfurt. High-risk `BLOCK` payloads are isolated in a dedicated `fraud-quarantine` DynamoDB table until an authenticated analyst releases them."* |
| **Slide 5** | **Verification, Reliability & Live Demo** | • **39+ Automated Tests:** Unit, 7-Feature Intelligence, Idempotency (`HTTP 409`), `<50ms` Latency<br>• **4 CloudWatch Alarms:** Attack Wave (`Quarantine > 100`), Error Rate, Latency, Throttles | *"We validated the system with a comprehensive test suite verifying deterministic scoring, DynamoDB idempotency against duplicate transaction IDs, and sub-50ms execution latency. We will now demonstrate `APPROVE`, `REVIEW_QUEUE`, and `BLOCK` live on AWS."* |

---

## 3. Live Demo Fallback Plan (Top 2 Most Likely Failure Points)

> [!WARNING]
> Classroom Wi-Fi blocks or expired temporary AWS CLI session tokens are the two most common causes of live academic demo failures. Follow these exact recovery steps in **under 10 seconds** without losing presenter momentum.

### Failure Point 1: Classroom Wi-Fi Drops or AWS CLI Session Token Expires (`ExpiredTokenException` / Timeout)
1. **Immediate Action (< 5 seconds):** Switch `USE_AWS_DYNAMODB` to `"false"` so `src/lambda_function.py` uses its built-in thread-safe local persistence (`data/audit_log.json` and `data/quarantine_log.json`) which runs the **exact same `Python 3.12` `FraudRouter` code path**:
   ```powershell
   $env:USE_AWS_DYNAMODB = "false"
   python tests/run_all_tests.py
   ```
2. **Display Pre-Recorded Live AWS Output (< 5 seconds):** Display the pre-recorded AWS `eu-north-1` terminal captures stored in `demo/fallbacks/`:
   ```powershell
   Get-Content demo/fallbacks/step2_amount_anomaly_review_queue.txt
   Get-Content demo/fallbacks/step3_block_quarantine_and_dynamodb.txt
   ```

### Failure Point 2: EC2 / Local Port `8081` Conflict or Browser Cache Stall
1. **Immediate Action (< 5 seconds):** Query the dashboard JSON API directly from the terminal or display the pre-recorded dashboard & release trace:
   ```powershell
   Get-Content demo/fallbacks/step4_dashboard_and_release.txt
   ```
2. **Restart Dashboard on Alternate Port if Needed (< 5 seconds):**
   ```powershell
   python src/live_dashboard.py --port 8082
   ```
