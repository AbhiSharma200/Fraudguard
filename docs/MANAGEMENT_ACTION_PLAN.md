# FraudGuard Engineering Management Directive & Action Plan

**Document Owner:** Agent 7 — VP of Engineering & Technical Program Manager  
**Project:** FraudGuard Real-Time Fraud Detection Pipeline (`fraudguard-datapipeline`)  
**Target Region & Runtime:** AWS `eu-north-1` (Stockholm) | Python 3.12 | Dashboard Port `8081`  
**Status:** Active Remediation Sprint — Production Readiness Gate  

---

## 1. Executive Summary

Following a comprehensive audit by **Agent 6 (The Merciless Customer Agent)** and adversarial validation by **Agent 3 (The QA & Testing Agent)**, Engineering Leadership has established this mandatory remediation directive.

### Audit Findings Summary
* **Customer Audit (Agent 6):**
  * **10 Critical Blockers (`CRIT-01` – `CRIT-10`):** Infrastructure state collisions (Azure/AWS `.tf` mixing), broken Lambda packaging/handler wiring, read-only `/var/task/data` filesystem crashes on AWS Lambda, mismatched DynamoDB table names (`fraud-detection-transactions` vs `fraud-quarantine`), student AWS account IAM/Kinesis permission blocks, hardcoded API keys, port `8080` conflicts instead of `8081`, missing transaction filter controls, and missing offline SVG map visualization in the investigation sidebar.
  * **10 High-Priority Issues (`HIGH-01` – `HIGH-10`):** Missing structured `SCORE` logs for CloudWatch metrics, non-standard risk badge colors, crashes on `account_id`/string `amount`/naive timestamps, uncalibrated ML probabilities inflating moderate rule scores into false-positive `BLOCK`s, incomplete traceback mini-tables, disconnected `DBClient` in `stream_monitor.py`, DOM XSS vulnerabilities, silent UI button failures, dummy infrastructure verification script, and outdated documentation.
  * **8 Medium Issues (`MED-01` – `MED-08`):** Quarantined transactions omitted from historical velocity lookbacks, flat schema loss on quarantine records, uncurated `replay_stream.py` payloads, unguarded top-level `pandas`/`joblib`/`azure` imports, missing DynamoDB conditional updates on release, and remote S3 Terraform state bootstrapping blockers.
  * **6 UX Polish Items (`UX-01` – `UX-06`):** Active row highlight loss during polling, mobile `375px` layout overflow, pagination boundary state bugs, and missing pause/refresh/reset controls.
* **Adversarial QA Suite (Agent 3):**
  * **9 Specific Test Failures (`T-004`, `T-005`, `T-006`, `T-007`, `T-009`, `T-011`, `T-013`, `T-014`, `T-015`):** Uncaught exceptions on schema variations, `NaN`/`Infinity` float poisoning, ML score inflation (`93+` on moderate anomalies), `0.0`-minute simultaneous impossible travel bypass, future timestamp poisoning (`elapsed < 0`), velocity blindness on quarantined accounts, and crashes on non-dict JSON bodies or URL-encoded path parameters.

**Release Policy:** No code is considered production-ready until **100% of Critical, High, Medium, UX, and QA tickets** below pass automated verification and re-inspection by Agent 3 and Agent 6.

---

## 2. Team Assignments & Ticket Matrix

