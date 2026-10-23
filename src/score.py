"""
Legacy Azure ML Scoring Entry Point (Deprecated — Migrated to AWS Lambda `src/lambda_function.py`).
Retained with guarded optional imports for backwards compatibility.
"""

import json
import os
import logging

try:
    import joblib
    import pandas as pd
except ImportError:
    joblib = None
    pd = None

try:
    from azureml.core.model import Model
except ImportError:
    Model = None

model = None


def init():
    """
    Initialize and cache the ML model in memory if available.
    """
    global model
    try:
        if joblib is None:
            model = None
            return
        model_path = os.path.join(os.getenv("AZUREML_MODEL_DIR", "."), "fraud_model.pkl")
        if not os.path.exists(model_path):
            model_path = "fraud_model.pkl"
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            logging.info("Model loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading model: {e}")
        model = None


def run(raw_data):
    """
    Execute batch ML scoring on raw JSON payload.
    """
    logging.info("Request received")
    try:
        if model is None or pd is None:
            return json.dumps({"results": [], "warning": "ML model or pandas layer not loaded"})
        data = json.loads(raw_data)["data"]
        df = pd.DataFrame(data)
        drop_cols = ["transaction_id", "source_account", "destination_account", "timestamp", "is_suspicious"]
        df_model = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
        probs = model.predict_proba(df_model)
        scores = []
        for i, prob in enumerate(probs):
            score = float(prob[1]) if probs.shape[1] > 1 else 0.0
            scores.append({"index": i, "ml_risk_score": score})
        return json.dumps({"results": scores})
    except Exception as e:
        error = str(e)
        logging.error(error)
        return json.dumps({"error": error})
