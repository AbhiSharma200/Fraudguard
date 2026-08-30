import azure.functions as func
import logging
import json
from src.router_function import FraudRouter

app = func.FunctionApp()

router = FraudRouter(model_path="fraud_model.pkl")

@app.event_hub_message_trigger(arg_name="azeventhub", event_hub_name="evh-fraudguard-stream",
                               connection="EVENTHUB_CONNECTION") 
def fraud_router_trigger(azeventhub: func.EventHubEvent):
    """
    Azure Function triggered by Event Hub events.
    Routes transactions through rule engine and ML model, then saves decision.
    """
    logging.info('Python EventHub trigger processed an event: %s',
                 azeventhub.get_body().decode('utf-8'))
    
    try:
        # Parse the JSON payload
        event_body = azeventhub.get_body().decode('utf-8')
        tx_data = json.loads(event_body)
        
        # Route the transaction
        result = router.route_transaction(tx_data)
        
        logging.info(f"Transaction {result.get('transaction_id')} routed. Decision: {result.get('decision')}")
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Event Hub message as JSON: {e}")
    except Exception as e:
        logging.error(f"Error during transaction routing: {e}")

