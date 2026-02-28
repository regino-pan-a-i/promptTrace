import json
import uuid
import boto3
from datetime import datetime

bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")

LOG_BUCKET = "ai-eval-logs-dev"
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))

    candidate_token = body.get("candidateToken")
    task_id = body.get("taskId")
    user_message = body.get("userMessage")
    ctx = body.get("context", {})

    if not all([candidate_token, task_id, user_message]):
        return _response(400, {"error": "candidateToken, taskId, and userMessage are required"})

    request_id = str(uuid.uuid4())
    candidate_id = candidate_token  # TODO: resolve via DynamoDB if needed

    prompt = _build_prompt(user_message, ctx)
    bedrock_response = _invoke_bedrock(prompt)

    assistant_message = bedrock_response.get("assistantMessage", "")
    plan = bedrock_response.get("plan", "")
    proposed_edits = bedrock_response.get("proposedEdits", [])
    tags = bedrock_response.get("tags", {})

    _log_interaction(candidate_id, request_id, task_id, body, bedrock_response)

    return _response(200, {
        "requestId": request_id,
        "assistantMessage": assistant_message,
        "plan": plan,
        "proposedEdits": proposed_edits,
        "tags": tags,
    })


def _build_prompt(user_message: str, ctx: dict) -> str:
    files_section = ""
    for f in ctx.get("files", []):
        files_section += f"\n### {f['path']}\n```\n{f['content']}\n```"

    selection = ctx.get("selection", "")
    project_summary = ctx.get("projectSummary", "")

    return f"""You are an expert coding assistant evaluating a candidate's task.

Project Summary: {project_summary}

Current Selection:
{selection}

Relevant Files:{files_section}

Candidate Message: {user_message}

Respond with a JSON object with keys:
- assistantMessage: string (explanation for the candidate)
- plan: string (step-by-step plan)
- proposedEdits: array of {{path, original, replacement, rationale}}
- tags: {{taskCategory, complexity, confidence}}
"""


def _invoke_bedrock(prompt: str) -> dict:
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(payload),
        contentType="application/json",
    )
    raw = json.loads(response["body"].read())
    text = raw["content"][0]["text"]

    # Extract JSON block if wrapped in markdown
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    return json.loads(text)


def _log_interaction(candidate_id: str, request_id: str, task_id: str, request_body: dict, model_response: dict):
    now = datetime.utcnow()
    key = f"interactions/{now.year}/{now.month:02}/{now.day:02}/{candidate_id}/{request_id}.json"
    payload = {
        "requestId": request_id,
        "candidateId": candidate_id,
        "taskId": task_id,
        "timestamp": now.isoformat(),
        "request": request_body,
        "modelResponse": model_response,
    }
    s3.put_object(Bucket=LOG_BUCKET, Key=key, Body=json.dumps(payload), ContentType="application/json")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
