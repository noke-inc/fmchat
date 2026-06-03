"""
agent/agent.py

LangChain ReAct agent backed by Amazon Bedrock (nova-micro) and the Noke MCP server.

Flow:
  1. Receive user message + optional NOKE JWT (AGENT_AUTH_ENABLED=false → skip auth)
  2. Connect to MCP server SSE endpoint to load available tools
  3. Run ReAct agent via langgraph.prebuilt.create_react_agent
  4. Return final answer

MCP connection uses langchain-mcp-adapters which wraps the MCP SSE transport.
Bedrock credentials come from the EKS pod IAM role — no API key needed.
"""

import logging
from typing import Optional

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from mcp_server.config import (
    BEDROCK_REGION,
    BEDROCK_MODEL_ID,
    AGENT_MCP_URL,
    AGENT_AUTH_ENABLED,
)
from mcp_server.auth.noke_jwt import validate_noke_token

logger = logging.getLogger(__name__)

# ── System prompt template ─────────────────────────────────────────────────────
_SYSTEM_TEMPLATE = (
    "You are a helpful AI assistant for Noke Smart Entry property management. "
    "You have access to tools that query the Noke database in read-only mode. "
    "Only use the provided tools; do not make up data. "
    "If a tool returns an error, explain it clearly to the user. "
    "Keep answers concise and relevant to property management. "
    "User context: user_id={user_id}, site_id={site_id}."
)


def _build_llm() -> ChatBedrock:
    """Build the Bedrock LLM. Uses EKS pod IAM role for credentials."""
    logger.info("Initialising Bedrock LLM: model=%s region=%s", BEDROCK_MODEL_ID, BEDROCK_REGION)
    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        model_kwargs={
            "temperature": 0,
            "max_tokens": 2048,
        },
    )


async def run_agent(
    message: str,
    noke_jwt: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> dict:
    """
    Run the LangChain agent for a single user message.

    Returns:
        {
            "answer": str,
            "conversation_id": str | None,
            "user_id": int,
            "site_id": int | None,
        }
    """
    # ── 1. Auth (JWT validation — skip when AGENT_AUTH_ENABLED=false) ─────────
    user_id: int = 0
    site_id: Optional[int] = None
    company: str = "unknown"

    if AGENT_AUTH_ENABLED:
        if not noke_jwt:
            raise PermissionError("Authorization: Bearer <NOKE_JWT> header is required.")
        claims = validate_noke_token(noke_jwt)  # raises PermissionError on failure
        user_id  = claims["user_id"]
        site_id  = claims["site_id"]
        company  = claims["company"]
        logger.info("Agent request: user_id=%s site_id=%s company=%s", user_id, site_id, company)
    else:
        logger.info("Agent running in no-auth mode (AGENT_AUTH_ENABLED=false)")

    # ── 2. Connect to MCP server and load tools ───────────────────────────────
    logger.debug("Connecting to MCP SSE endpoint: %s", AGENT_MCP_URL)

    # langchain-mcp-adapters >=0.1.0 no longer supports async-with context
    # manager — call get_tools() directly on the client instance.
    mcp_client = MultiServerMCPClient(
        {
            "noke-mcp": {
                "url": AGENT_MCP_URL,
                "transport": "sse",
            }
        }
    )
    tools = await mcp_client.get_tools()
    logger.info("Loaded %d MCP tools: %s", len(tools), [t.name for t in tools])

    # ── 3. Build and run agent (langgraph ReAct) ──────────────────────────────
    system_prompt = _SYSTEM_TEMPLATE.format(user_id=user_id, site_id=site_id)
    llm   = _build_llm()
    graph = create_react_agent(llm, tools, prompt=system_prompt)

    logger.info("Running agent for message: %r", message[:120])

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=message)]}
    )

    # Final message from the agent is the last AIMessage in the list
    answer = result["messages"][-1].content
    logger.info("Agent answer: %r", str(answer)[:200])

    return {
        "answer":          answer,
        "conversation_id": conversation_id,
        "user_id":         user_id,
        "site_id":         site_id,
    }
