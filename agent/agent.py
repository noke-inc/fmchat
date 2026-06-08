"""
agent/agent.py

Entry point for the Noke agent.  Delegates to the intent-based LangGraph
defined in agent/graph.py.

Flow:
  1. Validate NOKE JWT (if AGENT_AUTH_ENABLED=true) to extract user_id / site_id
  2. Invoke the intent-routing graph (classify → tool node → answer)
  3. Return answer + user context

See agent/graph.py for the full graph topology.
"""

import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from agent.graph import graph
from mcp_server.config import AGENT_AUTH_ENABLED
from mcp_server.auth.noke_jwt import validate_noke_token

logger = logging.getLogger(__name__)


async def run_agent(
    message: str,
    noke_jwt: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> dict:
    """
    Run the intent-based LangGraph agent for a single user message.

    Returns:
        {
            "answer":          str,
            "conversation_id": str | None,
            "user_id":         int,
            "site_id":         int | None,
        }
    """
    # ── 1. Auth ───────────────────────────────────────────────────────────────
    user_id: int = 0
    site_id: Optional[int] = None
    company: str = "unknown"

    if AGENT_AUTH_ENABLED:
        if not noke_jwt:
            raise PermissionError("Authorization: Bearer <NOKE_JWT> header is required.")
        claims  = validate_noke_token(noke_jwt)
        user_id = claims["user_id"]
        site_id = claims["site_id"]
        company = claims["company"]
        logger.info(
            "Agent request: user_id=%s site_id=%s company=%s", user_id, site_id, company
        )
    else:
        user_id = 1034747
        site_id = 2223363
        company = "1000233"
        logger.info("Agent running in no-auth mode (AGENT_AUTH_ENABLED=false)")

    # ── 2. Invoke intent-routing graph ────────────────────────────────────────
    logger.info("Running agent for message: %r", message[:120])

    result = await raph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "user_id":  user_id,
            "site_id":  site_id,
            "intent":   None,
        }
    )

    answer = result["messages"][-1].content
    logger.info("Agent answer: %r", str(answer)[:200])

    return {
        "answer":          answer,
        "conversation_id": conversation_id,
        "user_id":         user_id,
        "site_id":         site_id,
    }