| Agent Role | Assigned Tickets | Core Deliverables |
| :--- | :--- | :--- |
| **Agent 1 — Architect** | `CRIT-01`, `CRIT-02`, `CRIT-05`, `CRIT-06`, `CRIT-07`, `MED-07`, `HIGH-09` | Clean AWS-only Terraform (`eu-north-1`, Python 3.12), Lambda packaging, student-account toggles, and real + offline `verify_aws_infrastructure.py`. |
| **Agent 2 — Backend Engineer** | `CRIT-03`, `CRIT-04`, `CRIT-05`, `CRIT-07`, `HIGH-01`, `HIGH-03`, `HIGH-04`, `MED-01`–`MED-06`, `T-004`–`T-007`, `T-009`, `T-011`, `T-013`–`T-015` | Resilient Lambda handler, DynamoDB + `/tmp` storage, calibrated integer `0..100` scoring, 7-feature hardening, velocity merge across quarantine, and safe HTTP parsing. |
| **Agent 4 — Frontend Engineer** | `CRIT-08`, `CRIT-09`, `CRIT-10`, `HIGH-02`, `HIGH-05`, `HIGH-06`, `HIGH-07`, `HIGH-08`, `UX-01`–`UX-06`, `T-015` | Port `8081` default, multi-criteria filter bar, inline offline SVG origin map, XSS-safe rendering, live TPS, interactive quarantine release, and responsive UX polish. |
| **Agent 5 — Demo & Docs** | `HIGH-10` | Comprehensive `README.md`, `docs/*`, `<30s` live review demo script (`AMOUNT_ANOMALY -> REVIEW_QUEUE` & `BLOCK`), curated payloads, and offline fallbacks. |

---

## 3. Detailed Engineering Tickets & Acceptance Criteria

### 3.1 Agent 1 — The Architect Agent (Infrastructure & Cloud Verification)

#### `CRIT-01`: Remove Conflicting Azure `.tf` Files from `terraform/`
* **Problem:** `terraform/` contains legacy Azure resources (`azurerm` provider) alongside AWS resources, causing `terraform validate` and `terraform plan` to fail.
* **Requirement:** Remove or archive all Azure `.tf` definitions from the active `terraform/` directory so only pure AWS infrastructure definitions remain.
* **Acceptance Criteria:** `terraform init -backend=false` and `terraform validate` succeed cleanly with zero Azure provider dependencies.

#### `CRIT-02`: Fix Lambda ZIP Packaging & Module Import Structure
* **Problem:** Terraform packages only a single file or omits `src/` subpackages (`fraud_intelligence`, `lambda_pkg`, `storage`), causing `ImportError` at Lambda startup.
* **Requirement:** Configure Terraform `archive_file` data source (or build packaging) to bundle the full application tree (`src/`) so both `lambda_function.handler` and internal module imports resolve in AWS Lambda Python 3.12 (`eu-north-1`).
* **Acceptance Criteria:** Packaged ZIP contains `lambda_function.py`, `db_client.py`, `fraud_intelligence/*`, `lambda_pkg/*`, and `storage/*` at importable paths.

#### `CRIT-05` (Infra): Standardize DynamoDB Table Names & Enable TTL
* **Problem:** Inconsistent table names between Terraform and backend code; missing TTL configuration.
* **Requirement:** Provision `fraud-detection-transactions` (partition key `transaction_id`, plus GSI on `user_id`/`timestamp` if needed) and `fraud-quarantine` (partition key `transaction_id`, with TTL attribute `ttl_expiry` enabled). Pass both table names into Lambda environment variables (`TRANSACTIONS_TABLE_NAME=fraud-detection-transactions`, `QUARANTINE_TABLE_NAME=fraud-quarantine`).
* **Acceptance Criteria:** Both tables exist in `terraform/` with `PAY_PER_REQUEST` billing, encryption, and TTL enabled on `fraud-quarantine`.

#### `CRIT-06`: Student Account Restriction Toggles (`enable_kinesis` & `enable_public_function_url`)
* **Problem:** Restricted AWS Academy / Student accounts often block `kinesis:CreateStream` or public unauthenticated Lambda Function URLs (`AuthType = NONE`).
* **Requirement:** Add boolean variables `enable_kinesis` (default `false`) and `enable_public_function_url` (default `false`) in `terraform/variables.tf` using `count = var.enable_kinesis ? 1 : 0` and `count = var.enable_public_function_url ? 1 : 0`.
* **Acceptance Criteria:** `terraform plan` defaults to deploying DynamoDB + Lambda + CloudWatch without failing on restricted student accounts, while supporting full Kinesis/Function URL deployment when toggled `true`.

