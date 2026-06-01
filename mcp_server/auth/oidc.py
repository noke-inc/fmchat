"""
mcp_server/auth/oidc.py

OIDC Identity Provider endpoints.

This server acts as an OIDC provider so it can be registered as an
AWS IAM Identity Provider and used as the identity source for an
Amazon Q Business application.

Endpoints:
  GET /.well-known/openid-configuration  — OIDC discovery document
  GET /.well-known/jwks.json             — JSON Web Key Set (public keys)

No RS256 tokens are issued by this server — real auth uses NOKE JWT.
The static JWK satisfies the AWS requirement that a JWKS endpoint exist.
"""

import os

from fastapi import APIRouter

router = APIRouter()

MCP_BASE_URL = os.getenv("MCP_BASE_URL", "https://mcp.smartentry.noke.dev")

# Static RSA 2048 public key JWK (RFC 7517 Appendix B test key).
# Satisfies the JWKS requirement for OIDC provider registration.
_STATIC_JWKS = {
    "keys": [{
        "kty": "RSA",
        "use": "sig",
        "kid": "noke-mcp-key-1",
        "alg": "RS256",
        "n":   "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
        "e":   "AQAB",
    }]
}


@router.get("/.well-known/openid-configuration")
def oidc_discovery():
    """OIDC discovery document — required for AWS IAM Identity Provider creation."""
    return {
        "issuer":                                MCP_BASE_URL,
        "authorization_endpoint":                MCP_BASE_URL + "/mcp/oauth/authorize",
        "token_endpoint":                        MCP_BASE_URL + "/mcp/oauth/token",
        "jwks_uri":                              MCP_BASE_URL + "/.well-known/jwks.json",
        "response_types_supported":              ["code"],
        "subject_types_supported":               ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported":                      ["openid"],
        "grant_types_supported":                 ["authorization_code"],
    }


@router.get("/.well-known/jwks.json")
def jwks():
    """JSON Web Key Set — fetched by AWS to validate the OIDC provider."""
    return _STATIC_JWKS
