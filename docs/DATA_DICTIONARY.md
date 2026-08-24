# FraudGuard — Module 1: Bank Account Fraud (BAF) Data Dictionary

> **Dataset Reference:** Bank Account Fraud (BAF) Suite — Feedzai / NeurIPS 2022  
> **Source:** `github.com/feedzai/bank-account-fraud`  
> **Module Owner:** Teammate 1 (Data Pipeline & Real-Time Stream Simulation)  

---

## 1. Feature Specifications

| Feature Name | Data Type | Sample Value | Description & Domain Significance |
|---|---|---|---|
| `transaction_id` | String | `tx_1001` | Unique transaction event identifier generated for event tracking. |
| `user_id` | String | `usr_4012` | Account or cardholder identifier. |
| `timestamp` | Datetime | `2026-08-23T19:00:00Z` | ISO-8601 UTC timestamp of payment event. |
| `amount` | Float | `4500.00` | Transaction monetary value in USD. High amounts combined with velocity signal potential fraud. |
| `velocity_6h` | Integer | `8` | Total transaction attempts by the same user in the past 6 hours. High velocity indicates card testing or account takeover. |
| `zip_count_4w` | Integer | `6` | Number of distinct ZIP codes used by account in past 4 weeks. Spikes indicate geo-impossible activity. |
| `payment_type` | String | `online_checkout` | Payment channel (`card_present`, `online_checkout`, `contactless`). Card-not-present carries higher risk. |
| `merchant_category`| String | `electronics` | Merchant sector (`electronics`, `crypto_exchange`, `jewelry`, `grocery`). |
| `geo_distance_km` | Float | `780.5` | Distance in km from primary billing address. |
| `device_os` | String | `windows` | Initiating device OS (`android`, `ios`, `windows`, `mac`, `linux`). |
| `fraud_bool` | Integer (0/1)| `1` | Ground truth label (0 = Legitimate, 1 = Fraudulent). |

---

## 2. Summary Statistics & Fraud Characteristics

- **Total Records in Benchmark Subset:** 20 Records
- **Legitimate Transactions (`fraud_bool = 0`):** 12 (60%)
- **Fraudulent Transactions (`fraud_bool = 1`):** 8 (40%)
- **Key Fraud Signals Identified:**
  - High transaction velocity (`velocity_6h > 5`)
  - Large geo-distance from billing address (`geo_distance_km > 500 km`)
  - High-risk categories (`crypto_exchange`, `wire_transfer`, `electronics`, `jewelry`)
