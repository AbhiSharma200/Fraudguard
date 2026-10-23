"""
Database Client for FraudGuard (DynamoDB + Cosmos DB + Thread-Safe Local Fallback)
Supports:
  - Main transaction table (`fraud-detection-transactions`, TTL: 30-90 days)
  - Quarantine table (`fraud-quarantine`, TTL: 7-30 days)
  - Conditional writes (`attribute_not_exists(transaction_id)`) to prevent duplicate ID overwrites
  - GSI query on `account_id` + `timestamp` descending for Feature 2 Traceback
  - Automatic `/tmp` fallback when running in AWS Lambda read-only `/var/task` filesystem
"""

import os
import json
import math
import time
import tempfile
import threading
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from azure.cosmos import CosmosClient, PartitionKey
    from azure.cosmos.exceptions import CosmosHttpResponseError
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False

DEFAULT_DYNAMODB_TABLE = "fraud-detection-transactions"
DEFAULT_QUARANTINE_TABLE = "fraud-quarantine"
DEFAULT_AWS_REGION = "eu-north-1"
TTL_30_DAYS_SECONDS = 30 * 86400
MAIN_TTL_DAYS = 90
QUARANTINE_TTL_DAYS = 7


def _to_dynamodb_safe(obj: Any) -> Any:
    """Convert floats to Decimal recursively for DynamoDB boto3 Table resource, rejecting NaN/Inf."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("Non-finite float (NaN or Infinity) is not allowed in DynamoDB item.")
        return Decimal(str(round(obj, 6)))
    if isinstance(obj, dict):
        return {k: _to_dynamodb_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamodb_safe(v) for v in obj]
    return obj


def _from_dynamodb_safe(obj: Any) -> Any:
    """Convert Decimal back to float/int for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamodb_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_dynamodb_safe(v) for v in obj]
    return obj


def _resolve_writable_path(path: Optional[str], default_filename: str) -> Optional[str]:
    """
    Ensure fallback JSON path is writable. If running on AWS Lambda (`/var/task` read-only),
    automatically redirect to `/tmp/<default_filename>`.
    """
    if not path:
        return None
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(path):
            if os.access(path, os.W_OK):
                return path
        elif os.access(parent or ".", os.W_OK):
            return path
    except OSError:
        pass
    tmp_dir = "/tmp" if os.path.isdir("/tmp") else tempfile.gettempdir()
    return os.path.join(tmp_dir, default_filename)


class DuplicateTransactionError(Exception):
    """Raised when a transaction_id already exists in the target table."""
    pass


