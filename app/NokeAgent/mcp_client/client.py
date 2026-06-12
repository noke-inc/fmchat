"""
app/NokeAgent/mcp_client/client.py

SigV4-signed MCP client for AgentCore Gateway.

Connects to the NokeAgent-NokeMCPGateway via streamable-http, signs each
request with SigV4 (service=bedrock-agentcore), and returns LangChain
StructuredTools backed by Gateway tool calls.

On AgentCore Runtime, credentials come from the Runtime execution role (IAM).
"""

import json
import logging
from typing import Any

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

_SERVICE_NAME = "bedrock-agentcore"


def _get_credentials():
    """Get AWS credentials from the default chain (Runtime execution role on AgentCore)."""
    session = BotocoreSession()
    return session.get_credentials().get_frozen_credentials()


def _sign_request(method: str, url: str, headers: dict, body: bytes, region: str) -> dict:
    """Sign an HTTP request with SigV4 for bedrock-agentcore service."""
    credentials = _get_credentials()
    request = AWSRequest(method=method, url=url, headers=headers, data=body)
    SigV4Auth(credentials, _SERVICE_NAME, region).add_auth(request)
    return dict(request.headers)


class GatewayMCPClient:
    """Stateful MCP client that communicates with AgentCore Gateway via streamable-http."""

    def __init__(self, gateway_url: str, region: str = "us-east-2"):
        self.gateway_url = gateway_url.rstrip("/")
        self.region = region
        self._session_id: str | None = None

    async def _call(self, method: str, params: dict, req_id: int = 1) -> dict:
        """Send a JSON-RPC MCP request to the Gateway with SigV4 signing."""
        body_dict = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        body = json.dumps(body_dict).encode()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id

        signed_headers = _sign_request(
            method="POST",
            url=self.gateway_url,
            headers=headers,
            body=body,
            region=self.region,
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.gateway_url,
                headers=signed_headers,
                content=body,
            )
            resp.raise_for_status()

        if "mcp-session-id" in resp.headers:
            self._session_id = resp.headers["mcp-session-id"]

        content = resp.text
        if content.startswith("event:") or content.startswith("data:"):
            for line in content.splitlines():
                if line.startswith("data: "):
                    return json.loads(line[6:])
            raise ValueError(f"No data line in SSE response: {content[:200]}")
        return json.loads(content)

    async def initialize(self) -> dict:
        result = await self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "noke-agentcore-agent", "version": "1.0"},
        }, req_id=1)
        logger.info("Gateway MCP initialized: %s", result.get("result", {}).get("serverInfo"))
        return result

    async def list_tools(self) -> list[dict]:
        result = await self._call("tools/list", {}, req_id=2)
        tools = result.get("result", {}).get("tools", [])
        logger.info("Gateway returned %d tools", len(tools))
        return tools

    async def call_tool(self, name: str, arguments: dict) -> Any:
        result = await self._call("tools/call", {
            "name": name,
            "arguments": arguments,
        }, req_id=3)
        mcp_result = result.get("result", result)
        content = mcp_result.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", str(content))
        error = result.get("error")
        if error:
            return f"MCP error {error.get('code')}: {error.get('message')}"
        return str(mcp_result)


def _build_pydantic_model(name: str, input_schema: dict) -> type[BaseModel]:
    """Build a Pydantic model class from a JSON Schema object."""
    props = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    field_defs: dict[str, Any] = {}
    for field_name, field_schema in props.items():
        py_type: Any = str
        json_type = field_schema.get("type", "string")
        if json_type == "integer":
            py_type = int
        elif json_type == "number":
            py_type = float
        elif json_type == "boolean":
            py_type = bool

        description = field_schema.get("description", "")
        default = field_schema.get("default", ...)
        if field_name not in required:
            default = field_schema.get("default", None)

        field_defs[field_name] = (py_type, Field(default=default, description=description))

    return create_model(f"{name}Args", **field_defs)


def _make_langchain_tool(tool_def: dict, gateway_client: GatewayMCPClient) -> StructuredTool:
    """Convert an MCP tool definition to a LangChain StructuredTool backed by the Gateway."""
    name        = tool_def["name"]
    description = tool_def.get("description", "")
    schema      = tool_def.get("inputSchema", {})
    ArgsModel   = _build_pydantic_model(name, schema)

    async def call_tool(**kwargs: Any) -> str:
        return await gateway_client.call_tool(name, kwargs)

    return StructuredTool.from_function(
        coroutine=call_tool,
        name=name,
        description=description,
        args_schema=ArgsModel,
    )


async def get_noke_tools(gateway_url: str, region: str = "us-east-2") -> list[StructuredTool]:
    """Connect to AgentCore Gateway, initialize MCP session, and return LangChain tools."""
    client = GatewayMCPClient(gateway_url, region)
    await client.initialize()
    tool_defs = await client.list_tools()
    return [_make_langchain_tool(t, client) for t in tool_defs]

