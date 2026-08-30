import json
import joblib
import pandas as pd
import os
import logging
from azureml.core.model import Model

def init():
    """
    This function is called when the container is initialized/started, typically after create/update of the deployment.
    You can write the logic here to perform init operations like caching the model in memory.
    """
    global model
    try:
        # AZUREML_MODEL_DIR is an environment variable created during deployment.
        # It is the path to the model folder (./azureml-models/$MODEL_NAME/$VERSION)
        model_path = os.path.join(os.getenv("AZUREML_MODEL_DIR", "."), "fraud_model.pkl")
        if not os.path.exists(model_path):
            # Fallback for local testing
            model_path = "fraud_model.pkl"
            
        model = joblib.load(model_path)
        logging.info("Model loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading model: {e}")
        model = None

def run(raw_data):
    """
    This function is called for every invocation of the endpoint to perform the actual scoring/prediction.
    """
    logging.info("Request received")
    
    try:
        # Expected input format: {"data": [{"amount": 250, "txn_type": "WIRE", "simulation_step": 1}]}
        data = json.loads(raw_data)["data"]
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data)
        
        # Ensure we drop columns the pipeline wasn't trained on
        drop_cols = ["transaction_id", "source_account", "destination_account", "timestamp", "is_suspicious"]
        df_model = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
        
        # Predict probability of class 1 (is_suspicious)
        probs = model.predict_proba(df_model)
        
        # Format the result
        scores = []
        for i, prob in enumerate(probs):
            score = float(prob[1]) if probs.shape[1] > 1 else 0.0
            scores.append({"index": i, "ml_risk_score": score})
            
        return json.dumps({"results": scores})

    except Exception as e:
        error = str(e)
        logging.error(error)
        return json.dumps({"error": error})

