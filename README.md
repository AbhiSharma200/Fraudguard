# FraudGuard — Module 1: Data Pipeline & Real-Time Stream Simulation

> **Project Title:** FraudGuard – Real-Time Fraud Detection & Risk Scoring System for Digital Payments  
> **Module:** Module 1 — Data Pipeline & Real-Time Stream Simulation  
> **Module Owner:** Teammate 1 (You)  
> **Dataset:** Bank Account Fraud (BAF) Suite — Feedzai / NeurIPS 2022  
> **Ingestion Target:** Azure Event Hubs (`evh-fraudguard-stream`)  

---

## 1. Overview & Objective
Digital payment platforms process thousands of transactions per second. In this module, you prepare the Bank Account Fraud (BAF) dataset, define the authoritative JSON transaction schema, and run a high-performance Python **Replay Streaming Engine (`replay_stream.py`)** that pushes live transaction events into **Azure Event Hubs** at a controlled interval (e.g., 500ms per event).

---

## 2. Directory Structure

```
fraudguard-datapipeline/
├── data/
│   └── baf_cleaned_sample.csv             # Cleaned Bank Account Fraud (BAF) dataset sample
├── schema/
│   └── transaction_schema.json            # JSON schema contract for all downstream modules
├── src/
│   ├── replay_stream.py                   # Main Python replay stream producer script
│   └── stream_monitor.py                  # Live stream telemetry web UI server (http://localhost:8080)
├── docs/
│   ├── DATA_DICTIONARY.md                 # Complete BAF dataset feature dictionary
│   └── REVIEW1_MODULE1_DATA_PIPELINE_GUIDE.md  # Review 1 presentation speech & demo script
├── run_replay.bat                         # One-click shortcut to launch replay stream
├── launch_monitor.bat                     # One-click shortcut to launch web monitor
└── README.md                              # Project documentation
```

---

## 3. Quick Start Commands

### Option A: Run Stream Replay Engine (Terminal)
```bash
python src/replay_stream.py
```

### Option B: Launch Visual Web Telemetry Monitor
```bash
python src/stream_monitor.py
```
Then open `http://localhost:8080` in your web browser.
