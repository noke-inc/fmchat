"""
End-to-end test: NokeAgent → NokeMCP → RDS
Usage: python test_e2e.py
"""
import boto3, json, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROFILE  = "DeveloperAdmin-440124919638"
REGION   = "us-east-2"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-2:440124919638:runtime/NokeAgent_NokeAgent-tm7hzt7fsf"
MCP_ARN   = "arn:aws:bedrock-agentcore:us-east-2:440124919638:runtime/NokeAgent_NokeMCP-1E5MbAG99J"

dc = boto3.Session(profile_name=PROFILE, region_name=REGION).client("bedrock-agentcore")


def call_mcp(method, params={}):
    r = dc.invoke_agent_runtime(
        agentRuntimeArn=MCP_ARN, qualifier="DEFAULT",
        payload=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    )
    return json.loads(r["response"].read())


def call_agent(prompt, user_id, session_id):
    r = dc.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN, qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt, "session_id": session_id, "user_id": user_id}).encode()
    )
    return json.loads(r["response"].read())


print("=" * 60)
print("STEP 1: NokeMCP tools/list")
print("=" * 60)
result = call_mcp("tools/list")
tools = result.get("result", {}).get("tools", [])
print(f"  Tools found: {[t['name'] for t in tools]}")

print()
print("=" * 60)
print("STEP 2: NokeMCP tools/call → get_units (direct DB test)")
print("=" * 60)
result = call_mcp("tools/call", {"name": "get_units", "arguments": {"user_id": 1034747, "limit": 3}})
if "error" in result:
    print(f"  ERROR: {result['error']}")
else:
    content = result.get("result", {}).get("content", [{}])
    text = content[0].get("text", "") if content else ""
    rows = json.loads(text) if text.startswith("[") else text
    if isinstance(rows, list):
        print(f"  Units returned: {len(rows)} rows")
        if rows:
            print(f"  First unit: {json.dumps(rows[0], default=str)[:200]}")
    else:
        print(f"  Response: {text[:300]}")

print()
print("=" * 60)
print("STEP 3: Full NokeAgent e2e ('How many units do I have?')")
print("=" * 60)
result = call_agent("How many units do I have?", user_id=1034747, session_id="e2e-final-001")
print(f"  Agent response: {result.get('result', result)[:400]}")

print()
print("Done.")
