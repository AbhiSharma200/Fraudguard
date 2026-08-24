# FraudGuard — Review 1 Module 1 Data Pipeline Speech & Demo Script

> **Presenter:** Teammate 1 (Data Pipeline & Stream Simulation Engineer)  

---

## 1. Presentation Structure (5 Minutes for Your Part)

### 0:00 - 1:30 | Introduction & Data Problem Statement
> *"Good morning evaluators. I am Teammate 1, responsible for **Module 1: Data Pipeline & Real-Time Stream Simulation**.
> In digital payment systems, live fraud detection requires streaming transactions as they happen. Because live bank data cannot be shared publicly, my responsibility in Module 1 is to clean the industry-standard Bank Account Fraud (BAF) NeurIPS dataset and build a high-performance Python Replay Streaming Engine (`replay_stream.py`) that feeds real-time transaction events into Azure Event Hubs."*

### 1:30 - 3:30 | Live Technical Demonstration
1. Open terminal and run:
   ```bash
   python src/replay_stream.py
   ```
2. Point out the live stream output emitting transaction JSON events with timestamps, velocity signals, amounts, and ground-truth flags.
3. Open `http://localhost:8080` in browser to show the **Live Payload Inspector** and TPS telemetry counters updating in real time.

### 3:30 - 5:00 | Downstream Data Contracts & Hand-off
> *"I defined the authoritative JSON transaction schema contract (`transaction_schema.json`). Every event emitted by my stream includes critical fraud signals — such as 6-hour transaction velocity and geo-distance — which my teammates' downstream modules (Stream Analytics rules and ML scoring) consume seamlessly."*

---

## 2. Technical Q&A Defense Guide

### Q1: Why not just read the CSV file directly inside Stream Analytics or ML?
**Answer:** In a real-world enterprise architecture, transactions do not sit in static CSV files; they arrive via high-throughput messaging brokers. By building a stream replay engine that publishes to Azure Event Hubs, we realistically model production stream ingestion.

### Q2: What happens if the stream rate surges?
**Answer:** The Python replay engine is decoupled from the ingestion broker. Azure Event Hubs partitions handle scaling automatically without dropping payloads.
