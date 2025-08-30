# lambda_function.py
"""
SQS → Lambda → DynamoDB (+ SNS alerts)

Improvements:
- Env-var fallbacks: TABLE_NAME/ORDERS_TABLE_NAME, LARGE_ORDER_THRESHOLD/LARGE_ORDER_AMOUNT,
  single-topic (TOPIC_ARN) or two-topic (TOPIC_LARGE_ARN & TOPIC_INVALID_ARN)
- Auto-generate transaction_id when missing
- Swallow ConditionalCheckFailed (idempotent duplicates)
- Clear startup validation/logs + richer per-record logs
"""

import json
import os
import logging
import traceback
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# ---------- Config & Logger ----------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# Env var fallbacks to match any Terraform flavors you used
TABLE_NAME = (
    os.environ.get("TABLE_NAME")
    or os.environ.get("ORDERS_TABLE_NAME")
    or "orders"
)

# Allow either LARGE_ORDER_THRESHOLD or LARGE_ORDER_AMOUNT
_threshold_raw = os.environ.get("LARGE_ORDER_THRESHOLD") or os.environ.get("LARGE_ORDER_AMOUNT") or "1000"

# Support one topic (TOPIC_ARN) or two topics (TOPIC_LARGE_ARN / TOPIC_INVALID_ARN)
TOPIC_FALLBACK = os.environ.get("TOPIC_ARN")
TOPIC_LARGE = os.environ.get("TOPIC_LARGE_ARN") or TOPIC_FALLBACK
TOPIC_INVALID = os.environ.get("TOPIC_INVALID_ARN") or TOPIC_FALLBACK

try:
    THRESHOLD_DEC = Decimal(str(_threshold_raw))
except (InvalidOperation, TypeError, ValueError):
    THRESHOLD_DEC = Decimal("1000")

# ---------- AWS clients ----------
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
sns = boto3.client("sns")

# Cold-start validation: make it obvious in logs if table is wrong/missing
try:
    dynamodb.meta.client.describe_table(TableName=TABLE_NAME)
    logger.info("✅ DynamoDB table found: %s", TABLE_NAME)
except ClientError as e:
    logger.error("❌ DynamoDB table not found or access denied: %s", e)

