"""
agent/routes.py

FastAPI router for the LangChain agent endpoint.

POST /agent/chat
  Body:  { "message": "...", "conversation_id": "..." }
  Header (optional for now): Authorization: Bearer <NOKE_JWT>
  Returns: { "answer": "...", "conversation_id": "...", "user_id": 0, "site_id": null }
"""

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agent.agent import run_agent

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message:         str        = Field(..., min_length=1, description="User's chat message")
    conversation_id: str | None = Field(None, description="Optional: continue an existing conversation")


class ChatResponse(BaseModel):
    answer:          str
    conversation_id: str | None = None
    user_id:         int        = 0
    site_id:         int | None = None


@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(
    req: ChatRequest,
    authorization: str = Header(default="", alias="Authorization"),
):
    """
    LangChain + Bedrock agent endpoint.

    - Loads tools from the MCP server via SSE (/mcp)
    - Runs a ReAct agent using Amazon Bedrock (nova-micro)
    - No auth required when AGENT_AUTH_ENABLED=false (default)
    - Pass Authorization: Bearer <NOKE_JWT> to enable user-scoped queries
    """
    noke_jwt = authorization.removeprefix("Bearer ").strip() or None

    logger.info("POST /agent/chat | message=%r | jwt_present=%s", req.message[:80], bool(noke_jwt))

    try:
        result = await run_agent(
            message=req.message,
            noke_jwt=noke_jwt,
            conversation_id=req.conversation_id,
        )
        return ChatResponse(**result)

    except PermissionError as e:
        logger.warning("Auth failure: %s", e)
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Agent error: %s", e)
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
