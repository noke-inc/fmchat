"""
mcp_server/chat.py

Amazon Q Business ChatSync proxy.
Ported from helpers/fmchat/chat.go.

Flow:
  Portal frontend  →  POST /api/ai/chat  (Authorization: Bearer <NOKE_JWT>)
    → validates NOKE JWT, extracts user_id
    → calls Q Business ChatSync API (boto3, uses EKS pod IAM role / ~/.aws/credentials locally)
    → if Q Business returns authChallengeRequests (first use of MCP plugin):
        generates OAuth code via generate_oauth_code() — no HTTP round-trip
        retries ChatSync with authChallengeResponses
        Q Business then calls POST /mcp/oauth/token to exchange code → access_token (NOKE JWT)
        Q Business calls POST /api/query with Authorization: Bearer <NOKE_JWT>
    → returns AI answer + conversation_id to portal
"""

import os
import uuid
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from mcp_server.auth.noke_jwt import validate_noke_token
from mcp_server.auth.oauth import generate_oauth_code

router = APIRouter()


class ChatRequest(BaseModel):
    message:         str         = Field(..., min_length=1, description="The user's chat message")
    conversation_id: str | None  = Field(None, description="Continue an existing conversation")


class ChatResponse(BaseModel):
    message:         str
    conversation_id: str | None = None


@router.post("/api/ai/chat", response_model=ChatResponse)
def ai_chat(
    req: ChatRequest,
    authorization: str = Header(default="", alias="Authorization"),
):
    """
    AI chat proxy — forwards portal chat messages to Amazon Q Business.

    Requires:
      Authorization: Bearer <NOKE_JWT>  — portal user's active session token

    The NOKE JWT is validated locally (no DB call for auth).
    User identity (nokeUser claim) is used as the Q Business userId.
    """
    # 1. Resolve and validate NOKE JWT
    noke_jwt = ""
    if authorization.startswith("Bearer "):
        noke_jwt = authorization[len("Bearer "):]

    if not noke_jwt:
        return JSONResponse(status_code=401, content={"error": "Authorization: Bearer <NOKE_JWT> header is required"})

    try:
        claims = validate_noke_token(noke_jwt)
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"error": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    user_id = f"noke-{claims['user_id']}"

    # 2. Config
    app_id = os.getenv("QBUSINESS_APP_ID", "")
    region = os.getenv("QBUSINESS_REGION", "us-east-1")

    if not app_id:
        return JSONResponse(status_code=500, content={"error": "QBUSINESS_APP_ID environment variable is not set"})

    # 3. Build boto3 client
    # On EKS: uses pod IAM role automatically.
    # Locally: uses ~/.aws/credentials or AWS_PROFILE env var.
    try:
        qb = boto3.client("qbusiness", region_name=region)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to create Q Business client: {e}"})

    # 4. First ChatSync call
    call_args: dict = {
        "applicationId": app_id,
        "userId":        user_id,
        "userMessage":   req.message,
        "clientToken":   str(uuid.uuid4()),
    }
    if req.conversation_id:
        call_args["conversationId"] = req.conversation_id

    try:
        response = qb.chat_sync(**call_args)
    except (BotoCoreError, ClientError) as e:
        return JSONResponse(status_code=502, content={"error": f"Q Business error: {e}"})

    # 5. Handle MCP plugin OAuth challenge (first time this userId uses the plugin)
    challenges = response.get("authChallengeRequests", [])
    if challenges:
        # Generate auth codes directly — no HTTP self-call needed
        auth_responses = []
        for ch in challenges:
            if ch.get("authorizationUrl"):
                code = generate_oauth_code(noke_jwt)
                auth_responses.append({"responseCode": code})

        if auth_responses:
            call_args["authChallengeResponses"] = auth_responses
            call_args["clientToken"] = str(uuid.uuid4())  # new idempotency token for retry

            try:
                response = qb.chat_sync(**call_args)
            except (BotoCoreError, ClientError) as e:
                return JSONResponse(status_code=502, content={"error": f"Q Business retry error: {e}"})

    # 6. Return result
    return ChatResponse(
        message=response.get("systemMessage", ""),
        conversation_id=response.get("conversationId"),
    )
