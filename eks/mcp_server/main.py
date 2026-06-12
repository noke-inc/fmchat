"""
mcp_server/main.py

FastAPI application entry point.

Endpoints
─────────
GET  /health                   liveness probe
GET  /mcp                      MCP SSE endpoint — LangChain agent discovers tools here
POST /agent/chat               LangChain + Bedrock agent (new chat entry point)
POST /api/query                Direct MCP tool call (JWT + API-key protected, for testing)
GET  /                         Serves ui/index.html
"""

import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from agent.routes import router as agent_router
from mcp_server.auth.noke_jwt import validate_noke_token
from mcp_server.config import (
    AGENT_AUTH_ENABLED,
    AGENT_MCP_URL,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    MCP_API_KEY,
)
from mcp_server.tools import (
    tool_describe_table,
    tool_get_locks,
    tool_get_locks_to_units,
    tool_get_units,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── MCP server (fastmcp) ──────────────────────────────────────────────────────
# Registers DB tools so LangChain can discover and call them via SSE at GET /mcp
mcp = FastMCP("Noke Smart Entry MCP")


@mcp.tool()
def get_units(user_id: int, limit: int = 100) -> list[dict]:
    """Return storage units scoped to the sites assigned to this user."""
    logger.debug("MCP tool: get_units user_id=%s limit=%s", user_id, limit)
    return tool_get_units(user_id=user_id, limit=limit)


@mcp.tool()
def get_locks(user_id: int, limit: int = 100) -> list[dict]:
    """Return locks scoped to the sites assigned to this user."""
    logger.debug("MCP tool: get_locks user_id=%s limit=%s", user_id, limit)
    return tool_get_locks(user_id=user_id, limit=limit)


@mcp.tool()
def get_locks_to_units(user_id: int, limit: int = 100) -> list[dict]:
    """Return lock-to-unit assignments scoped to the sites assigned to this user."""
    logger.debug("MCP tool: get_locks_to_units user_id=%s limit=%s", user_id, limit)
    return tool_get_locks_to_units(user_id=user_id, limit=limit)


@mcp.tool()
def describe_table(table: str) -> list[dict]:
    """Return column metadata for the given table name."""
    logger.debug("MCP tool: describe_table table=%s", table)
    return tool_describe_table(table)


# Build streamable MCP app once so we can reuse its lifespan in the parent FastAPI app.
mcp_http_app = mcp.http_app(path="/", transport="streamable-http")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Noke Smart Entry — Agent + MCP Server",
    description=(
        "LangChain/Bedrock agent server with MCP SSE tool endpoint. "
        "AGENT_AUTH_ENABLED=false skips JWT validation (current phase)."
    ),
    version="1.0.0",
    lifespan=mcp_http_app.lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class NoCacheStaticFiles(StaticFiles):
    """Static file handler that disables browser caching for local UI assets."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

# POST /agent/chat
app.include_router(agent_router)

# Gateway-compatible MCP endpoint (Streamable HTTP)
# AgentCore Gateway target should point to: https://mcp.smartentry.noke.dev/mcp-http/
app.mount("/mcp-http", mcp_http_app)

# SSE MCP endpoint kept for local/dev LangChain MultiServerMCPClient usage
# Local agent URL remains: http://localhost:8000/mcp/sse
app.mount("/mcp", mcp.sse_app())

logger.info(
    "Server config: model=%s region=%s auth_enabled=%s agent_mcp_url=%s",
    BEDROCK_MODEL_ID, BEDROCK_REGION, AGENT_AUTH_ENABLED, AGENT_MCP_URL,
)

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":       "ok",
        "auth_enabled": AGENT_AUTH_ENABLED,
        "model":        BEDROCK_MODEL_ID,
        "region":       BEDROCK_REGION,
    }


# ── Static UI ─────────────────────────────────────────────────────────────────
# NOTE: mount LAST — catch-all "/" shadows any routes defined after it.
# Only mounted when the ui/ directory actually exists (local dev only).
# In EKS the container has no ui/ directory — only /agent/chat and /mcp/sse are needed.
UI_DIR = Path(__file__).resolve().parent.parent.parent / "ui"


# ── Direct query endpoint (JWT + API-key protected, kept for direct testing) ──
TOOL_MAP = {
    "get_units":          tool_get_units,
    "get_locks":          tool_get_locks,
    "get_locks_to_units": tool_get_locks_to_units,
}


class QueryRequest(BaseModel):
    tool:       str        = Field(..., description="get_units | get_locks | get_locks_to_units | describe_table")
    user_token: str | None = Field(None, description="NOKE JWT (fallback when no Authorization header)")
    limit:      int        = Field(100, ge=1, le=1000)
    table:      str | None = Field(None, description="Required for describe_table")


class QueryResponse(BaseModel):
    tool:      str
    user_id:   int
    site_id:   int | None
    row_count: int
    data:      list[dict]


@app.post("/api/query", response_model=QueryResponse)
def query(
    req:           QueryRequest,
    x_api_key:     str = Header(default="", alias="X-API-Key"),
    authorization: str = Header(default="", alias="Authorization"),
):
    """Direct MCP tool query. Requires X-API-Key + valid NOKE JWT."""
    logger.info("POST /api/query tool=%s", req.tool)

    if MCP_API_KEY and x_api_key != MCP_API_KEY:
        logger.warning("Invalid API key on /api/query")
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    if not token and req.user_token:
        token = req.user_token
    if not token:
        raise HTTPException(status_code=401, detail="NOKE JWT required.")

    try:
        claims = validate_noke_token(token)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    user_id = claims["user_id"]
    site_id = claims["site_id"]
    logger.info("/api/query user_id=%s site_id=%s tool=%s", user_id, site_id, req.tool)

    try:
        if req.tool == "describe_table":
            if not req.table:
                raise HTTPException(status_code=400, detail="'table' required for describe_table.")
            data = tool_describe_table(req.table)
        elif req.tool in TOOL_MAP:
            data = TOOL_MAP[req.tool](user_id=user_id, limit=req.limit)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown tool '{req.tool}'. Available: {list(TOOL_MAP) + ['describe_table']}",
            )
        return QueryResponse(
            tool=req.tool, user_id=user_id, site_id=site_id,
            row_count=len(data), data=data,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in /api/query: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ── Static mount MUST be last — "/" catches all unmatched paths ───────────────
if UI_DIR.exists():
    app.mount("/", NoCacheStaticFiles(directory=UI_DIR, html=True), name="ui")
    logger.info("Serving static UI from %s", UI_DIR)
else:
    logger.info("No ui/ directory found — static UI not mounted (EKS mode)")


if __name__ == "__main__":
    uvicorn.run("mcp_server.main:app", host="0.0.0.0", port=8000, reload=False)