#### `CRIT-07` (Infra): Eliminate Hardcoded API Keys & Secrets
* **Problem:** Hardcoded dummy secrets or API keys in Terraform/environment configs.
* **Requirement:** Use sensitive Terraform variables (`sensitive = true`) with empty/safe defaults and environment injection (`FRAUDGUARD_API_KEY`).
* **Acceptance Criteria:** Zero hardcoded credentials in `terraform/*.tf`.

#### `MED-07`: Default to Local Terraform State with Documented S3 Backend Option
* **Problem:** Hardcoded remote S3 backend (`fraudguard-tf-state-bucket`) fails `terraform init` when the bootstrap bucket does not exist.
* **Requirement:** Use local backend by default in `terraform/main.tf` and provide a commented S3 backend block with clear bootstrap instructions.
* **Acceptance Criteria:** `terraform init` works out-of-the-box without pre-existing S3 buckets.

#### `HIGH-09`: Real `boto3` + Offline-Capable `scripts/verify_aws_infrastructure.py`
* **Problem:** Existing verification script was a placeholder or crashed when offline/unauthenticated.
* **Requirement:** Implement `scripts/verify_aws_infrastructure.py` targeting `eu-north-1` and Python 3.12. It must perform real `boto3` checks (`sts:GetCallerIdentity`, DynamoDB `describe_table` for `fraud-detection-transactions` and `fraud-quarantine`, Lambda `get_function_configuration` verifying `python3.12`, CloudWatch log groups) AND gracefully fall back to static local verification (checking `terraform/*.tf` and local codebase wiring) when AWS credentials are unavailable or `--offline` is passed.
* **Acceptance Criteria:** Script exits `0` in offline/static verification mode and accurately validates live AWS resources when credentials are provided.

---

### 3.2 Agent 2 — The Backend Engineer Agent (Core Engine, Lambda, & Storage)

#### `CRIT-03`: Lambda Entry Point `handler(event, context)` & Top-Level Exception Safety
* **Problem:** AWS Lambda expects `lambda_function.handler(event, context)`, and unhandled runtime exceptions crash the invocation without returning a structured HTTP response.
* **Requirement:** Expose `handler(event, context)` (keeping `lambda_handler` as an alias) and wrap execution in a top-level `try/except Exception as e:` block that logs the error and returns `{"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e)})}`.
* **Acceptance Criteria:** Both `handler` and `lambda_handler` exist and never raise unhandled exceptions to the Lambda runtime.

#### `CRIT-04`: Eliminate Read-Only `/var/task/data` Writes in AWS Lambda & Fix DB Queries
* **Problem:** Writing local JSON files to `./data` inside AWS Lambda (`AWS_EXECUTION_ENV` / `/var/task`) raises `OSError: [Errno 30] Read-only file system`. Furthermore, `get_all_main_transactions()` and `get_all_quarantined_transactions()` did not properly scan/query DynamoDB first before falling back.
* **Requirement:**
  1. Detect Lambda execution (`os.environ.get("AWS_EXECUTION_ENV")` or read-only working dir) and route any local file fallback writes to `/tmp/fraudguard_data`.
  2. Ensure `DBClient.get_all_main_transactions()` and `DBClient.get_all_quarantined_transactions()` query/scan DynamoDB when available and merge/fall back cleanly to local storage in offline mode.
* **Acceptance Criteria:** Zero writes to `/var/task`; local fallback uses `/tmp` when running in Lambda; DynamoDB queries return normalized Python dicts (`Decimal` converted to `float`/`int`).

#### `CRIT-05` (Backend): Default Table Names (`fraud-detection-transactions` & `fraud-quarantine`)
* **Problem:** Mismatched default table names across `db_client.py`, `quarantine_manager.py`, and `lambda_function.py`.
* **Requirement:** Standardize default table names to `fraud-detection-transactions` (main) and `fraud-quarantine` (quarantine) across all backend modules, configurable via environment variables (`TRANSACTIONS_TABLE_NAME`, `QUARANTINE_TABLE_NAME`).
* **Acceptance Criteria:** All modules reference the exact same default table names.

