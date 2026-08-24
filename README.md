# FraudGuard — Real-Time Fraud Detection & Risk Scoring System

> **Project Title:** FraudGuard — Real-Time Fraud Detection & Risk Scoring System for Digital Payments  
> **Repository:** [https://github.com/AbhiSharma200/Fraudguard.git](https://github.com/AbhiSharma200/Fraudguard.git)  
> **Architecture:** Cloud-Native Event-Driven Streaming & Machine Learning Pipeline  
> **Dataset:** IBM AMLSim (Anti-Money Laundering Simulator) Master Dataset  

---

## 1. Executive Summary

Digital payment platforms process thousands of transactions per second, and a meaningful fraction are fraudulent — stolen card testing, account takeover, mule-account laundering, and velocity abuse. Fraud must be caught **before settlement**, since post-transaction review is too late.

**FraudGuard** is designed to ingest a simulated real-time financial transaction stream, evaluate each transaction using deterministic rule checks and machine learning models, and automatically route high-risk transactions to **ALLOW**, **REVIEW QUEUE**, or **BLOCK** before settlement occurs.

---

## 2. Project Architecture & 8-Module Team Breakdown

The project is structured into **8 Technical Modules** designed for a 4-developer engineering team:

```
[Module 1: Data Pipeline (DONE)] ──> [Module 3: Cloud Infrastructure (IaC)]
                │                                    │
                ├──> [Module 2: Rule Engine] ────────┼──> [Module 5: Decision Router]
                │                                    │                 │
                └──> [Module 4: ML Fraud Model] ─────┘                 ▼
                                                            [Module 6: Cosmos Audit Log]
                                                                       │
                                                                       ▼
                                                            [Module 7: Web Dashboard]
```

### Module Status Matrix

| Module | Title | Primary Tech | Assigned Role | Status |
|---|---|---|---|---|
| **Module 1** | **Data Pipeline & Real-Time Stream Simulation** | Python, pandas, Event Hubs | **Developer 1 (Completed)** | **100% COMPLETE** |
| **Module 2** | **Rule-Based Fraud Detection Engine** | Stream Analytics, SQL, Python | Developer 2 | *Next Step* |
| **Module 3** | **Cloud Infrastructure Setup & Provisioning** | Terraform IaC, Azure CLI | Developer 3 | Ready for `terraform apply` |
| **Module 4** | **ML-Based Fraud Risk Scoring Model** | Python, XGBoost, Azure ML | Developer 4 | Ready for Training |
| **Module 5** | **Decision Orchestration & Routing Logic** | Azure Functions, Python | Developer 3 / 2 | Pending Modules 2 & 4 |
| **Module 6** | **Audit Log & Data Persistence** | Azure Cosmos DB (SQL API) | Developer 4 | Schema Ready |
| **Module 7** | **Analyst Dashboard & Visualization** | HTML5, CSS3, JavaScript, Python | Developer 2 / 1 | Baseline UI Ready |
| **Module 8** | **Integration, Testing & Review Demo** | End-to-End Pipeline | Shared (All 4) | Pending Integration |

---

## 3. What Has Been Completed So Far (Module 1 Hand-off)

Developer 1 has **100% completed Module 1 (Data Pipeline & Real-Time Stream Simulation)**. Here is what is built and ready in this repository:

### Completed Work & Assets
1. **Dataset Integration & Preprocessing (`src/preprocess_amlsim.py`)**:
   - Ingested raw records from the **IBM AMLSim Master Dataset** (`data/amlsim_tx.csv`).
   - Cleaned nulls, formatted account/transaction IDs (`acc_`, `tx_fg_`), converted simulation steps to ISO-8601 UTC timestamps (`YYYY-MM-DDTHH:MM:SSZ`), normalized currency values, and computed risk indicators.
   - Production preprocessed dataset saved at `data/fraudguard_cleaned_amlsim.csv`.
2. **JSON Schema Payload Contract (`schema/transaction_schema.json`)**:
   - Established the authoritative JSON schema contract for all stream payloads.
3. **Replay Streaming Engine (`src/replay_stream.py`)**:
   - High-performance Python producer reading cleaned records and emitting micro-batch transaction events every 500ms (2 TPS) to Azure Event Hubs (`evh-fraudguard-stream`).
4. **FraudGuard Live Web Dashboard (`src/stream_monitor.py`)**:
   - Real-time web application hosted at `http://localhost:8080` displaying *Total Transactions*, *Flagged Suspicious Count*, *Fraud Risk Rate (%)*, *Processing Speed (TPS)*, and a **Live JSON Payload Inspector**.
5. **Infrastructure-as-Code Specifications (`terraform/`)**:
   - Complete Terraform scripts (`main.tf`, `variables.tf`, `outputs.tf`) provisioning all 6 Azure Cloud Services.
6. **Data Comparison & Audit Tool (`src/compare_datasets.py`)**:
   - Command-line tool to compare raw unprocessed CSV vs preprocessed production CSV.

---

## 4. Developer Guide: How to Continue with Next Modules

If you are a developer taking over or building the next modules, follow these exact technical hand-off instructions:

### For Developer 2 — Implementing Module 2 (Rule-Based Fraud Engine)
1. **Input Stream**: Subscribe your rule processor to the stream emitted by `src/replay_stream.py` on Azure Event Hubs (`evh-fraudguard-stream`).
2. **Data Contract**: Use the payload schema specified in `schema/transaction_schema.json`.
3. **Rules to Implement**:
   - **Velocity Rule**: Flag transactions where same `source_account` has $> 5$ attempts in a sliding 6-hour window.
   - **Channel Risk Rule**: Flag transactions where `txn_type` is `WIRE` or `CHECK` and `amount > $150.00`.
   - **Amount Anomaly Rule**: Flag any transaction where `amount > $180.00`.
4. **Output Format**: Emit a rule score payload `{"transaction_id": "...", "rule_score": 1.0, "triggered_rules": ["WIRE_HIGH_AMOUNT"]}` to the decision router (Module 5).

### For Developer 3 — Implementing Module 3 (Cloud Infrastructure Provisioning)
1. **Prerequisites**: Install Azure CLI (`az`) and Terraform (`>= 1.3.0`).
2. **Deployment**:
   ```bash
   cd terraform
   az login
   terraform init
   terraform apply
   ```
3. **Services Provisioned**: Azure Event Hubs, Stream Analytics, Azure ML Workspace, Cosmos DB (`FraudGuardDB/AuditLog`), Azure Functions, and App Service.
4. **Connection Strings**: Collect connection outputs from `terraform output` and update environment variables for the team.

### For Developer 4 — Implementing Module 4 (ML Fraud Risk Model)
1. **Dataset**: Use the preprocessed dataset `data/fraudguard_cleaned_amlsim.csv`.
2. **Model Specs**: Train an XGBoost or Random Forest classifier predicting target column `is_suspicious`.
3. **Metrics Target**: Aim for $\text{Recall} \ge 90\%$ and $\text{Precision} \ge 80\%$.
4. **Deployment**: Export model binary and deploy a real-time scoring REST endpoint `/score` on Azure Machine Learning Workspace (`aml-fraudguard-workspace`).

---

## 5. Directory & File Reference

```
Fraudguard/
├── data/
│   ├── amlsim_tx.csv                       # Raw AMLSim Master dataset
│   ├── fraudguard_cleaned_amlsim.csv       # Production preprocessed dataset (Cleaned)
│   └── baf_cleaned_sample.csv              # BAF dataset sample
├── schema/
│   └── transaction_schema.json             # Authoritative JSON payload contract
├── src/
│   ├── preprocess_amlsim.py                # Data cleaning & preprocessing pipeline script
│   ├── replay_stream.py                    # Real-time event replay stream producer
│   ├── stream_monitor.py                   # Live FraudGuard business web dashboard server
│   └── compare_datasets.py                 # Side-by-side raw vs preprocessed comparison tool
├── docs/
│   ├── DATA_DICTIONARY.md                  # Feature dictionary & variable specifications
│   └── REVIEW1_MODULE1_DATA_PIPELINE_GUIDE.md # Review 1 presentation script & Q&A defense
├── terraform/                              # Infrastructure-as-Code (IaC) Terraform scripts
│   ├── main.tf                             # Provisioning specifications for 6 Azure services
│   ├── variables.tf                        # Region, SKU, and tagging parameters
│   └── outputs.tf                          # Inter-module connection string outputs
├── compare_data.bat                        # 1-click shortcut for dataset comparison
├── launch_monitor.bat                      # 1-click shortcut for web dashboard (localhost:8080)
├── run_replay.bat                          # 1-click shortcut for stream producer
├── .gitignore                              # Git ignore rules
└── README.md                               # Project documentation & developer guide
```

---

## 6. Quickstart Commands for Developers

### 1. Install Dependencies
```bash
pip install pandas azure-eventhub jsonschema
```

### 2. Re-run Data Preprocessing
```bash
python src/preprocess_amlsim.py
```

### 3. Compare Raw vs. Preprocessed Data
```bash
compare_data
```
*(or `python src/compare_datasets.py`)*

### 4. Start Real-Time Stream Producer
```bash
run_replay
```
*(or `python src/replay_stream.py`)*

### 5. Launch FraudGuard Dashboard
```bash
launch_monitor
```
*(or `python src/stream_monitor.py`)*  
Then open **`http://localhost:8080`** in your browser.

---

## 7. Commit & Git Handoff

To push changes to GitHub:
```bash
git_push
```
*(Target Remote: `https://github.com/AbhiSharma200/Fraudguard.git`)*
