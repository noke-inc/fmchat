"""
lambda/chat_proxy.py

AWS Lambda handler — public chat API bridge.

Flow:
  API Gateway HTTP API  →  POST /chat
  Lambda (this file)    →  boto3 invoke_agent_runtime
  NokeAgent runtime     →  NokeMCP runtime  →  RDS MySQL

Environment variables (set by CDK):
  NOKEAGENT_RUNTIME_ARN  — ARN of the deployed NokeAgent AgentCore runtime

Request body (JSON):
  { "message": "How many units do I have?", "conversation_id": "optional-string" }

Response (JSON):
  { "answer": "...", "conversation_id": "...", "user_id": 1034747, "site_id": null }

No external dependencies — boto3 is pre-installed in Lambda Python 3.12 runtime.
"""

import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AGENT_ARN = os.environ["NOKEAGENT_RUNTIME_ARN"]
REGION    = os.environ.get("AWS_REGION", "us-east-2")

# Re-use client across warm invocations
_client = boto3.client("bedrock-agentcore", region_name=REGION)

CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers":    {**CORS, "Content-Type": "application/json"},
        "body":       json.dumps(body),
    }


def handler(event: dict, context) -> dict:
    method = (
        event.get("requestContext", {})
             .get("http", {})
             .get("method", "")
             .upper()
    )

    # CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    # Parse request body
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON body"})

    message = (body.get("message") or "").strip()
    if not message:
        return _response(400, {"error": "'message' field is required"})

    session_id = body.get("conversation_id") or f"ui-{uuid.uuid4().hex[:8]}"

    logger.info("invoke: session=%s prompt=%r", session_id, message[:120])

    payload = json.dumps({
        "prompt":     message,
        "session_id": session_id,
        "user_id":    1034747,
    }).encode()

    try:
        resp   = _client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            qualifier="DEFAULT",
            payload=payload,
        )
        result = json.loads(resp["response"].read())
    except Exception as exc:
        logger.exception("invoke_agent_runtime failed: %s", exc)
        return _response(502, {"error": f"Agent error: {exc}"})

    answer = (
        result.get("answer")
        or result.get("result")
        or result.get("response")
        or str(result)
    )

    logger.info("response: session=%s answer=%r", session_id, str(answer)[:120])

    return _response(200, {
        "answer":          answer,
        "conversation_id": session_id,
        "user_id":         1034747,
        "site_id":         None,
    })