#### `CRIT-07` (Backend): Remove Hardcoded API Key in `quarantine_manager.py`
* **Problem:** Hardcoded fallback API key (`"fg-admin-secret-key-2025"`) in source code.
* **Requirement:** Read expected API key strictly from `os.environ.get("FRAUDGUARD_API_KEY")`. If unset in local dev mode, allow local development operations with a logged warning or explicit env configuration rather than a hardcoded secret string.
* **Acceptance Criteria:** No hardcoded secret keys in `src/storage/quarantine_manager.py` or `src/lambda_pkg/lambda_function.py`.

#### `HIGH-01`: Structured CloudWatch Metric Log (`{"event": "SCORE", ...}`)
* **Problem:** CloudWatch Metric Filters require a structured JSON log line on every scored transaction.
* **Requirement:** Emit `json.dumps({"event": "SCORE", "txn_id": transaction_id, "score": risk_score, "action": action})` via standard logger/stdout on every transaction evaluation.
* **Acceptance Criteria:** Every scored transaction outputs a valid JSON line containing `"event": "SCORE"`, `"txn_id"`, and `"score"`.

#### `HIGH-03` / `T-004` / `T-005` / `T-006`: Input Normalization in `RuleEngine` (`account_id`, String/Null `amount`, Naive Timestamps)
* **Problem:**
  * `T-004`: Payloads providing `account_id` instead of `user_id` fail user lookbacks or crash.
  * `T-005`: Numeric string amounts (e.g., `"1500.50"`) or `None`/negative amounts cause `TypeError` or invalid math.
  * `T-006`: Combining timezone-naive (`2026-10-23T12:00:00`) and timezone-aware (`2026-10-23T12:05:00Z`) ISO timestamps raises `TypeError: can't subtract offset-naive and offset-aware datetimes`.
* **Requirement:**
  1. Normalize `user_id = txn.get("user_id") or txn.get("account_id") or "unknown"` across `RuleEngine`, `DBClient`, and analyzers.
  2. Coerce numeric string amounts (`"1500.50" -> 1500.50`), reject `None`, boolean, negative, or unparseable amounts cleanly (`ValueError` caught and handled or flagged safely).
  3. Normalize all parsed timestamps to timezone-aware `datetime.timezone.utc` before subtraction or comparison.
* **Acceptance Criteria:** Adversarial tests `T-004`, `T-005`, and `T-006` pass with zero unhandled exceptions.

#### `HIGH-04` / `T-009`: Strictly Integer `0..100` Risk Score & Calibrated ML/Rule Blending
* **Problem:** Uncalibrated binary ML classifier outputs (`0.99+`) or additive boosting turned moderate single-rule anomalies (e.g., `AMOUNT_ANOMALY` with rule score `40–79` expecting `REVIEW_QUEUE`) into `93+` (`BLOCK`), and sometimes produced float scores instead of `int`.
* **Requirement:**
  1. Guarantee `risk_score` is always an `int` clamped to `[0, 100]`.
  2. Calibrate ML/Rule score combination in `RuleEngine` so a single moderate anomaly (`40 <= rule_score < 80`, such as a $2,500–$4,500 amount anomaly with no other high-risk flags) stays in the `40..79` (`REVIEW_QUEUE` / `QUARANTINED`) band rather than jumping to `80+` (`BLOCK`), while multi-factor fraud or severe anomalies (`rule_score >= 80`) reliably trigger `BLOCK` (`>= 80`).
* **Acceptance Criteria:** `isinstance(result["risk_score"], int)` is always `True`, `0 <= score <= 100`, and `T-009` passes (`AMOUNT_ANOMALY` routes to `REVIEW_QUEUE` with score `40..79`).

