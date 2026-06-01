from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
import os
import uvicorn

from mcp_server.auth.noke_jwt import validate_noke_token
from mcp_server.auth.oidc import router as oidc_router
from mcp_server.auth.oauth import router as oauth_router
from mcp_server.chat import router as chat_router
from mcp_server.config import MCP_API_KEY
from mcp_server.tools import (
    tool_get_units,
    tool_get_locks,
    tool_get_locks_to_units,
    tool_describe_table,
)

UI_FILE = Path(__file__).parent.parent / "index.html"

app = FastAPI(
    title="Noke Smart Entry MCP Server",
    description="Read-only MCP server — NOKE JWT authorization, per-user site scoping.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Sub-routers ───────────────────────────────────────────────────────────────
app.include_router(oidc_router)    # auth: /.well-known/openid-configuration, /.well-known/jwks.json
app.include_router(oauth_router)   # auth: /mcp/oauth/authorize, /mcp/oauth/token
app.include_router(chat_router)    # mcp:  /api/ai/chat

TOOL_MAP = {
    "get_units":          tool_get_units,
    "get_locks":          tool_get_locks,
    "get_locks_to_units": tool_get_locks_to_units,
}


# ── Models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    tool:       str        = Field(..., description="get_units | get_locks | get_locks_to_units | describe_table")
    user_token: str | None = Field(None, description="NOKE JWT — used when Authorization: Bearer header is not supplied")
    limit:      int        = Field(100, ge=1, le=1000)
    table:      str | None = Field(None, description="Required only for describe_table")


class QueryResponse(BaseModel):
    tool:      str
    user_id:   int
    site_id:   int | None
    row_count: int
    data:      list[dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
@app.get("/index.html")
def serve_ui():
    return FileResponse(UI_FILE)


@app.post("/api/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    x_api_key: str = Header(default="", alias="X-API-Key"),
    authorization: str = Header(default="", alias="Authorization"),
):
    """
    Protected query endpoint.
    Requires:
      X-API-Key header  — identifies Amazon Q Business as the trusted caller
      NOKE JWT supplied via one of:
        • Authorization: Bearer <NOKE_JWT>  (Q Business OAuth plugin path)
        • user_token body field             (direct API / dev testing path)
    """
    # 1. Validate API key
    if MCP_API_KEY and x_api_key != MCP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    # 2. Resolve NOKE JWT — prefer Authorization: Bearer header (Q Business OAuth path)
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    elif req.user_token:
        token = req.user_token

    if not token:
        raise HTTPException(status_code=401, detail="NOKE JWT required in Authorization: Bearer header or user_token body field.")

    # 3. Validate NOKE JWT — pure local SHA256 check, no network calls
    try:
        claims = validate_noke_token(token)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    user_id = claims["user_id"]
    site_id = claims["site_id"]

    # 3. Execute requested tool
    try:
        if req.tool == "describe_table":
            if not req.table:
                raise HTTPException(status_code=400, detail="'table' is required for describe_table.")
            data = tool_describe_table(req.table)

        elif req.tool in TOOL_MAP:
            data = TOOL_MAP[req.tool](user_id=user_id, limit=req.limit)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown tool '{req.tool}'. Available: {list(TOOL_MAP) + ['describe_table']}",
            )

        return QueryResponse(
            tool=req.tool,
            user_id=user_id,
            site_id=site_id,
            row_count=len(data),
            data=data,
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("mcp_server.main:app", host="0.0.0.0", port=8000, reload=False)
