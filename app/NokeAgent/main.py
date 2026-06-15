"""
app/NokeAgent/main.py

Amazon Bedrock AgentCore Runtime entrypoint for the Noke Smart Entry agent.

Stack:
  Framework      : LangGraph  (intent-routing graph)
  Model provider : Amazon Bedrock  (Nova Micro, configurable via BEDROCK_MODEL_ID)
  Memory         : Short-term — LangGraph MemorySaver per session
  Deployment     : AWS Bedrock AgentCore (CodeZip)

Request payload (any of these fields):
  {
    "prompt":     "How many units do I have?",
    "session_id": "user-abc-session-xyz",   # optional — drives short-term memory
    "user_id":    1034747,                   # optional
    "site_id":    2223363                    # optional
  }

Local dev:
  cd <project-root>
  agentcore dev              # browser inspector on :8080
  agentcore dev --no-browser # TUI mode

Deploy:
  agentcore deploy
"""

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from auth.noke_jwt import validate_noke_token
from config import AGENT_AUTH_ENABLED
from graph import build_graph          # graph.py in same directory

# ── Instrumentation ───────────────────────────────────────────────────────────
LangchainInstrumentor().instrument()

# ── AgentCore app ─────────────────────────────────────────────────────────────
app = BedrockAgentCoreApp()
log = app.logger

# ── Build LangGraph once at cold start — MemorySaver gives short-term memory ─
_memory = MemorySaver()
_graph  = build_graph(checkpointer=_memory)


@app.entrypoint
async def invoke(payload: dict[str, Any], context: Any):
    """
    AgentCore Runtime invocation handler.

    Each session_id maps to a LangGraph thread_id, so MemorySaver retains
    conversation history within a session (short-term memory).  AgentCore
    Runtime ensures each user session runs in an isolated microVM.
    """
    session_id: str = (
        payload.get("session_id")
        or payload.get("sessionId")
        or "default-session"
    )

    # First step: optional JWT auth guard controlled by AGENT_AUTH_ENABLED.
    claims: dict | None = None
    if AGENT_AUTH_ENABLED:
      authorization = str(payload.get("authorization", "")).strip()
      token = (
        authorization.removeprefix("Bearer ").strip()
        if authorization.startswith("Bearer ")
        else str(payload.get("jwt_token") or payload.get("user_token") or "").strip()
      )
      if not token:
        return {
          "error": "Missing JWT token. Provide 'authorization: Bearer <token>' or 'jwt_token'."
        }
      try:
        claims = validate_noke_token(token)
      except PermissionError as e:
        return {"error": f"JWT validation failed: {e}"}
      except RuntimeError as e:
        return {"error": f"JWT configuration error: {e}"}

    prompt: str = payload.get("prompt") or payload.get("message", "")
    user_id = int(claims["user_id"]) if claims else int(payload.get("user_id", 1034747))
    site_id = int(claims["site_id"]) if claims else payload.get("site_id","2223363")
    if site_id is not None:
      site_id = int(site_id)

    log.info(
        "Invoke: session=%s user_id=%s site_id=%s prompt=%r",
        session_id, user_id, site_id, str(prompt)[:120],
    )

    if not prompt:
        return {"error": "Missing 'prompt' or 'message' field in request."}

    # LangGraph config — thread_id drives MemorySaver checkpointing
    config = {"configurable": {"thread_id": session_id}}

    result = await _graph.ainvoke(
        {
            "messages": [HumanMessage(content=prompt)],
            "user_id":  user_id,
            "site_id":  site_id,
            "intent":   None,
        },
        config=config,
    )

    answer: str = result["messages"][-1].content

    # Strip any <thinking>...</thinking> blocks that reasoning models emit.
    # These are internal model reasoning and must never be shown to end users.
    answer = re.sub(r"<thinking>.*?</thinking>", "", answer, flags=re.DOTALL).strip()

    log.info("Answer: session=%s answer=%r", session_id, str(answer)[:200])

    return {"result": answer, "session_id": session_id}


if __name__ == "__main__":
    app.run()
