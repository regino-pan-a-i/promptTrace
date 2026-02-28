import json
import os
import boto3
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

LOG_BUCKET = os.environ.get("LOG_BUCKET", "ai-eval-logs-dev")


def lambda_handler(event, context):
    """
    Triggered when a project is finalized.
    Reads all interactions and outcomes for a candidate and computes hiring metrics.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        
        candidate_token = body.get("candidateToken")
        task_id = body.get("taskId")  # Optional: specific task, or all tasks if not provided
        
        if not candidate_token:
            return _response(400, {"error": "candidateToken is required"})
        
        candidate_id = candidate_token  # TODO: resolve via DynamoDB if needed
        
        # Fetch all interaction and outcome logs for the candidate
        interactions = _fetch_interactions(candidate_id, task_id)
        outcomes = _fetch_outcomes(candidate_id, task_id)
        
        if not interactions or not outcomes:
            return _response(400, {"error": "No interactions or outcomes found for candidate"})
        
        logger.info(f"Computing metrics for candidate {candidate_id}: {len(interactions)} interactions")
        
        # Compute foundational signals
        signals = _compute_signals(interactions, outcomes)
        
        # Compute composite scores
        scores = _compute_composite_scores(signals)
        
        # Generate hiring recommendation
        recommendation = _generate_recommendation(scores)
        
        # Write metrics summary to S3
        metrics_summary = {
            "candidateId": candidate_id,
            "taskId": task_id or "all-tasks",
            "timestamp": datetime.utcnow().isoformat(),
            "interactionCount": len(interactions),
            "outcomeCount": len(outcomes),
            "signals": signals,
            "scores": scores,
            "recommendation": recommendation,
        }
        
        _save_metrics_summary(candidate_id, metrics_summary)
        
        return _response(200, {
            "candidateId": candidate_id,
            "signals": signals,
            "scores": scores,
            "recommendation": recommendation,
        })
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return _response(500, {"error": str(e)})


def _fetch_interactions(candidate_id: str, task_id: str = None) -> list:
    """Fetch all interaction logs for a candidate from S3."""
    interactions = []
    
    # List all objects in interactions/ prefix
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(
        Bucket=LOG_BUCKET,
        Prefix=f"interactions/",
    )
    
    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            key = obj['Key']
            # Pattern: interactions/{year}/{month}/{day}/{candidateId}/{requestId}.json
            parts = key.split('/')
            if len(parts) >= 5 and parts[4] == candidate_id:
                try:
                    resp = s3.get_object(Bucket=LOG_BUCKET, Key=key)
                    data = json.loads(resp['Body'].read())
                    if task_id is None or data.get('taskId') == task_id:
                        interactions.append(data)
                except Exception as e:
                    logger.warning(f"Failed to read interaction {key}: {str(e)}")
    
    return interactions


def _fetch_outcomes(candidate_id: str, task_id: str = None) -> list:
    """Fetch all outcome logs for a candidate from S3."""
    outcomes = []
    
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(
        Bucket=LOG_BUCKET,
        Prefix=f"outcomes/",
    )
    
    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            key = obj['Key']
            # Pattern: outcomes/{year}/{month}/{day}/{candidateId}/{requestId}.json
            parts = key.split('/')
            if len(parts) >= 5 and parts[4] == candidate_id:
                try:
                    resp = s3.get_object(Bucket=LOG_BUCKET, Key=key)
                    data = json.loads(resp['Body'].read())
                    if task_id is None or data.get('taskId') == task_id:
                        outcomes.append(data)
                except Exception as e:
                    logger.warning(f"Failed to read outcome {key}: {str(e)}")
    
    return outcomes


def _compute_signals(interactions: list, outcomes: list) -> dict:
    """Compute 6 foundational signals from interactions and outcomes."""
    
    # Signal 1: Context Quality (0-100)
    # How thorough was the problem description?
    context_qualities = []
    for interaction in interactions:
        context_q = interaction.get("contextQuality", {})
        clarity = context_q.get("clarityScore", 0)
        context_qualities.append(clarity)
    
    context_quality_score = sum(context_qualities) / len(context_qualities) if context_qualities else 0
    
    # Signal 2: Analysis Depth (0-100)
    # Did they take time and ask questions?
    decision_speeds = []
    for outcome in outcomes:
        metrics = outcome.get("metrics", {})
        speed = metrics.get("decisionSpeed", 2000)  # Default 2000ms if not provided
        decision_speeds.append(speed)
    
    # Slower decisions (2000-5000ms) indicate analysis, faster (<500ms) indicate snap decisions
    analysis_depth_score = 0
    if decision_speeds:
        for speed in decision_speeds:
            if speed < 500:
                score_contribution = 20  # Snap decision - low thinking
            elif speed < 2000:
                score_contribution = 50  # Some thinking
            elif speed < 5000:
                score_contribution = 80  # Good thinking time
            else:
                score_contribution = 100  # Extended analysis
            analysis_depth_score += score_contribution
        analysis_depth_score / len(decision_speeds)
    
    # Signal 3: Critical Thinking (0-100)
    # Rejection rate, modification rate, test quality
    rejection_count = 0
    modification_count = 0
    test_passes_before = 0
    test_passes_after = 0
    
    for outcome in outcomes:
        metrics = outcome.get("metrics", {})
        rejection_count += metrics.get("rejectionCount", 0)
        modification_count += metrics.get("modificationCount", 0)
        
        test_before = metrics.get("testStatusBefore", {})
        test_after = metrics.get("testStatusAfter", {})
        test_passes_before += test_before.get("passing", 0)
        test_passes_after += test_after.get("passing", 0)
    
    # Higher modification/rejection rates with passing tests = good critical thinking
    critical_thinking_score = min(100, (modification_count * 10) + (rejection_count * 15))
    
    # Signal 4: Test Culture (0-100)
    # Did they write and run tests?
    test_coverage_changes = []
    for outcome in outcomes:
        metrics = outcome.get("metrics", {})
        coverage_change = metrics.get("testCoverageChange", 0)
        test_coverage_changes.append(coverage_change)
    
    test_culture_score = 0
    if test_coverage_changes:
        # Positive coverage changes = good test discipline
        test_culture_score = sum(max(0, change) for change in test_coverage_changes) / len(test_coverage_changes)
    
    # Signal 5: Code Quality (0-100)
    # Reduced complexity, removed duplication (from proposed edits quality tags)
    confidence_scores = []
    for interaction in interactions:
        model_response = interaction.get("modelResponse", {})
        proposed_edits = model_response.get("proposedEdits", [])
        for edit in proposed_edits:
            conf = edit.get("confidence", 70)
            confidence_scores.append(conf)
    
    code_quality_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
    
    # Signal 6: Decision Quality (0-100)
    # Post-edit tests pass? No new bugs?
    decision_quality_score = 0
    if test_passes_after > 0:
        # If tests pass after edits, quality is high
        decision_quality_score = min(100, (test_passes_after / (test_passes_before + 1)) * 100)
    
    return {
        "contextQuality": round(context_quality_score, 1),
        "analysisDepth": round(analysis_depth_score, 1),
        "criticalThinking": round(critical_thinking_score, 1),
        "testCulture": round(test_culture_score, 1),
        "codeQuality": round(code_quality_score, 1),
        "decisionQuality": round(decision_quality_score, 1),
    }


def _compute_composite_scores(signals: dict) -> dict:
    """Compute 3 composite scores from foundational signals."""
    
    # AI Leverage Score: Strategic acceptance of high-confidence suggestions
    # Combines codeQuality (confidence of suggestions) + decisionQuality (did they work)
    ai_leverage = (signals["codeQuality"] * 0.4 + signals["decisionQuality"] * 0.6)
    
    # Problem Solver Score: Understanding + Analysis Depth + Critical Thinking
    problem_solver = (signals["analysisDepth"] * 0.4 + 
                     signals["criticalThinking"] * 0.35 + 
                     signals["contextQuality"] * 0.25)
    
    # Engineer Score: Testing discipline + Code quality
    engineer = (signals["testCulture"] * 0.5 + signals["codeQuality"] * 0.5)
    
    return {
        "aiLeverage": round(ai_leverage, 1),
        "problemSolver": round(problem_solver, 1),
        "engineer": round(engineer, 1),
    }


def _generate_recommendation(scores: dict) -> str:
    """Generate hiring recommendation based on composite scores."""
    
    problem_solver = scores["problemSolver"]
    engineer = scores["engineer"]
    ai_leverage = scores["aiLeverage"]
    
    # Thresholds
    excellent_threshold = 75
    good_threshold = 60
    
    if problem_solver >= excellent_threshold and engineer >= excellent_threshold:
        return "🟢 HIRE"
    elif (problem_solver >= good_threshold and engineer >= good_threshold) or ai_leverage >= excellent_threshold:
        return "🟡 INTERVIEW"
    else:
        return "🔴 PASS"


def _save_metrics_summary(candidate_id: str, metrics_summary: dict):
    """Save metrics summary to S3."""
    key = f"metrics/{candidate_id}/summary.json"
    s3.put_object(
        Bucket=LOG_BUCKET,
        Key=key,
        Body=json.dumps(metrics_summary, indent=2),
        ContentType="application/json"
    )
    logger.info(f"Saved metrics summary to {key}")


def _response(status_code: int, body: dict) -> dict:
    """Format Lambda response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
