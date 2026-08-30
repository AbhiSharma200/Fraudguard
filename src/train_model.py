import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib
import os

def train():
    # Load dataset
    data_path = os.path.join("..", "data", "fraudguard_cleaned_amlsim.csv")
    if not os.path.exists(data_path):
        data_path = os.path.join("data", "fraudguard_cleaned_amlsim.csv")
        
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)

    # Prepare features and target
    target_col = "is_suspicious"
    
    # Drop irrelevant columns (IDs and timestamp)
    X = df.drop(columns=[target_col, "transaction_id", "source_account", "destination_account", "timestamp"])
    y = df[target_col]

    # Preprocessing for categorical features
    categorical_features = ["txn_type"]
    numeric_features = ["amount", "simulation_step"]

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', 'passthrough', numeric_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
        ])

    # Define the model pipeline
    model = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', xgb.XGBClassifier(
            use_label_encoder=False, 
            eval_metric='logloss',
            scale_pos_weight=10  # adjust for imbalance if needed
        ))
    ])

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train model
    print("Training XGBoost model...")
    model.fit(X_train, y_train)

    # Evaluate model
    print("Evaluating model...")
    y_pred = model.predict(X_test)
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    rec = recall_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    print(f"Recall: {rec:.2f}")
    print(f"Precision: {prec:.2f}")

    if rec >= 0.90 and prec >= 0.80:
        print("Success: Met target metrics (Recall >= 0.90 and Precision >= 0.80)")
    else:
        print("Warning: Did not meet target metrics.")

    # Save model
    model_file = "fraud_model.pkl"
    joblib.dump(model, model_file)
    print(f"Model saved to {model_file}")

if __name__ == "__main__":
    train()
