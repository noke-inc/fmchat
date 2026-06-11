"""
app/NokeAgent/mcp_client/client.py

Boto3-based MCP client for NokeMCP runtime.

Replaces MultiServerMCPClient / httpx-SigV4 approach with direct
boto3 invoke_agent_runtime calls.  Each call is a stateless JSON-RPC
request to the NokeMCP container's /invocations handler.

The NokeMCP container exposes a stateless JSON-RPC API that handles:
  initialize, notifications/initialized, tools/list, tools/call
"""

import asyncio
import json
import logging
import os
from typing import Any

import boto3
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)


def _get_nokemcp_arn() -> str:
    return os.getenv("NOKEMCP_RUNTIME_ARN", "")


def _get_region() -> str:
    return os.getenv("AWS_REGION", os.getenv("BEDROCK_REGION", "us-east-2"))


def _call_nokemcp_sync(method: str, params: dict) -> dict:
    """Send a single JSON-RPC call to NokeMCP via boto3 invoke_agent_runtime."""
    arn = _get_nokemcp_arn()
    if not arn:
        raise RuntimeError("NOKEMCP_RUNTIME_ARN env var is not set")

    client = boto3.Session().client("bedrock-agentcore", region_name=_get_region())
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode()

    logger.info("NokeMCP call: method=%s arn=%s", method, arn)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier="DEFAULT",
        payload=payload,
    )

    # invoke_agent_runtime returns the response body under the "response" key
    body_stream = resp.get("response")
    body = body_stream.read() if body_stream is not None else b""

    logger.info("NokeMCP response: status=%s body_len=%d",
                resp.get("statusCode"), len(body))
    return json.loads(body.decode())


async def _call_nokemcp(method: str, params: dict) -> dict:
    """Async wrapper — runs boto3 call in thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call_nokemcp_sync, method, params)


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


def _make_langchain_tool(tool_def: dict) -> StructuredTool:
    """Convert an MCP tool definition to a LangChain StructuredTool."""
    name        = tool_def["name"]
    description = tool_def.get("description", "")
    schema      = tool_def.get("inputSchema", {})

    ArgsModel = _build_pydantic_model(name, schema)

    async def call_tool(**kwargs: Any) -> str:
        result = await _call_nokemcp("tools/call", {"name": name, "arguments": kwargs})
        # MCP result format: {"result": {"content": [{"type": "text", "text": "..."}]}}
        mcp_result = result.get("result", result)
        content = mcp_result.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", str(content))
        error = result.get("error")
        if error:
            return f"MCP error {error.get('code')}: {error.get('message')}"
        return str(mcp_result)

    return StructuredTool.from_function(
        coroutine=call_tool,
        name=name,
        description=description,
        args_schema=ArgsModel,
    )


async def get_noke_tools() -> list[StructuredTool]:
    """Fetch available tools from NokeMCP and return as LangChain StructuredTools."""
    result = await _call_nokemcp("tools/list", {})
    tools_list = result.get("result", {}).get("tools", [])
    logger.info("NokeMCP tools/list returned %d tools", len(tools_list))
    return [_make_langchain_tool(t) for t in tools_list]

