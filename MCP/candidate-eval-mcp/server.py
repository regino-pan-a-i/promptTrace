import os
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import urllib.request
import urllib.error

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("candidate-eval-mcp")

# --- Simple file logger (JSONL). Avoid stdout logs in stdio MCP servers. ---
LOG_DIR = Path.home() / ".candidate-eval-mcp" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "tool_calls.jsonl"


def log_event(event: Dict[str, Any]) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def call_aws_backend(endpoint: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    """
    Calls your AWS backend (e.g., API Gateway/Lambda). Returns parsed JSON.
    Uses only stdlib so candidates don't need extra dependencies.
    """
    base_url = os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("Missing EVAL_API_BASE_URL env var (backend not configured).")

    url = f"{base_url}{endpoint}"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={
            "Content-Type": "application/json",
            # forward identity so backend can map candidateId/taskId
            "x-candidate-token": os.environ.get("CANDIDATE_TOKEN", ""),
            "x-task-id": os.environ.get("TASK_ID", ""),
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


@mcp.tool()
def ping(message: str = "") -> str:
    """Health check tool to verify MCP server connectivity."""
    return "pong" + (f": {message}" if message else "")


@mcp.tool()
def evaluation_plan(project_summary: str, user_prompt: str) -> str:
    """
    Returns a structured plan for Copilot to follow.
    Calls AWS backend so you can log + score candidate behavior.
    Required inputs match your spec: project_summary, user_prompt.
    """
    request_id = str(uuid.uuid4())
    start = time.time()

    candidate_token = os.environ.get("CANDIDATE_TOKEN", "")
    task_id = os.environ.get("TASK_ID", "")

    log_event({
        "ts": now_iso(),
        "request_id": request_id,
        "tool": "evaluation_plan",
        "candidate_token_present": bool(candidate_token),
        "task_id": task_id,
        "inputs": {
            "project_summary_len": len(project_summary or ""),
            "user_prompt_len": len(user_prompt or ""),
        }
    })

    try:
        base_url = os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")
        if base_url in ("", "https://example.com", "http://example.com"):
            result = {
                "mode": "stub",
                "message": "Backend not configured yet. Returning a stub evaluation plan.",
                "plan": [
                    "Read the README and identify the task requirements.",
                    "Ask Copilot to summarize project structure and key files.",
                    "Propose edits for the most relevant files (do not apply automatically).",
                    "List tests/commands the candidate should run to validate changes.",
                    "When AWS is ready, run evaluation_check to score results."
                ]
            }
        else:
            result = call_aws_backend(
                endpoint="/interact",
                payload={
                    "candidateToken": os.environ.get("CANDIDATE_TOKEN", ""),
                    "taskId": os.environ.get("TASK_ID", ""),
                    "userMessage": user_prompt,
                    "context": {
                        "files": [],
                        "selection": "",
                        "projectSummary": project_summary
                    }
                }
            )

        latency_ms = int((time.time() - start) * 1000)
        log_event({
            "ts": now_iso(),
            "request_id": request_id,
            "tool": "evaluation_plan",
            "status": "ok",
            "latency_ms": latency_ms,
            "backend_keys": list(result.keys()),
        })

        return json.dumps(result, indent=2)

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start) * 1000)
        err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""

        log_event({
            "ts": now_iso(),
            "request_id": request_id,
            "tool": "evaluation_plan",
            "status": "error",
            "latency_ms": latency_ms,
            "error_type": "HTTPError",
            "error_code": getattr(e, "code", None),
            "error_body": err_body[:2000],
        })

        return f"Backend HTTP error ({getattr(e, 'code', 'unknown')}): {err_body}"

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)

        log_event({
            "ts": now_iso(),
            "request_id": request_id,
            "tool": "evaluation_plan",
            "status": "error",
            "latency_ms": latency_ms,
            "error_type": type(e).__name__,
            "error_message": str(e),
        })

        return f"Error: {type(e).__name__}: {e}"


@mcp.tool()
def evaluation_propose_edits(
    file_path: str,
    file_content: str,
    project_summary: str,
    user_prompt: str
) -> str:
    """
    Proposes edits for a single file. Does not apply changes.
    Copilot will apply edits in the workspace after approval.
    Required inputs match your spec: file_path, file_content, project_summary, user_prompt.
    """
    request_id = str(uuid.uuid4())
    start = time.time()

    candidate_token = os.environ.get("CANDIDATE_TOKEN", "")
    task_id = os.environ.get("TASK_ID", "")

    log_event({
        "ts": now_iso(),
        "request_id": request_id,
        "tool": "evaluation_propose_edits",
        "candidate_token_present": bool(candidate_token),
        "task_id": task_id,
        "inputs": {
            "file_path": file_path,
            "file_content_len": len(file_content or ""),
            "project_summary_len": len(project_summary or ""),
            "user_prompt_len": len(user_prompt or ""),
        }
    })

    try:
        base_url = os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")
        if base_url in ("", "https://example.com", "http://example.com"):
            result = {
                "mode": "stub",
                "message": "Backend not configured yet. Returning a sample proposed edit structure.",
                "edits": [
                    {
                        "path": file_path,
                        "diff_or_new_content": file_content,
                        "rationale": "Stub: no changes suggested yet. Replace diff_or_new_content with a real diff or updated content."
                    }
                ],
                "tests_to_run": [],
                "risks": ["Stub mode: no real analysis performed."]
            }
        else:
            result = call_aws_backend(
                endpoint="/interact",
                payload={
                    "candidateToken": os.environ.get("CANDIDATE_TOKEN", ""),
                    "taskId": os.environ.get("TASK_ID", ""),
                    "userMessage": user_prompt,
                    "context": {
                        "files": [
                        {"path": file_path, "content": file_content}
                        ],
                        "selection": "",
                        "projectSummary": project_summary
                    }
            }
            )

        latency_ms = int((time.time() - start) * 1000)
        log_event({
            "ts": now_iso(),
            "request_id": request_id,
            "tool": "evaluation_propose_edits",
            "status": "ok",
            "latency_ms": latency_ms,
            "backend_keys": list(result.keys()),
        })

        return json.dumps(result, indent=2)

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        log_event({
            "ts": now_iso(),
            "request_id": request_id,
            "tool": "evaluation_propose_edits",
            "status": "error",
            "latency_ms": latency_ms,
            "error_type": type(e).__name__,
            "error_message": str(e),
        })
        return f"Error: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run()