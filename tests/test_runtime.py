"""Test script to invoke the NokeMCP Runtime directly."""
import boto3
import json
import sys

session = boto3.Session(profile_name='DeveloperAdmin-440124919638', region_name='us-east-2')
control = session.client('bedrock-agentcore-control')
data_client = session.client('bedrock-agentcore')

# List existing runtimes
print("=== Existing Runtimes ===")
runtimes = control.list_agent_runtimes()
for rt in runtimes.get('agentRuntimes', []):
    name = rt['agentRuntimeName']
    status = rt['status']
    arn = rt['agentRuntimeArn']
    print(f"  {name} - {status} - {arn}")

# List existing gateways
print("\n=== Existing Gateways ===")
gateways = control.list_gateways()
for gw in gateways.get('gateways', []):
    name = gw['name']
    status = gw['status']
    gw_id = gw['gatewayId']
    print(f"  {name} - {status} - {gw_id}")

# Try to invoke the NokeAgent runtime with an MCP initialize message
print("\n=== Testing Runtime Invocation ===")
target_runtime = None
for rt in runtimes.get('agentRuntimes', []):
    if 'NokeMCP' in rt['agentRuntimeName']:
        target_runtime = rt
        break

if not target_runtime:
    print("NokeMCP runtime not found. Checking NokeAgent...")
    for rt in runtimes.get('agentRuntimes', []):
        if 'NokeAgent' in rt['agentRuntimeName']:
            target_runtime = rt
            break

if not target_runtime:
    print("No suitable runtime found!")
    sys.exit(1)

print(f"Target runtime: {target_runtime['agentRuntimeName']} ({target_runtime['status']})")
print(f"ARN: {target_runtime['agentRuntimeArn']}")

# Send MCP initialize message
mcp_init = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
}

print(f"\nSending MCP initialize: {json.dumps(mcp_init)}")
try:
    response = data_client.invoke_agent_runtime(
        agentRuntimeArn=target_runtime['agentRuntimeArn'],
        qualifier='DEFAULT',
        contentType='application/json',
        accept='application/json, text/event-stream',
        mcpSessionId='test-session-001',
        mcpProtocolVersion='2024-11-05',
        payload=json.dumps(mcp_init).encode('utf-8'),
    )
    print(f"\nResponse status: {response['ResponseMetadata']['HTTPStatusCode']}")
    # The response body might be a streaming body
    if 'response' in response:
        body = response['response'].read().decode('utf-8')
        print(f"Response body: {body[:2000]}")
    elif 'body' in response:
        body = response['body'].read().decode('utf-8')
        print(f"Response body: {body[:2000]}")
    else:
        # Print all keys
        print(f"Response keys: {list(response.keys())}")
        for k, v in response.items():
            if k != 'ResponseMetadata':
                print(f"  {k}: {str(v)[:500]}")
except Exception as e:
    print(f"\nError invoking runtime: {type(e).__name__}: {e}")
