"""
tests/test_mcp_local.py

Quick local E2E test for the generic MCP tools (aggregate_query, search_records).
  1. Connects to the local MCP server (port 8001) via streamable-http
  2. Lists tools — verifies aggregate_query and search_records are registered
  3. Calls aggregate_query(entity="unit", aggregation="count")
  4. Calls aggregate_query(entity="site", aggregation="count")
  5. Calls search_records(entity="site", columns=["name"], limit=10)

Run AFTER starting the MCP server:
  cd <repo-root>/eks
  python -m uvicorn mcp_server.main:app --port 8001

Then:
  python tests/test_mcp_local.py
"""

import asyncio
import sys
import json

MCP_URL = "http://localhost:8001/mcp-http/"

TEST_USER_ID = 1034887     # from .env

import urllib.request
import urllib.error


def mcp_call(method: str, params: dict, session_id: str | None = None, req_id: int = 1) -> tuple[dict, str]:
    body = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept":        "application/json, text/event-stream",
    }
    if session_id:
        headers["mcp-session-id"] = session_id

    req = urllib.request.Request(MCP_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            new_sid = r.headers.get("mcp-session-id", session_id)
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        new_sid = session_id
        print(f"  HTTP {e.code}: {raw[:200]}")

    if raw.strip().startswith("{"):
        return json.loads(raw), new_sid
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:]), new_sid
    return {"raw": raw}, new_sid


def parse_tool_result(resp: dict) -> list | dict | str:
    """Extract and JSON-parse the first content item from a tools/call response."""
    content = resp.get("result", {}).get("content", [])
    if not content:
        return resp
    raw_text = content[0].get("text", "")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text


def main():
    print("=" * 60)
    print("Local MCP E2E Test — generic tools")
    print("=" * 60)

    # ── 1. Initialize ──────────────────────────────────────────────────────────
    print("\n[1] initialize")
    resp, sid = mcp_call("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    })
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    server_info = resp.get("result", {}).get("serverInfo", {})
    print(f"  OK  server={server_info}  session={sid}")

    # ── 2. List tools ──────────────────────────────────────────────────────────
    print("\n[2] tools/list")
    resp, sid = mcp_call("tools/list", {}, session_id=sid, req_id=2)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    tools = resp.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    print(f"  Registered tools: {tool_names}")

    failed = False
    for expected in ("aggregate_query", "search_records"):
        if expected in tool_names:
            print(f"    OK:      {expected}")
        else:
            print(f"    MISSING: {expected}")
            failed = True
    if failed:
        print("\nFAIL: required tools not registered in MCP server")
        sys.exit(1)

    # ── 3. aggregate_query — unit count ───────────────────────────────────────
    print(f"\n[3] aggregate_query(entity='unit', aggregation='count', user_id={TEST_USER_ID})")
    resp, sid = mcp_call("tools/call", {
        "name": "aggregate_query",
        "arguments": {
            "user_id":      TEST_USER_ID,
            "entity":       "unit",
            "aggregation":  "count",
        },
    }, session_id=sid, req_id=3)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    result = parse_tool_result(resp)
    if isinstance(result, dict) and "error" in result:
        print(f"  FAIL (tool error): {result['error']}")
        sys.exit(1)
    rows = result.get("results", []) if isinstance(result, dict) else []
    count = rows[0].get("count") if rows else None
    corrections = result.get("corrections", []) if isinstance(result, dict) else []
    print(f"  OK  unit count={count}  corrections={corrections}")

    # ── 4. aggregate_query — site count ───────────────────────────────────────
    print(f"\n[4] aggregate_query(entity='site', aggregation='count', user_id={TEST_USER_ID})")
    resp, sid = mcp_call("tools/call", {
        "name": "aggregate_query",
        "arguments": {
            "user_id":      TEST_USER_ID,
            "entity":       "site",
            "aggregation":  "count",
        },
    }, session_id=sid, req_id=4)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    result = parse_tool_result(resp)
    if isinstance(result, dict) and "error" in result:
        print(f"  FAIL (tool error): {result['error']}")
        sys.exit(1)
    rows = result.get("results", []) if isinstance(result, dict) else []
    site_count = rows[0].get("count") if rows else None
    print(f"  OK  site count={site_count}")

    # ── 5. search_records — list site names ───────────────────────────────────
    print(f"\n[5] search_records(entity='site', columns=['name'], limit=10, user_id={TEST_USER_ID})")
    resp, sid = mcp_call("tools/call", {
        "name": "search_records",
        "arguments": {
            "user_id":  TEST_USER_ID,
            "entity":   "site",
            "columns":  ["name"],
            "limit":    10,
        },
    }, session_id=sid, req_id=5)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    result = parse_tool_result(resp)
    if isinstance(result, dict) and "error" in result:
        print(f"  FAIL (tool error): {result['error']}")
        sys.exit(1)
    rows = result.get("results", []) if isinstance(result, dict) else []
    print(f"  OK  {len(rows)} site(s) returned:")
    for s in rows[:10]:
        print(f"    name={s.get('name')}")

    # ── 6. search_records — list units with rental_state ──────────────────────
    print(f"\n[6] search_records(entity='unit', columns=['name','rental_state'], limit=5)")
    resp, sid = mcp_call("tools/call", {
        "name": "search_records",
        "arguments": {
            "user_id":  TEST_USER_ID,
            "entity":   "unit",
            "columns":  ["name", "rental_state"],
            "limit":    5,
        },
    }, session_id=sid, req_id=6)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    result = parse_tool_result(resp)
    if isinstance(result, dict) and "error" in result:
        print(f"  FAIL (tool error): {result['error']}")
        sys.exit(1)
    rows = result.get("results", []) if isinstance(result, dict) else []
    print(f"  OK  {len(rows)} unit(s) returned:")
    for u in rows:
        print(f"    name={u.get('name')}  rental_state={u.get('rental_state')}")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()