#### `T-007`: Reject `NaN` / `Infinity` Amounts & Safe DynamoDB `Decimal` Conversion
* **Problem:** `float("nan")`, `float("inf")`, or `"NaN"` bypass numeric checks and crash `Decimal(str(val))` or corrupt z-score calculations.
* **Requirement:** Check `math.isnan(amount)` and `math.isinf(amount)` during validation/coercion; reject or sanitize before scoring and before converting floats to DynamoDB `Decimal`.
* **Acceptance Criteria:** `T-007` passes; `NaN` and `Infinity` never crash `RuleEngine` or `DBClient`.

#### `T-011`: Detect `0.0`-Minute Simultaneous Impossible Travel (`location_checker.py`)
* **Problem:** When two transactions occur at the exact same timestamp (`elapsed_minutes == 0.0`) in distant cities (e.g., London and Tokyo), `if elapsed_minutes <= 0:` skipped the speed check instead of flagging instantaneous teleportation.
* **Requirement:** In `location_checker.py`, if `distance_km > 50` (or significant distance) and `0.0 <= elapsed_minutes < 1e-6`, treat speed as infinite (`float("inf")` or `999999.0 km/h`) and flag `IMPOSSIBLE_TRAVEL`.
* **Acceptance Criteria:** `T-011` passes; simultaneous distant transactions trigger `IMPOSSIBLE_TRAVEL`.

#### `T-013`: Prevent Future Timestamp Poisoning (`time_analyzer.py` & `traceback_analyzer.py`)
* **Problem:** Out-of-order or future-dated historical records (`elapsed_seconds < 0`) caused negative time deltas, corrupting rapid-fire velocity and impossible travel calculations.
* **Requirement:** Ignore future-dated history records relative to the current transaction timestamp (or use `abs()` only where appropriate, ensuring future records cannot poison backward lookback windows) in `time_analyzer.py`, `traceback_analyzer.py`, and `location_checker.py`.
* **Acceptance Criteria:** `T-013` passes; negative elapsed times do not suppress velocity detection or produce negative intervals.

#### `T-014` / `MED-01` / `MED-02`: Flatten Top-Level Fields on Quarantine Records & Merge Quarantine History in `get_account_transactions()`
* **Problem:**
  * `MED-02`: `quarantine_transaction()` wrapped the original transaction inside `original_payload` without preserving top-level fields (`user_id`, `account_id`, `amount`, `timestamp`, `location`, `merchant_category`, `risk_score`, `flagged_reasons`), breaking UI tables and lookback queries.
  * `MED-01` / `T-014`: `DBClient.get_account_transactions()` only queried the main transactions table, making the velocity and traceback analyzers blind to prior quarantined transactions from the same user.
* **Requirement:**
  1. Preserve top-level transaction attributes (`user_id`, `account_id`, `amount`, `timestamp`, `location`, `merchant`, `risk_score`, `action`, `flagged_reasons`) on every quarantined item in addition to `original_payload` and `quarantine_status`.
  2. Update `DBClient.get_account_transactions(user_id)` to query/merge records from **both** main (`fraud-detection-transactions`) and quarantine (`fraud-quarantine`) storage, deduplicated by `transaction_id` and sorted chronologically.
* **Acceptance Criteria:** `T-014` passes; rapid-fire or impossible-travel attacks across quarantined transactions are caught immediately.

#### `MED-03`: Curated Demo Scenarios in `scripts/replay_stream.py`
* **Problem:** `replay_stream.py` lacked deterministic, high-impact fraud scenarios for the `<30s` live review demo.
* **Requirement:** Include curated demo transactions covering normal approval (`APPROVE`), moderate amount anomaly (`AMOUNT_ANOMALY -> REVIEW_QUEUE`), and multi-factor impossible travel + velocity attack (`BLOCK`), plus a `--demo` or fast replay mode targeting port `8081` / local pipeline.
* **Acceptance Criteria:** Running `replay_stream.py` populates all three action tiers (`APPROVE`, `REVIEW_QUEUE`, `BLOCK`) predictably.

