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


def _b64_decode(s: str) -> bytes:
    """Base64url decode with padding correction."""
    s = s.replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    if pad:
        s += "=" * pad
    return base64.b64decode(s)


def _to_int(value: object, claim_name: str) -> int:
    """Convert a claim value to int while accepting JSON number/string forms."""
    if isinstance(value, bool):
        raise PermissionError(f"Claim '{claim_name}' has invalid type.")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError as exc:
            raise PermissionError(f"Claim '{claim_name}' has invalid value.") from exc
    raise PermissionError(f"Claim '{claim_name}' has invalid type.")


def _to_str(value: object, claim_name: str) -> str:
    if not isinstance(value, str):
        raise PermissionError(f"Claim '{claim_name}' has invalid type.")
    return value


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
    noke_secret = os.getenv("NOKE_JWT_SECRET", "")
    if not noke_secret:
        raise RuntimeError(
            "NOKE_JWT_SECRET is not set. Add it to .env (local) or K8s secret (production)."
        )

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise PermissionError("Malformed token: expected 3 dot-separated parts.")

    header_b64, payload_b64, received_sig = parts

    try:
        header: dict = json.loads(_b64_decode(header_b64).decode("utf-8"))
    except Exception:
        raise PermissionError("Token header could not be decoded.")

    if str(header.get("alg", "")).upper() != "NOKE":
        raise PermissionError("Incorrect token algorithm.")

    # The Go JWT library (golang-jwt/jwt) calls Sign() → returns []byte(hex_digest),
    # then base64url-encodes those bytes as the JWT third part.
    # Verify() receives the base64url-decoded bytes and does string(signature) == hex_digest.
    # So: JWT third part = base64url( hex_digest_string_bytes )
    # We must decode received_sig from base64url to recover the raw hex string before comparing.
    try:
        received_hex = _b64_decode(received_sig).decode("utf-8")
    except Exception:
        raise PermissionError("Token signature could not be decoded.")

    expected_hex = hashlib.sha256(
        (header_b64 + "." + payload_b64 + noke_secret).encode("utf-8")
    ).hexdigest()

    if expected_hex != received_hex:
        raise PermissionError("Token signature is invalid.")

    try:
        claims: dict = json.loads(_b64_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise PermissionError("Token payload could not be decoded.")

    required_claims = [
        "company",
        "nokeUser",
        "alg",
        "exp",
        "iss",
        "tokenType",
        "sessionSalt",
        "currentSite",
    ]
    missing = [name for name in required_claims if name not in claims]
    if missing:
        raise PermissionError(f"Token is missing required claims: {', '.join(missing)}")

    if str(claims.get("alg", "")).upper() != "NOKE":
        raise PermissionError("Incorrect algorithm claim.")

    exp = _to_int(claims.get("exp"), "exp")
    if exp and exp < int(time.time()):
        raise PermissionError("Token has expired. Please refresh your portal session.")

    user_id = _to_int(claims.get("nokeUser"), "nokeUser")
    site_id = _to_int(claims.get("currentSite"), "currentSite")
    company = _to_str(claims.get("company"), "company")
    token_type = _to_str(claims.get("tokenType"), "tokenType")

    return {
        "user_id": user_id,
        "site_id": site_id,
        "company": company,
        "token_type": token_type,
    }
