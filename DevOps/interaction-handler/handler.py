import json
import uuid
import os
import boto3
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")

LOG_BUCKET = os.environ.get("LOG_BUCKET", "ai-eval-logs-dev")
MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-3-5-haiku-20241022")


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        candidate_token = body.get("candidateToken")
        task_id = body.get("taskId")
        user_message = body.get("userMessage")
        ctx = body.get("context", {})

        if not all([candidate_token, task_id, user_message]):
            return _response(400, {"error": "candidateToken, taskId, and userMessage are required"})

        request_id = str(uuid.uuid4())
        candidate_id = candidate_token  # TODO: resolve via DynamoDB if needed

        # Compute context quality metrics
        context_quality = _compute_context_quality(user_message, ctx)

        prompt = _build_prompt(user_message, ctx)
        logger.info(f"Invoking Bedrock model {MODEL_ID} for request {request_id}")
        bedrock_response = _invoke_bedrock(prompt)

        assistant_message = bedrock_response.get("assistantMessage", "")
        plan = bedrock_response.get("plan", "")
        proposed_edits = bedrock_response.get("proposedEdits", [])
        alternatives = bedrock_response.get("alternatives", [])
        test_strategy = bedrock_response.get("testStrategy", "")
        tags = bedrock_response.get("tags", {})

        _log_interaction(candidate_id, request_id, task_id, body, bedrock_response, context_quality)

        return _response(200, {
            "requestId": request_id,
            "assistantMessage": assistant_message,
            "plan": plan,
            "proposedEdits": proposed_edits,
            "alternatives": alternatives,
            "testStrategy": test_strategy,
            "tags": tags,
        })
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return _response(500, {"error": str(e)})


def _build_prompt(user_message: str, ctx: dict) -> str:
    files_section = ""
    for f in ctx.get("files", []):
        files_section += f"\n### {f['path']}\n```\n{f['content']}\n```"

    selection = ctx.get("selection", "")
    project_summary = ctx.get("projectSummary", "")

    return f"""You are an expert coding assistant evaluating a candidate's task. Assess the quality of their work and provide strategic, high-confidence suggestions.

Project Summary: {project_summary}

Current Selection:
{selection}

Relevant Files:{files_section}

Candidate Message: {user_message}

Respond with a JSON object with keys:
- assistantMessage: string (explanation for the candidate)
- plan: string (step-by-step plan)
- proposedEdits: array of {{path, original, replacement, rationale, confidence (0-100)}}
- alternatives: array of {{description, tradeoffs}} (2-3 alternative approaches)
- testStrategy: string (suggested testing approach to validate the changes)
- tags: {{taskCategory, complexity, confidence (0-100)}}

Be thorough and consider multiple approaches. Flag if a solution is over-engineered.
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


def _log_interaction(candidate_id: str, request_id: str, task_id: str, request_body: dict, model_response: dict, context_quality: dict):
    now = datetime.utcnow()
    key = f"interactions/{now.year}/{now.month:02}/{now.day:02}/{candidate_id}/{request_id}.json"
    payload = {
        "requestId": request_id,
        "candidateId": candidate_id,
        "taskId": task_id,
        "timestamp": now.isoformat(),
        "request": request_body,
        "modelResponse": model_response,
        "contextQuality": context_quality,
    }
    s3.put_object(Bucket=LOG_BUCKET, Key=key, Body=json.dumps(payload), ContentType="application/json")


def _compute_context_quality(user_message: str, ctx: dict) -> dict:
    """Assess the quality and depth of context provided by the candidate."""
    files = ctx.get("files", [])
    selection = ctx.get("selection", "")
    project_summary = ctx.get("projectSummary", "")
    
    # Calculate metrics
    file_count = len(files)
    total_file_size = sum(len(f.get("content", "")) for f in files)
    selection_length = len(selection)
    message_length = len(user_message)
    
    # Detect questions (heuristic: question marks, "why", "how", "what")
    question_indicators = ["?", "why", "how", "what", "explain", "understand"]
    questions_asked = sum(1 for indicator in question_indicators if indicator.lower() in user_message.lower())
    
    # Compute clarity score (0-100): longer, specific messages with questions score higher
    clarity_score = min(100, (message_length / 500) * 40 + (questions_asked * 15) + (20 if project_summary else 0))
    
    return {
        "fileCount": file_count,
        "totalFileSizeBytes": total_file_size,
        "selectionLength": selection_length,
        "messageLength": message_length,
        "questionsAsked": questions_asked,
        "clarityScore": int(clarity_score),
        "hasProjectSummary": bool(project_summary),
    }


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