#### `MED-04` & `MED-05`: Graceful Optional Imports (`pandas`, `joblib`, `azure`)
* **Problem:** Unconditional top-level `import pandas`, `import joblib`, or `import azure.functions` crashes minimal Python 3.12 environments (such as AWS Lambda without heavy C-extensions).
* **Requirement:** Wrap `pandas`, `joblib`, `sklearn`, and `azure.functions` imports in `try/except ImportError` blocks with pure-Python heuristic fallbacks.
* **Acceptance Criteria:** Core pipeline (`RuleEngine`, `lambda_function`, `stream_monitor`) runs with zero third-party packages required.

#### `MED-06`: Conditional Update on Quarantine Release (`update_quarantine_status`)
* **Problem:** Releasing or updating a non-existent `transaction_id` in DynamoDB silently created a blank stub item instead of failing with `not_found`.
* **Requirement:** Add `ConditionExpression="attribute_exists(transaction_id)"` to DynamoDB `update_item` in `quarantine_manager.py` / `db_client.py` and verify existence in local fallback mode, returning `False` / HTTP `404` when the transaction ID does not exist.
* **Acceptance Criteria:** Releasing a non-existent transaction ID returns `404 Not Found` without creating phantom records.

#### `T-015` (Backend): Safe URL Decoding & Non-Dict JSON Body Handling in `lambda_function.py`
* **Problem:** URL-encoded path parameters (e.g., `/transactions/txn%2F123`) were not decoded via `urllib.parse.unquote`, and valid JSON payloads that are not dicts (e.g., `[1, 2, 3]`, `"string"`, `123`) caused `AttributeError: 'list' object has no attribute 'get'`.
* **Requirement:** Apply `urllib.parse.unquote()` to path parameters and validate `isinstance(payload, dict)` after `json.loads()`, returning HTTP `400` if the parsed JSON root is not a dictionary (unless explicitly handling a batch list where each item is validated as a `dict`).
* **Acceptance Criteria:** `T-015` passes with HTTP `400` on malformed/non-dict JSON bodies and proper URL decoding on path IDs.

---

### 3.3 Agent 4 — The Frontend/Dashboard Agent (`stream_monitor.py` & UI)

#### `CRIT-08`: Default Dashboard Port `8081`
* **Problem:** `src/Fraud_Detection_Model/stream_monitor.py` and `launch_monitor.bat` defaulted to port `8080`, conflicting with local services and customer specifications.
* **Requirement:** Change default port to `8081` across `stream_monitor.py`, `launch_monitor.bat`, and CLI argument defaults (`--port 8081`).
* **Acceptance Criteria:** Starting `stream_monitor.py` without flags binds to `http://localhost:8081`.

#### `CRIT-09`: Interactive Multi-Criteria Filter Bar
* **Problem:** Analysts had no way to filter the live transaction stream by decision status, date/time window, or risk score range.
* **Requirement:** Add a filter bar in the dashboard UI supporting:
  1. **Action Type Filter:** All, `APPROVE`, `REVIEW_QUEUE` / `QUARANTINED`, `BLOCK`.
  2. **Risk Score Range Filter:** Min/Max score inputs (`0` to `100`).
  3. **Date/Time or Search Filter:** Date range or quick search/date filter, plus a **Reset Filters** button (`UX-06`).
* **Acceptance Criteria:** Filtering dynamically updates the displayed transaction table and preserves filter state across background refreshes.

#### `CRIT-10`: Offline Inline SVG Origin Map Marker in Slide-In Detail Sidebar
* **Problem:** Investigation sidebar lacked a visual geographic origin map or relied on external map tiles that fail offline.
* **Requirement:** Render an inline, zero-dependency SVG world map inside the slide-in transaction detail sidebar that plots a pulsing marker pin (`<circle>`) at projected `(x, y)` coordinates based on the transaction's `location` / latitude-longitude lookup, displaying the city/country label.
* **Acceptance Criteria:** Clicking any transaction row opens the slide-in sidebar with a visible inline SVG map and animated origin marker pin working 100% offline.

