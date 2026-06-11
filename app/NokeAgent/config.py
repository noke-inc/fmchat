"""
app/NokeAgent/config.py

Environment variable configuration for the AgentCore-deployed agent.
Reads from environment (AgentCore injects these at runtime) with local .env fallback.
"""
import os
from dotenv import load_dotenv

load_dotenv()   # no-op in production; loads .env for local dev

# ── Bedrock ───────────────────────────────────────────────────────────────────
BEDROCK_REGION:   str = os.getenv("BEDROCK_REGION",   "us-east-2")
BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")

# ── MCP server URL ────────────────────────────────────────────────────────────
# For direct AgentCore runtime-to-runtime calls:
#   AGENT_MCP_URL = https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime-id}/invocations?qualifier=DEFAULT
# AGENT_MCP_AUTH_TYPE must be AWS_IAM so SigV4 signing is applied.
_nokemcp_runtime_arn: str = os.getenv("NOKEMCP_RUNTIME_ARN", "")
_aws_region_for_url: str = os.getenv("AWS_REGION", os.getenv("BEDROCK_REGION", "us-east-2"))

def _build_runtime_url(arn: str, region: str) -> str:
    """Build the direct HTTP invoke URL for an AgentCore runtime."""
    from urllib.parse import quote
    encoded = quote(arn, safe="")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"

_default_mcp_url = (
    _build_runtime_url(_nokemcp_runtime_arn, _aws_region_for_url)
    if _nokemcp_runtime_arn
    else "https://mcp.smartentry.noke.dev/mcp/sse"
)
AGENT_MCP_URL: str = os.getenv("AGENT_MCP_URL", _default_mcp_url)

# ── MCP inbound auth type (AWS_IAM | CUSTOM_JWT | NONE) ──────────────────────
# When calling AgentCore runtime directly, must be AWS_IAM for SigV4 signing.
AGENT_MCP_AUTH_TYPE: str = os.getenv("AGENT_MCP_AUTH_TYPE",
    os.getenv("AGENTCORE_GATEWAY_NOKEMCPGATEWAY_AUTH_TYPE", "NONE"))

# ── AWS region for SigV4 signing (used when AGENT_MCP_AUTH_TYPE == "AWS_IAM") ─
AWS_REGION: str = os.getenv("AWS_REGION", BEDROCK_REGION)

# ── MCP API key (sent as X-MCP-Api-Key header when set, legacy auth) ─────────
MCP_API_KEY: str = os.getenv("MCP_API_KEY", "")
