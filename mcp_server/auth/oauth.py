"""
mcp_server/auth/oauth.py

OAuth 2.0 Authorization-Code endpoints for the Amazon Q Business MCP plugin.

Flow:
  1. Q Business calls  GET  /mcp/oauth/authorize
     Caller supplies NOKE JWT via X-Noke-Token or Authorization: Bearer header.
     → validates JWT, stores code→JWT (TTL 5 min), redirects or returns JSON

  2. Q Business calls  POST /mcp/oauth/token  (form-encoded)
     → validates client_secret, exchanges code for NOKE JWT access_token

Code storage: Redis when REDIS_HOST is set; in-memory TTL dict for local dev.
"""

import os
import secrets
import threading
import time
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mcp_server.auth.noke_jwt import validate_noke_token

router = APIRouter()

# ── Code store ────────────────────────────────────────────────────────────────

_CODE_TTL = 300  # seconds — 5 minutes
_mem_store: dict[str, tuple[str, float]] = {}  # code → (noke_jwt, expires_at)
_mem_lock = threading.Lock()
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    host = os.getenv("REDIS_HOST", "")
    if not host:
        return None
    try:
        import redis as redis_lib
        port = int(os.getenv("REDIS_PORT", "6379"))
        _redis_client = redis_lib.Redis(
            host=host, port=port,
            ssl=os.getenv("REDIS_TLS", "true").lower() == "true",
            decode_responses=True,
        )
        _redis_client.ping()
    except Exception:
        _redis_client = None
    return _redis_client


def generate_oauth_code(noke_jwt: str) -> str:
    """
    Store noke_jwt under a random code (TTL = 5 min) and return the code.
    Called both by the HTTP authorize endpoint and directly by the chat proxy
    when handling Q Business auth challenge requests.
    """
    code = secrets.token_urlsafe(32)
    rdb = _get_redis()
    if rdb:
        rdb.setex(f"mcp_oauth:{code}", _CODE_TTL, noke_jwt)
    else:
        with _mem_lock:
            _mem_store[code] = (noke_jwt, time.time() + _CODE_TTL)
    return code


def consume_oauth_code(code: str) -> Optional[str]:
    """
    Retrieve and delete the NOKE JWT for the given code (one-time use).
    Returns None if the code is missing or expired.
    """
    rdb = _get_redis()
    if rdb:
        key = f"mcp_oauth:{code}"
        noke_jwt = rdb.get(key)
        if noke_jwt:
            rdb.delete(key)
        return noke_jwt or None
    else:
        with _mem_lock:
            entry = _mem_store.pop(code, None)
            if not entry:
                return None
            noke_jwt, expires_at = entry
            if time.time() > expires_at:
                return None
            return noke_jwt


def _is_allowed_redirect_uri(uri: str) -> bool:
    """Exact-match check against FMCHAT_OAUTH_REDIRECT_URIS (comma-separated)."""
    allowed = os.getenv("FMCHAT_OAUTH_REDIRECT_URIS", "")
    if not allowed:
        return False
    return any(entry.strip() == uri for entry in allowed.split(","))


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/mcp/oauth/authorize")
def oauth_authorize(
    request: Request,
    redirect_uri: str = "",
    state: str = "",
    response_type: str = "code",
    client_id: str = "",
    x_noke_token: str = Header(default="", alias="X-Noke-Token"),
    authorization: str = Header(default="", alias="Authorization"),
):
    """
    OAuth 2.0 Authorization endpoint.

    Validates the portal user's NOKE JWT and issues a one-time authorization code.
    The NOKE JWT must be supplied via:
      - X-Noke-Token header          (preferred for server-to-server calls)
      - Authorization: Bearer <jwt>  (standard OAuth bearer)
    """
    if redirect_uri and not _is_allowed_redirect_uri(redirect_uri):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "redirect_uri is not registered"},
        )

    noke_jwt = x_noke_token
    if not noke_jwt and authorization.startswith("Bearer "):
        noke_jwt = authorization[len("Bearer "):]

    if not noke_jwt:
        return JSONResponse(
            status_code=401,
            content={"error": "missing_token", "error_description": "NOKE JWT required in X-Noke-Token or Authorization: Bearer header"},
        )

    try:
        validate_noke_token(noke_jwt)
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"error": "invalid_token", "error_description": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=500, content={"error": "server_error", "error_description": str(e)})

    code = generate_oauth_code(noke_jwt)

    if redirect_uri:
        params: dict = {"code": code}
        if state:
            params["state"] = state
        return RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}", status_code=302)

    return JSONResponse(content={"code": code, "state": state})


@router.post("/mcp/oauth/token")
def oauth_token(
    grant_type: str = Form(default="authorization_code"),
    code: str = Form(default=""),
    client_id: str = Form(default=""),
    client_secret: str = Form(default=""),
    redirect_uri: str = Form(default=""),
):
    """
    OAuth 2.0 Token endpoint.

    Amazon Q Business calls this to exchange an authorization code for an access_token.
    Returns the portal user's NOKE JWT as the access_token.
    """
    expected_secret = os.getenv("FMCHAT_OAUTH_CLIENT_SECRET", "")
    if expected_secret and client_secret != expected_secret:
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_client", "error_description": "client_secret mismatch"},
        )

    if not code:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "code is required"},
        )

    noke_jwt = consume_oauth_code(code)
    if not noke_jwt:
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_grant", "error_description": "code not found or expired"},
        )

    return JSONResponse(content={
        "access_token": noke_jwt,
        "token_type":   "bearer",
        "expires_in":   28800,  # 8 hours — matches portal session length
    })
