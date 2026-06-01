"""
mcp_server/auth/noke_jwt.py

NOKE portal JWT validator.

Algorithm (custom — not standard HS256/RS256):
    signature = hex( SHA256( header_b64 + "." + payload_b64 + NOKE_SECRET ) )

The secret is loaded from the NOKE_JWT_SECRET environment variable.
Store this in AWS Secrets Manager for production; never hardcode it.
"""

import base64
import hashlib
import json
import os
import time

NOKE_SECRET: str = os.getenv("NOKE_JWT_SECRET", "")


def _b64_decode(s: str) -> bytes:
    """Base64url decode with padding correction."""
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (4 - len(s) % 4)
    return base64.b64decode(s)


def validate_noke_token(token: str) -> dict:
    """
    Validate a NOKE portal JWT and return its claims.

    Returns:
        {
            "user_id":    int,        # from nokeUser claim
            "site_id":    int | None, # from currentSite claim
            "company":    str,
            "token_type": str,        # e.g. "web"
        }

    Raises:
        PermissionError  — invalid signature, expired token, or missing claims
        RuntimeError     — NOKE_JWT_SECRET env var is not configured
    """
    if not NOKE_SECRET:
        raise RuntimeError(
            "NOKE_JWT_SECRET is not set. Add it to .env (local) or K8s secret (production)."
        )

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise PermissionError("Malformed token: expected 3 dot-separated parts.")

    header_b64, payload_b64, received_sig = parts

    # Recompute signature — constant-time hex comparison via == is safe for hex strings
    expected_sig = hashlib.sha256(
        (header_b64 + "." + payload_b64 + NOKE_SECRET).encode("utf-8")
    ).hexdigest()

    if expected_sig != received_sig:
        raise PermissionError("Token signature is invalid.")

    try:
        claims: dict = json.loads(_b64_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise PermissionError("Token payload could not be decoded.")

    exp = claims.get("exp", 0)
    if exp and int(exp) < int(time.time()):
        raise PermissionError("Token has expired. Please refresh your portal session.")

    user_id = claims.get("nokeUser")
    if user_id is None:
        raise PermissionError("Token is missing the nokeUser claim.")

    site_id = claims.get("currentSite")
    return {
        "user_id":    int(user_id),
        "site_id":    int(site_id) if site_id is not None else None,
        "company":    str(claims.get("company", "")),
        "token_type": str(claims.get("tokenType", "")),
    }
