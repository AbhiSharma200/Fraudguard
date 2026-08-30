import os
import json
from datetime import datetime
try:
    from azure.cosmos import CosmosClient, PartitionKey
    from azure.cosmos.exceptions import CosmosHttpResponseError
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False

class DBClient:
    """
    Cosmos DB Client for Module 6.
    Connects to Azure Cosmos DB if environment variables are present.
    Falls back to a local JSON file for local testing.
    """
    def __init__(self, fallback_path="data/audit_log.json"):
        self.endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
        self.key = os.environ.get("COSMOS_DB_KEY")
        self.db_name = "FraudGuardDB"
        self.container_name = "AuditLog"
        
        self.use_cosmos = COSMOS_AVAILABLE and self.endpoint and self.key
        self.fallback_path = fallback_path
        
        if self.use_cosmos:
            print(f"Connecting to Cosmos DB at {self.endpoint}")
            self.client = CosmosClient(self.endpoint, self.key)
            self.database = self.client.create_database_if_not_exists(id=self.db_name)
            self.container = self.database.create_container_if_not_exists(
                id=self.container_name, 
                partition_key=PartitionKey(path="/transaction_id"),
                offer_throughput=400
            )
        else:
            print("Cosmos DB credentials missing. Using local JSON fallback.")
            if not os.path.exists(self.fallback_path):
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.fallback_path), exist_ok=True)
                with open(self.fallback_path, "w") as f:
                    json.dump([], f)

    def log_transaction(self, tx_data):
        """
        Logs the transaction decision to Cosmos DB (or local JSON fallback).
        """
        # Ensure we have an id for Cosmos DB
        if "id" not in tx_data:
            tx_data["id"] = tx_data.get("transaction_id", str(datetime.utcnow().timestamp()))
            
        tx_data["_ts"] = datetime.utcnow().isoformat() + "Z"
        
        if self.use_cosmos:
            try:
                self.container.upsert_item(tx_data)
                return True
            except CosmosHttpResponseError as e:
                print(f"Failed to insert into Cosmos DB: {e.message}")
                return False
        else:
            # Fallback to local
            with open(self.fallback_path, "r") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []

            logs.append(tx_data)

            with open(self.fallback_path, "w") as f:
                json.dump(logs, f, indent=2)

            return True

if __name__ == "__main__":
    db = DBClient()
    db.log_transaction({
        "transaction_id": "test_tx_cosmos_1",
        "decision": "ALLOW",
        "reason": "Rule score low, ML score low"
    })
    print(f"Log operation complete.")