class DBClient:
    _lock = threading.Lock()

    def __init__(
        self,
        fallback_path: str = "data/audit_log.json",
        quarantine_fallback_path: str = "data/quarantine_log.json",
        in_memory_only: bool = False
    ) -> None:
        self.dynamodb_table_name = os.environ.get("DYNAMODB_TABLE", DEFAULT_DYNAMODB_TABLE)
        self.quarantine_table_name = os.environ.get("QUARANTINE_TABLE", DEFAULT_QUARANTINE_TABLE)
        self.aws_region = os.environ.get("AWS_REGION", DEFAULT_AWS_REGION)

        self.endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
        self.key = os.environ.get("COSMOS_DB_KEY")
        self.db_name = "FraudGuardDB"
        self.container_name = "AuditLog"

        self.use_dynamodb = bool(
            BOTO3_AVAILABLE
            and self.dynamodb_table_name
            and os.environ.get("USE_AWS_DYNAMODB", "").lower() == "true"
        )
        self.use_cosmos = bool(COSMOS_AVAILABLE and self.endpoint and self.key and not self.use_dynamodb)
        self.in_memory_only = in_memory_only

        self.fallback_path = _resolve_writable_path(fallback_path, "audit_log.json")
        self.quarantine_fallback_path = _resolve_writable_path(quarantine_fallback_path, "quarantine_log.json")

        self._mem_main: List[Dict[str, Any]] = []
        self._mem_quarantine: List[Dict[str, Any]] = []

        if self.use_dynamodb:
            region = self.aws_region or DEFAULT_AWS_REGION
            self.dynamodb = boto3.resource("dynamodb", region_name=region)
            self.main_table = self.dynamodb.Table(self.dynamodb_table_name)
            self.quarantine_table = (
                self.dynamodb.Table(self.quarantine_table_name)
                if self.quarantine_table_name
                else None
            )
            self.cloudwatch = boto3.client("cloudwatch", region_name=region)
        elif self.use_cosmos:
            self.client = CosmosClient(self.endpoint, self.key)
            self.database = self.client.create_database_if_not_exists(id=self.db_name)
            self.container = self.database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/transaction_id"),
                offer_throughput=400
            )
        elif not self.in_memory_only:
            self.fallback_path = self._ensure_file(self.fallback_path, "audit_log.json")
            self.quarantine_fallback_path = self._ensure_file(self.quarantine_fallback_path, "quarantine_log.json")

    @staticmethod
    def _ensure_file(path: Optional[str], default_filename: str = "audit_log.json") -> Optional[str]:
        if not path:
            return None
        target = _resolve_writable_path(path, default_filename)
        if not target:
            return None
        try:
            if not os.path.exists(target):
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    json.dump([], f)
            return target
        except OSError:
            tmp_dir = "/tmp" if os.path.isdir("/tmp") else tempfile.gettempdir()
            fallback_tmp = os.path.join(tmp_dir, default_filename)
            try:
                if not os.path.exists(fallback_tmp):
                    with open(fallback_tmp, "w", encoding="utf-8") as f:
                        json.dump([], f)
                return fallback_tmp
            except OSError:
                return None

    def _read_json_list(self, path: Optional[str], mem_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.in_memory_only or not path:
            return list(mem_list)
        resolved = self._ensure_file(path, os.path.basename(path))
        if not resolved:
            return list(mem_list)
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return list(mem_list)

    def _write_json_list(self, path: Optional[str], data: List[Dict[str, Any]], mem_list: List[Dict[str, Any]]) -> None:
        if self.in_memory_only or not path:
            mem_list.clear()
            mem_list.extend(data)
            return
        resolved = self._ensure_file(path, os.path.basename(path))
        if not resolved:
            mem_list.clear()
            mem_list.extend(data)
            return
        try:
            with open(resolved, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            mem_list.clear()
            mem_list.extend(data)

    def log_transaction(self, tx_data: Dict[str, Any], prevent_overwrite: bool = True) -> bool:
        """
        Writes a non-blocked (APPROVED / PENDING_REVIEW) transaction to the main table ONLY.
        Uses conditional expression attribute_not_exists(transaction_id) to prevent duplicate overwrites.
        Sets TTL attributes (`ttl_epoch` and `ttl_expiry`).
        """
        now_utc = datetime.now(timezone.utc)
        record = dict(tx_data)
        tx_id = record.get("transaction_id") or record.get("id") or f"tx_{int(now_utc.timestamp() * 1000)}"
        record["transaction_id"] = str(tx_id)
        if "id" not in record:
            record["id"] = record["transaction_id"]
        if "account_id" not in record:
            record["account_id"] = record.get("source_account") or record.get("user_id") or "unknown"
        if "timestamp" not in record or not record["timestamp"]:
            record["timestamp"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        record["_ts"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Validate finite floats before writing
        _to_dynamodb_safe(record)
        # Set TTL attributes
        record["ttl_epoch"] = int((now_utc + timedelta(days=MAIN_TTL_DAYS)).timestamp())
        if "ttl_expiry" not in record:
            record["ttl_expiry"] = int(time.time()) + TTL_30_DAYS_SECONDS

        if self.use_dynamodb:
            item = _to_dynamodb_safe(record)
            kwargs: Dict[str, Any] = {
                "Item": item,
                "ConditionExpression": "attribute_not_exists(transaction_id)"
            }
            try:
                self.main_table.put_item(**kwargs)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    if not prevent_overwrite:
                        return True
                    raise DuplicateTransactionError(f"Duplicate transaction_id: {tx_id}")
                raise
        elif self.use_cosmos:
            try:
                self.container.upsert_item(record)
                return True
            except CosmosHttpResponseError:
                return False
        else:
            with self._lock:
                logs = self._read_json_list(self.fallback_path, self._mem_main)
                q_logs = self._read_json_list(self.quarantine_fallback_path, self._mem_quarantine)
                if prevent_overwrite and (
                    any(r.get("transaction_id") == record["transaction_id"] for r in logs)
                    or any(q.get("transaction_id") == record["transaction_id"] for q in q_logs)
                ):
                    raise DuplicateTransactionError(f"Duplicate transaction_id: {tx_id}")
                logs.append(record)
                self._write_json_list(self.fallback_path, logs, self._mem_main)
            return True

    def log_quarantine(self, quarantine_record: Dict[str, Any], prevent_overwrite: bool = True) -> bool:
        """
        Writes a BLOCKED transaction to the `fraud-quarantine` table ONLY.
        Sets TTL attributes (`ttl_epoch` and `ttl_expiry`).
        """
        now_utc = datetime.now(timezone.utc)
        record = dict(quarantine_record)
        tx_id = record.get("transaction_id")
        if not tx_id:
            raise ValueError("quarantine_record requires transaction_id")
        if "account_id" not in record:
            record["account_id"] = record.get("source_account") or "unknown"
        if "timestamp" not in record or not record["timestamp"]:
            record["timestamp"] = record.get("quarantine_ts") or now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        _to_dynamodb_safe(record)
        record["ttl_epoch"] = int((now_utc + timedelta(days=QUARANTINE_TTL_DAYS)).timestamp())
        if "ttl_expiry" not in record:
            record["ttl_expiry"] = int(time.time()) + TTL_30_DAYS_SECONDS

        if self.use_dynamodb and self.quarantine_table is not None:
            item = _to_dynamodb_safe(record)
            kwargs: Dict[str, Any] = {
                "Item": item,
                "ConditionExpression": "attribute_not_exists(transaction_id)"
            }
            try:
                self.quarantine_table.put_item(**kwargs)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    if not prevent_overwrite:
                        return True
                    raise DuplicateTransactionError(f"Duplicate quarantine transaction_id: {tx_id}")
                raise
        else:
            with self._lock:
                logs = self._read_json_list(self.fallback_path, self._mem_main)
                q_logs = self._read_json_list(self.quarantine_fallback_path, self._mem_quarantine)
                if prevent_overwrite and (
                    any(q.get("transaction_id") == tx_id for q in q_logs)
                    or any(r.get("transaction_id") == tx_id for r in logs)
                ):
                    raise DuplicateTransactionError(f"Duplicate quarantine transaction_id: {tx_id}")
                q_logs.append(record)
                self._write_json_list(self.quarantine_fallback_path, q_logs, self._mem_quarantine)
            return True

    def get_account_transactions(self, account_id: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
        """
        Queries both main transactions and quarantined transactions for `account_id`,
        deduplicating by `transaction_id` and sorting by `timestamp` descending so repeated
        BLOCKed attacks are included in velocity and traceback chains.
        """
        if not account_id:
            return []
        acct_str = str(account_id)
        if self.use_dynamodb:
            from boto3.dynamodb.conditions import Key, Attr
            items: List[Dict[str, Any]] = []
            try:
                resp = self.main_table.query(
                    IndexName="AccountTimestampIndex",
                    KeyConditionExpression=Key("account_id").eq(acct_str),
                    ScanIndexForward=False,
                    Limit=limit
                )
                items.extend(_from_dynamodb_safe(x) for x in resp.get("Items", []))
            except Exception:
                scan_resp = self.main_table.scan(
                    FilterExpression=Attr("account_id").eq(acct_str) | Attr("source_account").eq(acct_str)
                )
                items.extend(_from_dynamodb_safe(x) for x in scan_resp.get("Items", []))

            if self.quarantine_table is not None:
                try:
                    q_resp = self.quarantine_table.query(
                        IndexName="AccountTimestampIndex",
                        KeyConditionExpression=Key("account_id").eq(acct_str),
                        ScanIndexForward=False,
                        Limit=limit
                    )
                    items.extend(_from_dynamodb_safe(x) for x in q_resp.get("Items", []))
                except Exception:
                    try:
                        q_scan = self.quarantine_table.scan(
                            FilterExpression=Attr("account_id").eq(acct_str) | Attr("source_account").eq(acct_str)
                        )
                        items.extend(_from_dynamodb_safe(x) for x in q_scan.get("Items", []))
                    except Exception:
                        pass

            deduped: Dict[str, Dict[str, Any]] = {}
            for it in items:
                tid = it.get("transaction_id")
                if tid and tid not in deduped:
                    deduped[tid] = it
            combined = list(deduped.values())
            combined.sort(
                key=lambda r: r.get("timestamp") or r.get("quarantine_ts") or "",
                reverse=True
            )
            return combined[:limit]
        else:
            with self._lock:
                logs = self._read_json_list(self.fallback_path, self._mem_main)
                q_logs = self._read_json_list(self.quarantine_fallback_path, self._mem_quarantine)

            combined_logs = list(logs) + list(q_logs)
            seen_ids = set()
            matched: List[Dict[str, Any]] = []
            for r in combined_logs:
                r_acct = (
                    r.get("account_id")
                    or r.get("source_account")
                    or (r.get("original_payload") or {}).get("source_account")
                    or (r.get("original_payload") or {}).get("account_id")
                )
                if r_acct == account_id:
                    tid = r.get("transaction_id")
                    if tid and tid in seen_ids:
                        continue
                    if tid:
                        seen_ids.add(tid)
                    matched.append(r)

            matched.sort(
                key=lambda r: (
                    r.get("timestamp")
                    or (r.get("original_payload") or {}).get("timestamp")
                    or r.get("quarantine_ts")
                    or ""
                ),
                reverse=True
            )
            return matched[:limit]

    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a transaction by ID across main table and quarantine table."""
        if self.use_dynamodb:
            resp = self.main_table.get_item(Key={"transaction_id": str(transaction_id)})
            if "Item" in resp:
                return _from_dynamodb_safe(resp["Item"])
            if self.quarantine_table is not None:
                q_resp = self.quarantine_table.get_item(Key={"transaction_id": str(transaction_id)})
                if "Item" in q_resp:
                    return _from_dynamodb_safe(q_resp["Item"])
            return None
        else:
            with self._lock:
                main_logs = self._read_json_list(self.fallback_path, self._mem_main)
                for r in main_logs:
                    if r.get("transaction_id") == transaction_id:
                        return r
                q_logs = self._read_json_list(self.quarantine_fallback_path, self._mem_quarantine)
                for q in q_logs:
                    if q.get("transaction_id") == transaction_id:
                        return q
            return None

    def get_all_main_transactions(self) -> List[Dict[str, Any]]:
        if self.use_dynamodb:
            try:
                resp = self.main_table.scan()
                items = [_from_dynamodb_safe(x) for x in resp.get("Items", [])]
                while "LastEvaluatedKey" in resp:
                    resp = self.main_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
                    items.extend(_from_dynamodb_safe(x) for x in resp.get("Items", []))
                return items
            except Exception:
                return []
        with self._lock:
            return self._read_json_list(self.fallback_path, self._mem_main)

    def get_all_quarantined_transactions(self) -> List[Dict[str, Any]]:
        if self.use_dynamodb and self.quarantine_table is not None:
            try:
                resp = self.quarantine_table.scan()
                items = [_from_dynamodb_safe(x) for x in resp.get("Items", [])]
                while "LastEvaluatedKey" in resp:
                    resp = self.quarantine_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
                    items.extend(_from_dynamodb_safe(x) for x in resp.get("Items", []))
                return items
            except Exception:
                return []
        with self._lock:
            return self._read_json_list(self.quarantine_fallback_path, self._mem_quarantine)

    def update_quarantine_status(
        self,
        transaction_id: str,
        new_status: str,
        analyst_notes: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update status of a quarantined transaction (e.g. QUARANTINED -> RELEASED)."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if self.use_dynamodb and self.quarantine_table is not None:
            try:
                resp = self.quarantine_table.update_item(
                    Key={"transaction_id": str(transaction_id)},
                    UpdateExpression="SET #st = :s, analyst_notes = :n, released_ts = :t",
                    ConditionExpression="attribute_exists(transaction_id)",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":s": new_status,
                        ":n": analyst_notes,
                        ":t": now_iso
                    },
                    ReturnValues="ALL_NEW"
                )
                return _from_dynamodb_safe(resp.get("Attributes"))
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return None
                raise
        else:
            with self._lock:
                q_logs = self._read_json_list(self.quarantine_fallback_path, self._mem_quarantine)
                updated_item = None
                for item in q_logs:
                    if item.get("transaction_id") == transaction_id:
                        item["status"] = new_status
                        if analyst_notes is not None:
                            item["analyst_notes"] = analyst_notes
                        item["updated_ts"] = now_iso
                        updated_item = dict(item)
                        break
                if updated_item:
                    self._write_json_list(self.quarantine_fallback_path, q_logs, self._mem_quarantine)
                return updated_item