# ---------- Helpers ----------
def _json_loads_safe(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s

def parse_record_body(body: str) -> Dict[str, Any]:
    """
    Accept:
      - JSON string
      - Double-encoded JSON
      - SNS->SQS envelope: {"Message":"<json>"}
    """
    payload = _json_loads_safe(body)

    if isinstance(payload, str):
        inner = _json_loads_safe(payload)
        if isinstance(inner, (dict, list)):
            payload = inner

    if isinstance(payload, dict) and isinstance(payload.get("Message"), str):
        inner = _json_loads_safe(payload["Message"])
        if isinstance(inner, (dict, list)):
            payload = inner

    if not isinstance(payload, dict):
        return {"raw": payload}
    return payload

def normalize(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize keys & validate. If transaction_id missing, generate one.
    """
    txid = schema.get("transaction_id") or schema.get("orderId") or schema.get("order_id")
    cid  = schema.get("customer_id") or schema.get("customerId")
    amt  = schema.get("amount")
    items = schema.get("items") if isinstance(schema.get("items"), list) else []

    # Generate a transaction_id if missing to avoid write failures
    if not txid:
        txid = str(uuid.uuid4())
        logger.info("No transaction_id in payload. Generated: %s", txid)

    if not cid:
        raise ValueError("Missing required field: customer_id/customerId")
    if amt is None:
        raise ValueError("Missing required field: amount")

    try:
        amt_dec = Decimal(str(amt))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("amount must be numeric")

    return {
        "transaction_id": str(txid),
        "customer_id": str(cid),
        "amount": amt_dec,
        "items": items,
    }

def classify(amount: Decimal) -> str:
    if amount <= 0:
        return "invalid"
    if amount > THRESHOLD_DEC:
        return "large"
    return "normal"

def to_ddb(obj: Any) -> Any:
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, (int, float, Decimal)):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [to_ddb(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_ddb(v) for k, v in obj.items()}
    return obj

def put_item_idempotent(item: Dict[str, Any]) -> None:
    """
    Idempotent write on transaction_id. Treat duplicate writes as success.
    """
    txid = item.get("transaction_id")
    now_iso = datetime.now(timezone.utc).isoformat()
    ddb_item = {**item, "created_at": now_iso}

    try:
        table.put_item(
            Item=to_ddb(ddb_item),
            ConditionExpression="attribute_not_exists(transaction_id)"
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("ConditionalCheckFailedException", "ConditionalCheckFailed"):
            # Duplicate delivery: consider success
            logger.info("Duplicate transaction_id=%s; treating as success", txid)
            return
        raise

def publish(topic_arn: Optional[str], subject: str, message_obj: Any) -> None:
    if not topic_arn:
        logger.warning("SNS topic not configured; subject=%s", subject)
        return
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=json.dumps(message_obj, default=str),
        )
        logger.info("Published SNS subject=%s topic=%s", subject, topic_arn.split(":")[-1])
    except Exception:
        logger.error("SNS publish failed: %s", traceback.format_exc())

# ---------- Handler ----------
def lambda_handler(event, context):
    failures: List[Dict[str, str]] = []

    metrics = {"Processed": 0, "Large": 0, "Invalid": 0, "Skipped": 0}

    recs = event.get("Records", [])
    logger.info("Received %d SQS records", len(recs))

    for record in recs:
        msg_id = record.get("messageId")
        raw_body = record.get("body", "")

        try:
            payload = parse_record_body(raw_body)

            if "raw" in payload:
                logger.warning("Skipping non-JSON payload id=%s preview=%s", msg_id, str(payload["raw"])[:200])
                metrics["Skipped"] += 1
                continue

            normalized = normalize(payload)
            category = classify(normalized["amount"])

            # Write first, then alert
            put_item_idempotent(normalized)
            metrics["Processed"] += 1
            logger.info("PutItem OK tx=%s cid=%s amt=%s",
                        normalized["transaction_id"], normalized["customer_id"], str(normalized["amount"]))

            # Alerts
            if category == "large":
                metrics["Large"] += 1
                publish(
                    TOPIC_LARGE,
                    "Large Order Detected",
                    {
                        "transaction_id": normalized["transaction_id"],
                        "customer_id": normalized["customer_id"],
                        "amount": str(normalized["amount"]),
                        "threshold": str(THRESHOLD_DEC),
                        "ts": datetime.now(timezone.utc).isoformat(),
                    },
                )
            elif category == "invalid":
                metrics["Invalid"] += 1
                publish(
                    TOPIC_INVALID,
                    "Invalid Transaction",
                    {"reason": "non-positive-amount", "payload_preview": str(payload)[:500]},
                )

        except ValueError as ve:
            logger.warning("Validation error for id=%s: %s", msg_id, ve)
            metrics["Invalid"] += 1
            publish(TOPIC_INVALID, "Invalid Transaction", {"error": str(ve), "payload_preview": raw_body[:500]})
            # don't fail batch for business-invalid data
        except ClientError as ce:
            logger.error("AWS client error for id=%s: %s", msg_id, ce)
            if msg_id:
                failures.append({"itemIdentifier": msg_id})
        except Exception as e:
            logger.error("Unhandled error for id=%s: %s", msg_id, e)
            logger.debug("Trace:\n%s", traceback.format_exc())
            if msg_id:
                failures.append({"itemIdentifier": msg_id})

    # Emit EMF metrics (optional)
    emf = {
        "_aws": {
            "CloudWatchMetrics": [
                {
                    "Namespace": "EcomRealtimePipeline",
                    "Dimensions": [["FunctionName"]],
                    "Metrics": [
                        {"Name": "Processed", "Unit": "Count"},
                        {"Name": "Large", "Unit": "Count"},
                        {"Name": "Invalid", "Unit": "Count"},
                        {"Name": "Skipped", "Unit": "Count"},
                    ],
                }
            ],
        },
        "FunctionName": getattr(context, "function_name", "unknown"),
        **metrics,
    }
    logger.info(json.dumps(emf))

    return {"batchItemFailures": failures}
