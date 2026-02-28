import json
import boto3
from datetime import datetime

s3 = boto3.client("s3")

LOG_BUCKET = "ai-eval-logs-dev"


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))

    candidate_token = body.get("candidateToken")
    task_id = body.get("taskId")
    request_id = body.get("requestId")
    decisions = body.get("decisions", [])
    metrics = body.get("metrics", {})

    if not all([candidate_token, task_id, request_id]):
        return _response(400, {"error": "candidateToken, taskId, and requestId are required"})

    candidate_id = candidate_token  # TODO: resolve via DynamoDB if needed

    _log_outcome(candidate_id, request_id, task_id, decisions, metrics)

    return _response(200, {"acknowledged": True, "requestId": request_id})


def _log_outcome(candidate_id: str, request_id: str, task_id: str, decisions: list, metrics: dict):
    now = datetime.utcnow()
    key = f"outcomes/{now.year}/{now.month:02}/{now.day:02}/{candidate_id}/{request_id}.json"
    payload = {
        "requestId": request_id,
        "candidateId": candidate_id,
        "taskId": task_id,
        "timestamp": now.isoformat(),
        "decisions": decisions,
        "metrics": metrics,
    }
    s3.put_object(Bucket=LOG_BUCKET, Key=key, Body=json.dumps(payload), ContentType="application/json")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
