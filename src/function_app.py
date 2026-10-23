"""
Legacy Azure Event Hub Function Trigger (Deprecated — Migrated to AWS Lambda `src/lambda_function.py`).
Retained with guarded optional imports so importing this module without `azure-functions` installed never crashes.
"""

import logging
import json

try:
    import azure.functions as func
except ImportError:
    func = None

try:
    from src.router_function import FraudRouter
except ImportError:
    from router_function import FraudRouter

router = FraudRouter(model_path="fraud_model.pkl")

if func is not None:
    app = func.FunctionApp()

    @app.event_hub_message_trigger(
        arg_name="azeventhub",
        event_hub_name="evh-fraudguard-stream",
        connection="EVENTHUB_CONNECTION"
    )
    def fraud_router_trigger(azeventhub):
        """
        Legacy Azure Function triggered by Event Hub events.
        """
        try:
            event_body = azeventhub.get_body().decode("utf-8")
            tx_data = json.loads(event_body)
            result = router.route_transaction(tx_data)
            logging.info(
                "Transaction %s routed. Decision: %s",
                result.get("transaction_id"),
                result.get("decision")
            )
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse Event Hub message as JSON: {e}")
        except Exception as e:
            logging.error(f"Error during transaction routing: {e}")
else:
    app = None
