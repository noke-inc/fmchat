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
import os
from logging.handlers import RotatingFileHandler
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

# Central logging configuration: console + optional rotating file handler.
# Controlled via env vars: LOG_LEVEL (DEBUG|INFO|WARNING) and LOG_FILE (path).
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_level = getattr(logging, LOG_LEVEL, logging.INFO)
handlers = []

# Console handler (always enabled)
console_handler = logging.StreamHandler()
console_handler.setLevel(_level)
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
# Make console stream unicode-safe on Windows (replace unencodable chars)
try:
  import sys, io
  console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
  console_handler.stream = console_stream
except Exception:
  pass
handlers.append(console_handler)

# Optional file handler when LOG_FILE is set
LOG_FILE = os.getenv("LOG_FILE", "")
if LOG_FILE:
  try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
  except Exception:
    pass
  file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
  file_handler.setLevel(_level)
  file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
  handlers.append(file_handler)

logging.basicConfig(level=_level, handlers=handlers)

# Route common library loggers to the configured level so their logs appear
lib_loggers = [
  "uvicorn", "uvicorn.error", "uvicorn.access",
  "botocore", "boto3", "urllib3",
  "asyncio", "aiobotocore", "httpx",
  "langchain", "langgraph", "bedrock_agentcore", "agentcore",
  "opentelemetry", "awscrt",
]
for _n in lib_loggers:
  try:
    logging.getLogger(_n).setLevel(_level)
  except Exception:
    pass

# Allowlist filter: limit console/file logs to application loggers only.
# Controlled via env var ALLOWED_LOGGER_PREFIXES (comma-separated prefixes).
ALLOWED = os.getenv("ALLOWED_LOGGER_PREFIXES", "bedrock_agentcore,graph,app,NokeAgent,stdout,stderr")
allowed_prefixes = [p.strip() for p in ALLOWED.split(",") if p.strip()]

class _AllowedFilter(logging.Filter):
  def __init__(self, prefixes):
    super().__init__()
    self.prefixes = prefixes

  def filter(self, record):
    for p in self.prefixes:
      if record.name.startswith(p):
        return True
    return False

filt = _AllowedFilter(allowed_prefixes)
for h in logging.getLogger().handlers:
  try:
    h.addFilter(filt)
  except Exception:
    pass

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
    print(f"Received request: session_id={session_id} payload={payload}")
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

    company_uuid = claims["company"] if claims else payload.get("company_uuid")

    result = await _graph.ainvoke(
      {
        "messages": [HumanMessage(content=prompt)],
        "user_id":  user_id,
        "site_id":  site_id,
        "company_uuid": company_uuid,
        "intent":   None,
      },
      config=config,
    )

    # Normalize answer — Bedrock may return content as a list of parts rather
    # than a plain string (e.g. when the final message follows a tool-use turn).
    raw = result["messages"][-1].content
    if isinstance(raw, list):
        answer: str = " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in raw
        ).strip()
    else:
        answer: str = str(raw)

    # Strip any <thinking>...</thinking> blocks that reasoning models emit.
    # These are internal model reasoning and must never be shown to end users.
    answer = re.sub(r"<thinking>.*?</thinking>", "", answer, flags=re.DOTALL).strip()

    log.info("Answer: session=%s answer=%r", session_id, str(answer)[:200])

    return {"result": answer, "session_id": session_id}


if __name__ == "__main__":
    app.run()
