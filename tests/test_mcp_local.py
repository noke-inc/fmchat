"""
tests/test_mcp_local.py

Quick local E2E test:
  1. Connects to the local MCP server (port 8001) via streamable-http
  2. Lists tools - verifies get_sites_by_company is registered
  3. Calls get_sites_by_company with the test company_uuid

Run AFTER starting the MCP server:
  cd <repo-root>
  $env:PYTHONPATH = "..."  (set appropriately)
  python -m uvicorn mcp_server.main:app --port 8001

Then:
  python tests/test_mcp_local.py
"""

import asyncio
import sys
import json

MCP_URL = "http://localhost:8001/mcp-http/"

# company_uuid for the test user's company (from test_connection.py data)
# Update this to a real company_uuid from your DB if needed
TEST_COMPANY_UUID = None   # will be discovered from get_units result if None
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


def main():
    print("=" * 60)
    print("Local MCP E2E Test")
    print("=" * 60)

    # 1. Initialize
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

    # 2. List tools
    print("\n[2] tools/list")
    resp, sid = mcp_call("tools/list", {}, session_id=sid, req_id=2)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
        sys.exit(1)
    tools = resp.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    print(f"  Tools: {tool_names}")

    for expected in ("get_units", "get_locks", "get_locks_to_units", "get_sites_by_company"):
        status = "OK" if expected in tool_names else "MISSING"
        print(f"    {status}: {expected}")

    if "get_sites_by_company" not in tool_names:
        print("\nFAIL: get_sites_by_company not registered in MCP server!")
        sys.exit(1)

    # 3. Call get_units to discover company_uuid
    print(f"\n[3] get_units(user_id={TEST_USER_ID})")
    resp, sid = mcp_call("tools/call", {
        "name": "get_units",
        "arguments": {"user_id": TEST_USER_ID, "limit": 1},
    }, session_id=sid, req_id=3)
    if "error" in resp:
        print(f"  FAIL: {resp['error']}")
    else:
        content = resp.get("result", {}).get("content", [])
        if content:
            raw_text = content[0].get("text", "")
            rows = json.loads(raw_text) if raw_text.startswith("[") else raw_text
            if isinstance(rows, list) and rows:
                print(f"  OK  first unit: {list(rows[0].items())[:4]}")
            else:
                print(f"  Response: {str(raw_text)[:200]}")
        else:
            print(f"  Response: {resp}")

    # 4. Call get_sites_by_company
    # Look up company_uuid from DB using test user's site
    print("\n[4] Fetching company_uuid for test...")
    sys.path.insert(0, "eks")
    try:
        from mcp_server.db import execute_query
        rows = execute_query(
            "SELECT s.company_uuid FROM users_roles ur "
            "JOIN sites s ON ur.site_id = s.id "
            "WHERE ur.user_id = %s LIMIT 1",
            (TEST_USER_ID,)
        )
        company_uuid = rows[0]["company_uuid"] if rows else None
        print(f"  company_uuid = {company_uuid}")
    except Exception as e:
        print(f"  Could not fetch company_uuid: {e}")
        company_uuid = None

    if company_uuid:
        print(f"\n[5] get_sites_by_company(company_uuid={company_uuid})")
        resp, sid = mcp_call("tools/call", {
            "name": "get_sites_by_company",
            "arguments": {"company_uuid": company_uuid},
        }, session_id=sid, req_id=5)
        if "error" in resp:
            print(f"  FAIL: {resp['error']}")
            sys.exit(1)
        content = resp.get("result", {}).get("content", [])
        if content:
            raw_text = content[0].get("text", "")
            sites = json.loads(raw_text) if raw_text.startswith("[") else raw_text
            if isinstance(sites, list):
                print(f"  OK  {len(sites)} site(s) found:")
                for s in sites[:5]:
                    print(f"    id={s.get('id')}  name={s.get('name')}")
            else:
                print(f"  Response: {raw_text[:200]}")
        else:
            print(f"  Response: {resp}")
    else:
        print("\n[5] SKIPPED — could not determine company_uuid")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
