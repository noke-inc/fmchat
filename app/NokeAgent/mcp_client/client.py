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
from typing import Any, List
from urllib.parse import urlparse

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

_SERVICE_NAME = "bedrock-agentcore"
_LOCAL_MCP_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


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
        parsed = urlparse(self.gateway_url)
        self._is_local_url = (parsed.hostname or "").lower() in _LOCAL_MCP_HOSTS
        if self._is_local_url and parsed.path.endswith("/mcp-http"):
            # FastMCP streamable-http endpoint expects trailing slash and may 307 otherwise.
            self.gateway_url = self.gateway_url + "/"
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

        if self._is_local_url:
            request_headers = headers
        else:
            request_headers = _sign_request(
                method="POST",
                url=self.gateway_url,
                headers=headers,
                body=body,
                region=self.region,
            )

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.post(
                self.gateway_url,
                headers=request_headers,
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
        logger.info("Calling MCP tool '%s' (local_url=%s)", name, self._is_local_url)
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
    """Build a Pydantic model from JSON Schema.

    Handles anyOf/null (FastMCP wraps Optional[X] as anyOf:[X,null]) and array types.
    Uses concrete non-null defaults for optional fields to avoid anyOf:null in the
    Bedrock Converse API tool schema — which causes ModelErrorException on Nova models.
    """
    props = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    field_defs: dict[str, Any] = {}

    for field_name, field_schema in props.items():
        # Unwrap anyOf — FastMCP emits anyOf:[X, {type:null}] for Optional[X]
        schema = field_schema
        if "anyOf" in field_schema:
            non_null = [s for s in field_schema["anyOf"] if s.get("type") != "null"]
            schema = non_null[0] if non_null else {"type": "string"}

        json_type = schema.get("type", "string")
        if json_type == "integer":
            base_type: Any = int
            empty_default: Any = 0
        elif json_type == "number":
            base_type = float
            empty_default = 0.0
        elif json_type == "boolean":
            base_type = bool
            empty_default = False
        elif json_type == "array":
            items_schema = schema.get("items", {})
            items_type = items_schema.get("type", "")
            if items_type == "integer":
                base_type = List[int]
            elif items_type == "string":
                base_type = List[str]
            elif (
                items_type == "object"
                or "$ref" in items_schema
                or "anyOf" in items_schema
                or "properties" in items_schema
            ):
                # Complex items (Pydantic model ref, nested object) — use List[dict]
                # so filter dicts pass Pydantic validation and reach the MCP server intact.
                base_type = List[dict]  # type: ignore[valid-type]
            else:
                # Unknown / empty items schema — safe default
                base_type = List[str]
            empty_default = []
        else:
            base_type = str
            empty_default = ""

        description = field_schema.get("description", schema.get("description", ""))

        if field_name in required:
            field_defs[field_name] = (base_type, Field(..., description=description))
        elif isinstance(empty_default, list):
            field_defs[field_name] = (base_type, Field(default_factory=list, description=description))
        else:
            default_val = field_schema.get("default", empty_default)
            field_defs[field_name] = (base_type, Field(default=default_val, description=description))

    return create_model(f"{name}Args", **field_defs)


def _make_langchain_tool(tool_def: dict, gateway_client: GatewayMCPClient) -> StructuredTool:
    """Convert an MCP tool definition to a LangChain StructuredTool backed by the Gateway."""
    name        = tool_def["name"]
    description = tool_def.get("description", "")
    schema      = tool_def.get("inputSchema", {})
    ArgsModel   = _build_pydantic_model(name, schema)

    async def call_tool(**kwargs: Any) -> str:
        # Serialize nested Pydantic model instances (e.g. FilterCondition) to plain dicts
        # so json.dumps inside _call() can handle them.
        serialized: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, list):
                serialized[k] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in v
                ]
            elif hasattr(v, "model_dump"):
                serialized[k] = v.model_dump()
            else:
                serialized[k] = v
        return await gateway_client.call_tool(name, serialized)

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

