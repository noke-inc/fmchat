# mcp_server/auth — authentication and identity sub-package
#
# noke_jwt.py  — NOKE portal JWT validator (custom SHA-256 algorithm)
# oauth.py     — OAuth 2.0 authorize + token endpoints (MCP plugin auth for Q Business)
# oidc.py      — OIDC discovery document + JWKS endpoint (acts as OIDC Identity Provider)
# db_user.py   — DB-backed user validation and site-scope resolution

# Re-export so existing callers (`from mcp_server.auth import resolve_user_sites`) still work.
from mcp_server.auth.db_user import validate_user, get_user_sites, resolve_user_sites

__all__ = ["validate_user", "get_user_sites", "resolve_user_sites"]
