"""
app/NokeAgent/auth/noke_jwt.py

NOKE portal JWT validator used by Agent runtime when AGENT_AUTH_ENABLED=true.

Algorithm (custom — not standard HS256/RS256):
    signature = hex( SHA256( header_b64 + "." + payload_b64 + NOKE_SECRET ) )
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
    """Validate a NOKE JWT and return normalized claims used by the runtime."""
    noke_secret = os.getenv("NOKE_JWT_SECRET", "")
    if not noke_secret:
        raise RuntimeError(
            "NOKE_JWT_SECRET is not set. Configure it in AgentCore runtime environment."
        )

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise PermissionError("Malformed token: expected 3 dot-separated parts.")

    header_b64, payload_b64, received_sig = parts

    try:
        header = json.loads(_b64_decode(header_b64).decode("utf-8"))
    except Exception as exc:
        raise PermissionError("Token header could not be decoded.") from exc

    if str(header.get("alg", "")).upper() != "NOKE":
        raise PermissionError("Incorrect token algorithm.")

    try:
        received_hex = _b64_decode(received_sig).decode("utf-8")
    except Exception as exc:
        raise PermissionError("Token signature could not be decoded.") from exc

    expected_hex = hashlib.sha256(
        (header_b64 + "." + payload_b64 + noke_secret).encode("utf-8")
    ).hexdigest()
    if expected_hex != received_hex:
        raise PermissionError("Token signature is invalid.")

    try:
        claims = json.loads(_b64_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise PermissionError("Token payload could not be decoded.") from exc

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

    return {
        "user_id": _to_int(claims.get("nokeUser"), "nokeUser"),
        "site_id": _to_int(claims.get("currentSite"), "currentSite"),
        "company": _to_str(claims.get("company"), "company"),
        "token_type": _to_str(claims.get("tokenType"), "tokenType"),
    }
