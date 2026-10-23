"""
AWS Lambda Entry Point for FraudGuard (`fraudguard-decision-router`)
Primary Handler: `handler(event, context)` (with alias `lambda_handler = handler`)
Handles:
  - Direct Lambda invocation (`{"transaction_id": ...}`)
  - API Gateway / Lambda Function URL (`POST /`, `POST /score`, `GET /transaction/{id}`, `POST /release`)
  - Amazon Kinesis Data Stream batch events (`event["Records"]`)
Always wraps execution in a top-level try/except returning valid JSON responses.
"""

import os
import sys
import json
import base64
import logging
import urllib.parse
from typing import Any, Dict, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from src.router_function import FraudRouter
    from src.db_client import DuplicateTransactionError
except ImportError:
    from router_function import FraudRouter
    from db_client import DuplicateTransactionError

logger = logging.getLogger("fraudguard.lambda")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

_ROUTER_INSTANCE: Optional[FraudRouter] = None


def get_router(reset: bool = False) -> FraudRouter:
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None or reset:
        _ROUTER_INSTANCE = FraudRouter()
    return _ROUTER_INSTANCE


def _json_response(status_code: int, body_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": int(status_code),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-API-Key"
        },
        "body": json.dumps(body_dict)
    }


def _extract_http_info(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    path = event.get("rawPath") or event.get("path") or "/"
    method = (
        event.get("httpMethod")
        or ((event.get("requestContext") or {}).get("http") or {}).get("method")
        or "POST"
    ).upper()
    headers = event.get("headers") if isinstance(event.get("headers"), dict) else {}
    return method, path, headers


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    Top-level AWS Lambda handler (`lambda_function.handler`) with guaranteed JSON error handling.
    Catches all unhandled exceptions and returns HTTP 500 with `{"error": str(e)}`.
    """
    try:
        if not isinstance(event, dict):
            return _json_response(400, {
                "error": "INVALID_EVENT",
                "message": "Lambda event must be a JSON object."
            })

        router = get_router()
        method, path, headers = _extract_http_info(event)

        if method == "OPTIONS":
            return _json_response(200, {"status": "ok"})

        # Route 1: GET /transaction/{id}
        if path.startswith("/transaction/") and method == "GET":
            parts = [p for p in path.split("/") if p]
            raw_tx_id = parts[1] if len(parts) >= 2 else None
            tx_id = urllib.parse.unquote(raw_tx_id) if raw_tx_id else None
            if not tx_id:
                return _json_response(400, {"error": "MISSING_TRANSACTION_ID"})
            record = router.db.get_transaction_by_id(tx_id)
            if not record:
                return _json_response(404, {"error": "NOT_FOUND", "transaction_id": tx_id})
            return _json_response(200, record)

        # Route 2: POST /release (Quarantine release endpoint)
        if path == "/release" and method == "POST":
            raw_body = event.get("body", "{}")
            body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body if raw_body is not None else {})
            if not isinstance(body, dict):
                return _json_response(400, {
                    "error": "INVALID_BODY",
                    "message": "Release request body must be a JSON object."
                })
            tx_id = body.get("transaction_id")
            if not tx_id:
                return _json_response(400, {"error": "MISSING_TRANSACTION_ID"})
            rel_res = router.quarantine_manager.release_transaction(
                transaction_id=str(tx_id),
                analyst_notes=body.get("analyst_notes", "Released via Lambda /release API"),
                auth_token=body.get("api_key"),
                headers=headers
            )
            return _json_response(rel_res["http_status"], rel_res)

        # Route 3: Kinesis Stream Event Batch
        if "Records" in event and isinstance(event["Records"], list):
            processed = []
            has_block = False
            for rec in event["Records"]:
                kinesis_data = (rec.get("kinesis") or {}).get("data", "")
                try:
                    decoded = base64.b64decode(kinesis_data).decode("utf-8")
                    tx_payload = json.loads(decoded)
                except Exception:
                    tx_payload = json.loads(kinesis_data) if isinstance(kinesis_data, str) else kinesis_data
                scored = router.route_transaction(tx_payload, event_headers=headers)
                if scored.get("decision") == "BLOCK":
                    has_block = True
                processed.append(scored)
            return _json_response(202 if has_block else 200, {"processed": processed})

        # Route 4: API Gateway / Function URL (`event["body"]`) or Direct Transaction Payload
        if "body" in event:
            raw_body = event["body"]
            if isinstance(raw_body, str):
                if not raw_body.strip():
                    return _json_response(400, {"error": "EMPTY_BODY", "message": "Request body cannot be empty."})
                tx_payload = json.loads(raw_body)
            elif isinstance(raw_body, dict):
                tx_payload = raw_body
            else:
                return _json_response(400, {"error": "INVALID_BODY", "message": "Unsupported body format."})
        else:
            tx_payload = event

        if not isinstance(tx_payload, dict):
            return _json_response(400, {
                "error": "VALIDATION_ERROR",
                "message": "Transaction payload must be a JSON object."
            })

        result = router.route_transaction(tx_payload, event_headers=headers)
        http_status = result.get("http_status", 202 if result.get("decision") == "BLOCK" else 200)
        return _json_response(http_status, result)

    except json.JSONDecodeError as e:
        logger.error(json.dumps({"event": "JSON_DECODE_ERROR", "error": str(e)}))
        return _json_response(400, {
            "error": "MALFORMED_JSON",
            "message": f"Invalid JSON payload: {str(e)}"
        })
    except DuplicateTransactionError as e:
        logger.warning(json.dumps({"event": "DUPLICATE_TRANSACTION", "error": str(e)}))
        return _json_response(409, {
            "error": "DUPLICATE_TRANSACTION_ID",
            "message": str(e)
        })
    except (ValueError, TypeError, KeyError) as e:
        logger.error(json.dumps({"event": "VALIDATION_ERROR", "error": str(e)}))
        return _json_response(400, {
            "error": "VALIDATION_ERROR",
            "message": str(e)
        })
    except Exception as e:
        logger.error(json.dumps({"event": "INTERNAL_HANDLER_ERROR", "error": str(e)}))
        return _json_response(500, {
            "error": str(e)
        })


# Backwards-compatible alias for unit and integration test suites
lambda_handler = handler
