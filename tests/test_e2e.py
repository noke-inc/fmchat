"""
End-to-end test: UI/Lambda → NokeAgent (AgentCore Runtime) → Gateway → EKS MCP → RDS

Usage (from repo root):
  python tests/test_e2e.py

Requires:
  AWS profile DeveloperAdmin-440124919638 with bedrock-agentcore:InvokeAgentRuntime permission.
"""
import boto3, json, sys, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROFILE   = "DeveloperAdmin-440124919638"
REGION    = "us-east-2"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-2:440124919638:runtime/NokeAgent_NokeAgent-tm7hzt7fsf"
API_GW_URL = "https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat"

dc = boto3.Session(profile_name=PROFILE, region_name=REGION).client("bedrock-agentcore")


def call_agent(prompt, user_id, session_id):
    r = dc.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN, qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt, "session_id": session_id, "user_id": user_id}).encode()
    )
    return json.loads(r["response"].read())


print("=" * 60)
print("STEP 1: NokeAgent direct invocation ('How many units do I have?')")
print("=" * 60)
result = call_agent("How many units do I have?", user_id=1034747, session_id="e2e-001")
print(f"  Agent response: {str(result.get('result', result))[:400]}")

print()
print("=" * 60)
print("STEP 2: API Gateway → Lambda → NokeAgent e2e")
print("=" * 60)
try:
    body = json.dumps({"message": "How many units do I have?", "user_id": 1034747}).encode()
    req = urllib.request.Request(
        API_GW_URL, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    print(f"  Status: {resp.status}")
    print(f"  Answer: {str(data.get('answer', data))[:400]}")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print("Done.")
