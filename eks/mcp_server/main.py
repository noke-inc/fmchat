"""
mcp_server/main.py

FastAPI application entry point.

Endpoints
─────────
GET  /health        liveness probe
GET  /mcp-http/     MCP streamable-http endpoint — AgentCore Gateway connects here
GET  /mcp           MCP SSE endpoint — local/dev LangChain usage
POST /api/query     Direct MCP tool call (JWT + API-key protected, for testing)
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

from mcp_server.auth.noke_jwt import validate_noke_token
from mcp_server.config import MCP_API_KEY
from mcp_server.tools import (
    tool_aggregate_query,
    tool_search_records,
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
def aggregate_query(
    user_id: int,
    entity: str,
    aggregation: str,
    agg_column: str | None = None,
    group_by: list[str] | None = None,
    filters: list[dict] | None = None,
) -> dict:
    """
    Run a deterministic aggregation (count/sum/avg) over an entity.

    entity       — semantic name: 'unit' | 'user' | 'site'
    aggregation  — 'count' | 'sum' | 'avg'
    agg_column   — required for sum/avg (e.g. 'details_price')
    group_by     — optional list of columns to group by (e.g. ['rental_state'])
    filters      — optional list of {column, operator, value} dicts

    Returns {results, corrections, metadata} or {error, code} on failure.
    """
    logger.debug(
        "MCP tool: aggregate_query user_id=%s entity=%s aggregation=%s group_by=%s filters=%s",
        user_id, entity, aggregation, group_by, filters,
    )
    return tool_aggregate_query(
        user_id=user_id,
        entity=entity,
        aggregation=aggregation,
        agg_column=agg_column,
        group_by=group_by,
        filters=filters,
    )


@mcp.tool()
def search_records(
    user_id: int,
    entity: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    sort_column: str | None = None,
    sort_direction: str | None = None,
    limit: int = 50,
) -> dict:
    """
    Retrieve records for an entity scoped to the calling user's sites.

    entity         — semantic name: 'unit' | 'user' | 'site'
    columns        — columns to return (None = entity defaults)
    filters        — optional list of {column, operator, value} dicts
    sort_column    — column to sort by (None = default)
    sort_direction — 'ASC' | 'DESC' (None = default)
    limit          — max rows to return (1-200, default 50)

    Returns {results, corrections, metadata} or {error, code} on failure.
    """
    logger.debug(
        "MCP tool: search_records user_id=%s entity=%s columns=%s filters=%s limit=%s",
        user_id, entity, columns, filters, limit,
    )
    return tool_search_records(
        user_id=user_id,
        entity=entity,
        columns=columns,
        filters=filters,
        sort_column=sort_column,
        sort_direction=sort_direction,
        limit=limit,
    )


# Build streamable MCP app once so we can reuse its lifespan in the parent FastAPI app.
mcp_http_app = mcp.http_app(path="/", transport="streamable-http")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Noke Smart Entry — MCP Server",
    description="MCP tool server for AgentCore Gateway and local dev usage.",
    version="3.0.0",
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

# Gateway-compatible MCP endpoint (Streamable HTTP)
# AgentCore Gateway target should point to: https://mcp.smartentry.noke.dev/mcp-http/
app.mount("/mcp-http", mcp_http_app)

# SSE MCP endpoint kept for local/dev LangChain MultiServerMCPClient usage
# Local agent URL remains: http://localhost:8000/mcp/sse
app.mount("/mcp", mcp.sse_app())

logger.info("MCP server starting — api_key_required=%s", bool(MCP_API_KEY))

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── Static UI ─────────────────────────────────────────────────────────────────
# NOTE: mount LAST — catch-all "/" shadows any routes defined after it.
# Only mounted when the ui/ directory exists (local dev only).
# In EKS the container has no ui/ directory.
UI_DIR = Path(__file__).resolve().parent.parent.parent / "ui"


# ── Direct query endpoint (JWT + API-key protected, kept for direct testing) ──

class QueryRequest(BaseModel):
    tool:           str             = Field(..., description="aggregate_query | search_records")
    entity:         str             = Field(..., description="Semantic entity: 'unit' | 'user' | 'site'")
    user_token:     str | None      = Field(None, description="NOKE JWT (fallback when no Authorization header)")
    aggregation:    str | None      = Field(None, description="count | sum | avg — required for aggregate_query")
    agg_column:     str | None      = Field(None, description="Column for sum/avg")
    group_by:       list[str] | None = Field(None, description="Columns to group by")
    columns:        list[str] | None = Field(None, description="Columns to return for search_records")
    filters:        list[dict] | None = Field(None, description="List of {column, operator, value} dicts")
    sort_column:    str | None      = Field(None)
    sort_direction: str | None      = Field(None, description="ASC | DESC")
    limit:          int             = Field(50, ge=1, le=200)


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
        if req.tool == "aggregate_query":
            if not req.aggregation:
                raise HTTPException(status_code=400, detail="'aggregation' required for aggregate_query.")
            result = tool_aggregate_query(
                user_id=user_id, entity=req.entity, aggregation=req.aggregation,
                agg_column=req.agg_column, group_by=req.group_by, filters=req.filters,
            )
        elif req.tool == "search_records":
            result = tool_search_records(
                user_id=user_id, entity=req.entity, columns=req.columns,
                filters=req.filters, sort_column=req.sort_column,
                sort_direction=req.sort_direction, limit=req.limit,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown tool '{req.tool}'. Available: aggregate_query, search_records",
            )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        data = result.get("results", [])
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

