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

# ---------------------------------------------------------------------------
# File logger (JSONL) — never write to stdout in stdio MCP servers.
# Rotates by date so logs don't grow forever.
# ---------------------------------------------------------------------------
LOG_DIR = Path.home() / ".candidate-eval-mcp" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_file() -> Path:
    """Return a date-stamped log file path (auto-rotates daily)."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return LOG_DIR / f"tool_calls_{date_str}.jsonl"


def log_event(event: Dict[str, Any]) -> None:
    try:
        with _log_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass  # Never crash the server over a logging failure


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Config helpers — read once per call so hot-reloads work in dev.
# ---------------------------------------------------------------------------
MAX_CONTENT_BYTES = 512_000  # 512 KB hard cap on file_content


def _base_url() -> str:
    return os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")


def _is_stub() -> bool:
    url = _base_url()
    return url in ("", "https://example.com", "http://example.com")


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-candidate-token": os.environ.get("CANDIDATE_TOKEN", ""),
        "x-task-id": os.environ.get("TASK_ID", ""),
    }


# ---------------------------------------------------------------------------
# AWS backend call
# ---------------------------------------------------------------------------
def call_aws_backend(endpoint: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    """POST to the configured AWS backend. Returns parsed JSON response."""
    url = f"{_base_url()}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=_headers(), method="POST")

    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _make_request_id() -> str:
    return str(uuid.uuid4())


def _build_response(result: Dict[str, Any], request_id: str) -> str:
    """Inject request_id into every response so callers can correlate with logs."""
    result["request_id"] = request_id
    return json.dumps(result, indent=2)


def _log_call_start(request_id: str, tool: str, extras: Dict[str, Any]) -> None:
    log_event({
        "ts": now_iso(),
        "request_id": request_id,
        "tool": tool,
        "candidate_token_present": bool(os.environ.get("CANDIDATE_TOKEN")),
        "task_id": os.environ.get("TASK_ID", ""),
        **extras,
    })


def _log_call_end(request_id: str, tool: str, status: str, latency_ms: int, **kwargs) -> None:
    log_event({
        "ts": now_iso(),
        "request_id": request_id,
        "tool": tool,
        "status": status,
        "latency_ms": latency_ms,
        **kwargs,
    })


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def ping(message: str = "") -> str:
    """Health-check tool to verify MCP server connectivity."""
    return "pong" + (f": {message}" if message else "")


@mcp.tool()
def evaluation_plan(project_summary: str, user_prompt: str) -> str:
    """
    Returns a structured evaluation plan.

    Args:
        project_summary: High-level description of the project / repo.
        user_prompt: The task or question the candidate is working on.

    Returns:
        JSON string with the plan (and request_id for log correlation).
    """
    # --- Input validation ---
    if not project_summary or not project_summary.strip():
        return json.dumps({"error": "project_summary must not be empty."})
    if not user_prompt or not user_prompt.strip():
        return json.dumps({"error": "user_prompt must not be empty."})

    request_id = _make_request_id()
    start = time.time()

    _log_call_start(request_id, "evaluation_plan", {
        "project_summary_len": len(project_summary),
        "user_prompt_len": len(user_prompt),
        "stub": _is_stub(),
    })

    try:
        if _is_stub():
            result = {
                "mode": "stub",
                "message": "Backend not configured. Returning a stub evaluation plan.",
                "plan": [
                    "Read the README and identify the task requirements.",
                    "Summarize the project structure and key files.",
                    "Propose edits for the most relevant files (do not apply automatically).",
                    "List tests/commands the candidate should run to validate changes.",
                    "Configure EVAL_API_BASE_URL and run evaluation_check to score results.",
                ],
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
                        "projectSummary": project_summary,
                    },
                },
            )

        latency_ms = int((time.time() - start) * 1000)
        _log_call_end(request_id, "evaluation_plan", "ok", latency_ms,
                      backend_keys=list(result.keys()))
        return _build_response(result, request_id)

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start) * 1000)
        err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        _log_call_end(request_id, "evaluation_plan", "error", latency_ms,
                      error_type="HTTPError", error_code=getattr(e, "code", None),
                      error_body=err_body[:2000])
        return json.dumps({"error": f"HTTP {getattr(e, 'code', 'unknown')}", "detail": err_body, "request_id": request_id})

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        _log_call_end(request_id, "evaluation_plan", "error", latency_ms,
                      error_type=type(e).__name__, error_message=str(e))
        return json.dumps({"error": f"{type(e).__name__}: {e}", "request_id": request_id})


@mcp.tool()
def evaluation_propose_edits(
    file_path: str,
    file_content: str,
    project_summary: str,
    user_prompt: str,
) -> str:
    """
    Proposes edits for a single file. Does NOT apply changes automatically.

    Args:
        file_path: Relative path to the file inside the project (e.g. src/main.py).
        file_content: Current full content of the file.
        project_summary: High-level description of the project / repo.
        user_prompt: The task or question driving the edit.

    Returns:
        JSON string with proposed edits (and request_id for log correlation).
    """
    # --- Input validation ---
    if not file_path or not file_path.strip():
        return json.dumps({"error": "file_path must not be empty."})
    if not user_prompt or not user_prompt.strip():
        return json.dumps({"error": "user_prompt must not be empty."})
    if not project_summary or not project_summary.strip():
        return json.dumps({"error": "project_summary must not be empty."})
    if len(file_content.encode("utf-8")) > MAX_CONTENT_BYTES:
        return json.dumps({"error": f"file_content exceeds {MAX_CONTENT_BYTES // 1024} KB limit. Split the file or send a subset."})

    request_id = _make_request_id()
    start = time.time()

    _log_call_start(request_id, "evaluation_propose_edits", {
        "file_path": file_path,
        "file_content_len": len(file_content),
        "project_summary_len": len(project_summary),
        "user_prompt_len": len(user_prompt),
        "stub": _is_stub(),
    })

    try:
        if _is_stub():
            result = {
                "mode": "stub",
                "message": "Backend not configured. Returning a sample edit structure.",
                "edits": [
                    {
                        "path": file_path,
                        "diff_or_new_content": file_content,
                        "rationale": "Stub mode — no changes suggested. Replace with real diff or updated content.",
                    }
                ],
                "tests_to_run": [],
                "risks": ["Stub mode: no real analysis performed."],
            }
        else:
            result = call_aws_backend(
                endpoint="/interact",
                payload={
                    "candidateToken": os.environ.get("CANDIDATE_TOKEN", ""),
                    "taskId": os.environ.get("TASK_ID", ""),
                    "userMessage": user_prompt,
                    "context": {
                        "files": [{"path": file_path, "content": file_content}],
                        "selection": "",
                        "projectSummary": project_summary,
                    },
                },
            )

        latency_ms = int((time.time() - start) * 1000)
        _log_call_end(request_id, "evaluation_propose_edits", "ok", latency_ms,
                      backend_keys=list(result.keys()))
        return _build_response(result, request_id)

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start) * 1000)
        err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        _log_call_end(request_id, "evaluation_propose_edits", "error", latency_ms,
                      error_type="HTTPError", error_code=getattr(e, "code", None),
                      error_body=err_body[:2000])
        return json.dumps({"error": f"HTTP {getattr(e, 'code', 'unknown')}", "detail": err_body, "request_id": request_id})

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        _log_call_end(request_id, "evaluation_propose_edits", "error", latency_ms,
                      error_type=type(e).__name__, error_message=str(e))
        return json.dumps({"error": f"{type(e).__name__}: {e}", "request_id": request_id})


@mcp.tool()
def finalize_project(evaluation_summary: str = "") -> str:
    """
    Finalizes the project evaluation and generates a comprehensive evaluation report.

    Args:
        evaluation_summary: Optional summary of the evaluation progress and findings.

    Returns:
        JSON string with the finalization result and evaluation report (and request_id for log correlation).
    """
    request_id = _make_request_id()
    start = time.time()

    _log_call_start(request_id, "finalize_project", {
        "evaluation_summary_len": len(evaluation_summary),
        "stub": _is_stub(),
    })

    try:
        if _is_stub():
            result = {
                "mode": "stub",
                "message": "Backend not configured. Returning a stub finalization result.",
                "status": "completed",
                "report": {
                    "overall_assessment": "Stub mode — no real evaluation performed.",
                    "summary": evaluation_summary or "No summary provided.",
                    "recommendation": "Configure EVAL_API_BASE_URL to enable real evaluation.",
                },
            }
        else:
            result = call_aws_backend(
                endpoint="/finalize-project",
                payload={
                    "candidateToken": os.environ.get("CANDIDATE_TOKEN", ""),
                    "taskId": os.environ.get("TASK_ID", ""),
                    "evaluationSummary": evaluation_summary,
                },
            )

        latency_ms = int((time.time() - start) * 1000)
        _log_call_end(request_id, "finalize_project", "ok", latency_ms,
                      backend_keys=list(result.keys()))
        return _build_response(result, request_id)

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start) * 1000)
        err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        _log_call_end(request_id, "finalize_project", "error", latency_ms,
                      error_type="HTTPError", error_code=getattr(e, "code", None),
                      error_body=err_body[:2000])
        return json.dumps({"error": f"HTTP {getattr(e, 'code', 'unknown')}", "detail": err_body, "request_id": request_id})

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        _log_call_end(request_id, "finalize_project", "error", latency_ms,
                      error_type=type(e).__name__, error_message=str(e))
        return json.dumps({"error": f"{type(e).__name__}: {e}", "request_id": request_id})


if __name__ == "__main__":
    mcp.run()