#### `HIGH-02`: Standardized Action Badge Colors & Labels
* **Problem:** Inconsistent action labels (`ALLOW` vs `APPROVE`, `QUARANTINE` vs `REVIEW_QUEUE`) and non-standard badge colors.
* **Requirement:** Normalize action badges with distinct semantic styling:
  * `APPROVE`: Emerald Green
  * `REVIEW_QUEUE`: Amber / Gold
  * `BLOCK`: Crimson Red
  * `QUARANTINED`: Purple / Violet (for quarantine status badge)
* **Acceptance Criteria:** All badges render with the exact semantic colors and normalized labels.

#### `HIGH-05`: Last 5 Transactions Traceback Mini-Table in Sidebar (Including Quarantined)
* **Problem:** Sidebar traceback view did not show a clear 5-row historical mini-table or omitted quarantined transactions.
* **Requirement:** In the `/transactions/<id>` detail endpoint and sidebar UI, return and render the **last 5 most recent transactions** for that `user_id`/`account_id` merged across both main and quarantine tables, showing timestamp, amount, location, risk score, and status badge.
* **Acceptance Criteria:** Sidebar displays up to 5 recent account transactions in a clean mini-table including quarantined items.

#### `HIGH-06`: `DBClient` Integration & Live TPS Calculation in `stream_monitor.py`
* **Problem:** `stream_monitor.py` read raw files directly instead of integrating with `DBClient`, and TPS (Transactions Per Second) was static or missing.
* **Requirement:** Connect `stream_monitor.py` to `DBClient` (with safe local JSON fallback) and compute live TPS based on recent transaction timestamps / ingestion window.
* **Acceptance Criteria:** Dashboard header displays live TPS metrics and serves data seamlessly from `DBClient` + local stream files.

#### `HIGH-07` / `T-015` (Frontend): Prevent DOM XSS & Harden HTTP Request Parsing
* **Problem:** Unescaped fields (`merchant`, `user_id`, `location`, `transaction_id`) injected into `innerHTML` allow DOM XSS (`<script>alert(1)</script>`), and `stream_monitor.py` crashed on non-dict JSON bodies or URL-encoded transaction IDs.
* **Requirement:**
  1. Implement an `escapeHtml()` helper in frontend JavaScript and sanitize all dynamic transaction strings before inserting into `innerHTML`.
  2. In `stream_monitor.py`, decode path parameters with `urllib.parse.unquote()`, parse query params safely, and verify `isinstance(body, dict)` on `POST /transactions/<id>/release` (returning HTTP `400` on invalid JSON or non-dict payloads).
* **Acceptance Criteria:** Malicious HTML/script payloads in transaction fields render harmlessly as escaped text; `T-015` passes against `stream_monitor.py`.

#### `HIGH-08`: Interactive Quarantine Release Button, Loading/Error States & Clipboard Fallback
* **Problem:** Sidebar lacked a working one-click "Release / Approve from Quarantine" action with loading/error states, failed silently on HTTP 404/500, and crashed when `navigator.clipboard` was unavailable in non-HTTPS contexts.
* **Requirement:**
  1. Add an interactive **Release / Approve Transaction** button in the sidebar for `REVIEW_QUEUE` / `QUARANTINED` items that calls `POST /transactions/<id>/release`, shows a `"Releasing..."` loading state, handles HTTP 404/500 with clear user error banners, and updates the UI status upon success.
  2. Add a `<textarea>` + `document.execCommand('copy')` fallback when `navigator.clipboard` is undefined.
* **Acceptance Criteria:** Analysts can release quarantined transactions directly from the sidebar with full visual feedback and error handling.

