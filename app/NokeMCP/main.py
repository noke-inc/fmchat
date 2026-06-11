"""
app/NokeMCP/main.py

AgentCore MCP Runtime entrypoint — Noke Smart Entry MCP tools.

Deployed as an AWS Bedrock AgentCore Runtime with protocol=MCP.
AgentCore platform communicates with containers via HTTP on port 8080.
It checks health via GET /ping and sends MCP requests via POST /mcp.
The container must respond to /ping within 30s of startup.

DB credentials are injected as environment variables by AgentCore at runtime.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from tools import (
        tool_describe_table,
        tool_get_locks,
        tool_get_locks_to_units,
        tool_get_units,
    )

    logger.info("Starting Noke Smart Entry MCP server on port 8080")

    # ── Tool registry ────────────────────────────────────────────────────────
    TOOLS = [
        {
            "name": "get_units",
            "description": "Return storage units scoped to the sites assigned to this user.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "The user's numeric ID"},
                    "limit":   {"type": "integer", "description": "Max rows to return", "default": 100},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "get_locks",
            "description": "Return locks scoped to the sites assigned to this user.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "The user's numeric ID"},
                    "limit":   {"type": "integer", "description": "Max rows to return", "default": 100},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "get_locks_to_units",
            "description": "Return lock-to-unit assignments scoped to the sites assigned to this user.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "The user's numeric ID"},
                    "limit":   {"type": "integer", "description": "Max rows to return", "default": 100},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "describe_table",
            "description": "Return column metadata for the given table name.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Name of the database table"},
                },
                "required": ["table"],
            },
        },
    ]

    TOOL_FN = {
        "get_units":         lambda a: tool_get_units(user_id=a["user_id"], limit=a.get("limit", 100)),
        "get_locks":         lambda a: tool_get_locks(user_id=a["user_id"], limit=a.get("limit", 100)),
        "get_locks_to_units": lambda a: tool_get_locks_to_units(user_id=a["user_id"], limit=a.get("limit", 100)),
        "describe_table":    lambda a: tool_describe_table(a["table"]),
    }

    # ── Health check ─────────────────────────────────────────────────────────
    import time as _time

    def ping(request: Request):
        return JSONResponse({"status": "HEALTHY", "time_of_last_update": int(_time.time())})

    # ── Stateless MCP JSON-RPC handler ───────────────────────────────────────
    import json as _json

    async def invocations(request: Request):
        """Handle MCP JSON-RPC requests statlessly (no session management).

        Supports: initialize, notifications/initialized, tools/list, tools/call.
        Each AgentCore invoke_agent_runtime call is independent.
        """
        try:
            body = await request.json()
        except Exception as exc:
            logger.warning("invocations: invalid JSON body: %s", exc)
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
                status_code=200,
            )

        method  = body.get("method", "")
        req_id  = body.get("id")
        params  = body.get("params", {})
        logger.info("MCP request: method=%s id=%s", method, req_id)

        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "NokeMCP", "version": "1.0.0"},
                },
            })

        if method == "notifications/initialized":
            # Client notification — no response expected (use 204)
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}}, status_code=200)

        if method == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            })

        if method == "tools/call":
            name      = params.get("name", "")
            arguments = params.get("arguments", {})
            logger.info("Tool call: name=%s args=%s", name, arguments)
            fn = TOOL_FN.get(name)
            if fn is None:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool not found: {name}"},
                })
            try:
                result = fn(arguments)
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": _json.dumps(result)}],
                        "isError": False,
                    },
                })
            except Exception as exc:
                logger.exception("Tool %s raised: %s", name, exc)
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {exc}"}],
                        "isError": True,
                    },
                })

        # Unknown method
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    app = Starlette(
        routes=[
            Route("/ping",        ping,        methods=["GET"]),
            Route("/invocations", invocations, methods=["POST"]),
        ],
    )

    logger.info("Server ready — /ping health, /invocations for stateless MCP JSON-RPC")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
