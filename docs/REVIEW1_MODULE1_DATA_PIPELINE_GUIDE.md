# FraudGuard — Review 1 Module 1 Data Pipeline Speech & Demo Guide

> **Presenter:** Teammate 1 (Data Pipeline & Real-Time Stream Simulation Engineer)  
> **Cloud Environment:** AWS `eu-north-1` (Stockholm) — `Python 3.12` Lambda + DynamoDB + EC2 Dashboard (`Port 8081`)  

---

## 1. Presentation Structure (5 Minutes for Module 1)

### 0:00 – 1:30 | Introduction & Data Problem Statement
> *"Good morning evaluators. I am responsible for **Module 1: Data Pipeline & Real-Time Stream Simulation**.  
> In digital payment platforms, fraud must be caught in milliseconds before settlement. Because live bank feeds contain sensitive customer PII and cannot be shared publicly, my responsibility in Module 1 is to normalize financial transaction streams from the IBM AMLSim / Bank Account Fraud (BAF) schema and build a deterministic Python Replay Streaming Engine (`src/replay_stream.py`) that feeds real-time transaction events into our AWS `eu-north-1` pipeline (`Amazon Kinesis Data Streams` and `AWS Lambda`)."*

### 1:30 – 3:30 | Live Technical Demonstration (< 30 Seconds per Step)
1. **Run the Stream Producer / Lambda Ingestion Flow:**
   Open the terminal and run:
   ```powershell
   python src/replay_stream.py
   ```
2. **Highlight the Enriched Payload Structure:**
   Point out the live stream output emitting structured JSON events containing `transaction_id`, `account_id`, `amount`, `txn_type`, `ip_address`, `transaction_city`, and `timestamp`.
3. **Show the Live Analyst Dashboard on Port `8081`:**
   Open **`http://localhost:8081`** (or **`http://<ec2-ip>:8081`**) in the browser to show incoming transactions being scored by AWS Lambda (`Python 3.12`), stored in Amazon DynamoDB (`fraud-detection-transactions` and `fraud-quarantine`), and rendered in real time with origin coordinates and risk badges.

### 3:30 – 5:00 | Downstream Data Contracts & Hand-off
> *"I defined the authoritative JSON transaction schema contract (`src/transaction_schema.json`). Every event emitted by the producer carries the exact identity, velocity, and network origin fields consumed by our AWS Lambda (`Python 3.12`) Decision Router, enabling our Rule Engine (`AMOUNT_ANOMALY -> REVIEW_QUEUE`) and our 7-Feature Fraud Intelligence Engine (`TOR_EXIT_NODE` & `IMPOSSIBLE_TRAVEL -> BLOCK / QUARANTINED`) to execute seamlessly in under 50 milliseconds."*

---

## 2. Technical Q&A Defense Guide

### Q1: Why stream JSON events through a producer instead of reading a static CSV inside the scoring script?
**Answer:** In production banking systems, transactions arrive continuously as individual network events over HTTPS and stream brokers (`Amazon Kinesis Data Streams`). By decoupling `src/replay_stream.py` from our `AWS Lambda` (`fraudguard-decision-router`) handler in `eu-north-1`, the exact same Lambda function processes live stream events, REST API requests, and CLI test payloads without changing a single line of scoring code.

### Q2: How do you prevent duplicate transactions if a network retry sends the same event twice?
**Answer:** Every event generated in Module 1 carries a unique `transaction_id`. Our Amazon DynamoDB client (`src/db_client.py`) enforces a conditional write (`ConditionExpression="attribute_not_exists(transaction_id)"`) on both `fraud-detection-transactions` and `fraud-quarantine`, returning `HTTP 409 Conflict` if a duplicate event is re-sent, guaranteeing zero double-counting in our velocity and traceback windows.

### Q3: How does your pipeline handle customer privacy and PII during academic demos?
**Answer:** Our Feature 7 PII Enrichment Layer (`src/pii_enricher.py`) exclusively uses synthetic demo profiles (`data/mock_pii_store.json`) explicitly tagged with `"data_source": "MOCK_DEMO_DATA"` and `" (MOCK)"` suffixes on every account holder name, ensuring realistic fraud correlation (such as cell-tower vs. IP location mismatch) with zero real personal data exposure.