#### `UX-01` – `UX-06`: Dashboard Usability & Responsive Polish
* **`UX-01`:** Preserve the `.active-row` highlight on the currently inspected transaction across automatic polling refreshes.
* **`UX-02`:** Make the slide-in detail sidebar responsive (`width: 100vw` / stacked scrollable layout at `<= 480px` / `375px` mobile viewports).
* **`UX-03`:** Disable "Previous" and "Next" pagination buttons at page boundaries (`page <= 1` or `page >= totalPages`).
* **`UX-04`:** Add a **Pause / Resume Auto-Refresh** toggle and a **Manual Refresh** button in the top controls.
* **`UX-05`:** Display clear empty-state messages when no transactions match active filters.
* **`UX-06`:** Add a one-click **Reset Filters** button that restores default filter values.

---

### 3.4 Agent 5 — The Demo & Documentation Agent (Docs, Demo Script & Payloads)

#### `HIGH-10`: Production Documentation, `<30s` Live Demo Playbook & Fallback Assets
* **Problem:** Documentation referenced outdated regions (`us-east-1`), Python 3.9/3.11, or port `8080`, and lacked a tight `<30s` interim review script with ready-to-fire JSON payloads and offline fallback outputs.
* **Requirement:**
  1. Update `README.md` and `docs/*` (`ARCHITECTURE.md`, `API_REFERENCE.md`, `DEPLOYMENT.md`, `DEMO_SCRIPT.md`, `SLIDE_TALKING_POINTS.md`) to consistently reflect:
     * **AWS Region:** `eu-north-1` (Stockholm)
     * **Runtime:** Python 3.12
     * **Dashboard Port:** `8081` (`http://localhost:8081`)
     * **DynamoDB Tables:** `fraud-detection-transactions` and `fraud-quarantine`
     * **7 Fraud Intelligence Features:** Amount Anomaly (`z-score` + cold-start thresholds), Velocity / Rapid-Fire Detection, Geographic Impossible Travel (`Haversine` + `0.0`-min teleportation guard), Merchant Category Risk Scoring, Historical User Traceback Analysis, Calibrated ML + Heuristic Ensemble (`0..100` integer score), and Automated Quarantine & Analyst Release Workflow.
  2. Create a punchy **`<30s` Live Review Demo Script** highlighting:
     * **Scenario A:** Normal transaction -> `APPROVE` (Green badge, score `< 40`).
     * **Scenario B:** Unusual $3,200 purchase -> `AMOUNT_ANOMALY` -> `REVIEW_QUEUE` (Amber badge, score `40–79`), inspecting the SVG Origin Map & 5-txn Traceback in the sidebar, and clicking **Release from Quarantine**.
     * **Scenario C:** Simultaneous Tokyo/London impossible travel + velocity attack -> `BLOCK` (Red badge, score `>= 80`).
  3. Provide curated test payloads in `demo/payloads/*.json` (`approve_normal.json`, `review_amount_anomaly.json`, `block_impossible_travel.json`) and pre-captured CLI/API output logs in `demo/fallbacks/*.txt`.
* **Acceptance Criteria:** All docs, demo scripts, JSON payloads, and fallback text files are complete, internally consistent (`eu-north-1`, Python 3.12, port `8081`), and executable in under 30 seconds.

---

## 4. Verification & Sign-Off Protocol

1. **Automated Unit & Adversarial QA Gate (Agent 3):**
   * Run the complete unit test suite (`tests/`) and adversarial QA runner covering `T-001` through `T-015`.
   * Zero test failures or unhandled exceptions permitted.
2. **Infrastructure & Offline Verification Gate (Agent 1):**
   * Run `python scripts/verify_aws_infrastructure.py --offline` (and live `eu-north-1` verification if credentials are configured).
3. **End-to-End Customer Acceptance Gate (Agent 6):**
   * Re-verify all 10 Critical Blockers, 10 High-Priority tickets, 8 Medium tickets, and 6 UX polish items against the live dashboard on port `8081` and Lambda handler endpoints.
