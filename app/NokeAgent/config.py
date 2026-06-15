"""
app/NokeAgent/config.py

Environment variable configuration for the AgentCore-deployed agent.
Reads from environment (AgentCore injects these at runtime) with local .env fallback.
"""
import os
from dotenv import load_dotenv

load_dotenv()   # no-op in production; loads .env for local dev

# Bedrock
BEDROCK_REGION:   str = os.getenv("BEDROCK_REGION",   "us-east-2")
BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")

# AgentCore Gateway
# Agent calls tools via the AgentCore Gateway (SigV4-signed streamable-http).
# The Gateway forwards requests to the EKS MCP target.
AGENT_GATEWAY_URL: str = os.getenv(
    "AGENT_GATEWAY_URL",
    "https://nokeagent-nokemcpgateway-f1kx7iz7lg.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp",
)
AGENT_GATEWAY_REGION: str = os.getenv("AGENT_GATEWAY_REGION", "us-east-2")

# Agent auth
# When true, the runtime requires a valid NOKE JWT token in the request payload.
AGENT_AUTH_ENABLED: bool = os.getenv("AGENT_AUTH_ENABLED", "false").lower() == "true"