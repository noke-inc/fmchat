# Noke FM Chat — Bedrock AgentCore + EKS MCP Server

## Architecture Overview

```
Browser / UI (ui/)
      │
      │  POST /chat  (Authorization: Bearer <NOKE_JWT>)
      ▼
API Gateway → Lambda (lambda/chat_proxy.py)
      │
      │  bedrock-agentcore:InvokeAgentRuntime  (SigV4)
      ▼
AgentCore Runtime — NokeAgent  (app/NokeAgent/)
      │  LangGraph intent-routing agent
      │  Model: Amazon Nova Micro (Bedrock)
      │
      │  MCP JSON-RPC  over streamable-http  (SigV4)
      ▼
AgentCore Gateway — NokeMCPGateway
      │  gateway.bedrock-agentcore.us-east-2.amazonaws.com
      │
      │  HTTPS streamable-http
      ▼
EKS MCP Server  (eks/mcp_server/)
      │  FastAPI + FastMCP  at  https://mcp.smartentry.noke.dev
      │
      │  SQL (PyMySQL)
      ▼
Amazon Aurora MySQL (RDS)
      noke-mysql-cluster.cluster-cmftlirsxmms.us-east-2.rds.amazonaws.com
      schema: smartentry-main
```

---

## Repository Structure

```
app/NokeAgent/          — AgentCore Runtime agent (LangGraph)
eks/
  mcp_server/           — FastMCP tool server (deployed to EKS)
  deployment/
    Dockerfile          — EKS Docker image
    ecr-push.ps1        — Build + push to ECR
    k8s/                — Kubernetes manifests
ui/                     — Static chat UI (HTML/JS/CSS)
lambda/                 — Lambda function: API Gateway → AgentCore bridge
agentcore/
  agentcore.json        — AgentCore project config (runtimes, gateways)
  cdk/                  — CDK stack for Lambda + API Gateway + IAM
local/
  local_proxy.py        — Local dev proxy (serves UI, calls AgentCore directly)
tests/                  — E2E and unit tests
```

---

## 1. Local Development

### Prerequisites

- Python 3.11+
- AWS profile `DeveloperAdmin-440124919638` configured with Bedrock + AgentCore permissions
- Access to RDS (either direct or via VPN/bastion)
- Docker Desktop (for EKS image builds)
- `uv` (for NokeAgent dependencies) — `pip install uv`

### 1a. Run the EKS MCP Server locally

The MCP server connects directly to RDS. It needs DB credentials and JWT secret.

```powershell
cd eks

# Create .env from the template
copy .env.example .env      # or create manually — see fields below

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m uvicorn mcp_server.main:app --host 0.0.0.0 --port 8000 --reload
```

**Required `.env` values** (in `eks/`):
```dotenv
DB_HOST=noke-mysql-cluster.cluster-cmftlirsxmms.us-east-2.rds.amazonaws.com
DB_PORT=3306
DB_USER=pradesh_kumar
DB_PASSWORD=<your-rds-password>
DB_SCHEMA=smartentry-main
NOKE_JWT_SECRET=<jwt-secret-from-go-backend-auth.go>
MCP_API_KEY=<optional-api-key-for-/api/query>
TEST_USER_ID=1034747
```

**Endpoints available locally:**
| Endpoint | Description |
|---|---|
| `GET  /health` | Liveness probe |
| `GET  /mcp-http/` | MCP streamable-http (AgentCore Gateway target) |
| `GET  /mcp/sse` | MCP SSE (legacy LangChain dev usage) |
| `POST /api/query` | Direct DB tool call (API-key + JWT protected) |

**Verify DB connectivity first:**
```powershell
# From repo root
cd eks && python ../tests/test_connection.py
```

**Test JWT generation:**
```powershell
cd eks && python ../tests/test_jwt.py
```

---

### 1b. Run the NokeAgent locally (agentcore dev)

The agent talks to the live AgentCore Gateway → EKS MCP by default.

```powershell
cd app/NokeAgent

# Install dependencies with uv
uv sync

# Create a local .env
copy .env.example .env      # or create manually — see fields below
```

**Required `.env` values** (in `app/NokeAgent/`):
```dotenv
BEDROCK_REGION=us-east-2
BEDROCK_MODEL_ID=us.amazon.nova-micro-v1:0
AGENT_GATEWAY_URL=https://nokeagent-nokemcpgateway-f1kx7iz7lg.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp
AGENT_GATEWAY_REGION=us-east-2
```

```powershell
# Start the AgentCore dev server (browser inspector on :8080)
$env:AWS_PROFILE = "DeveloperAdmin-440124919638"
agentcore dev

# Or without browser:
agentcore dev --no-browser
```

The dev server exposes a local endpoint you can POST to directly:
```powershell
Invoke-RestMethod -Uri "http://localhost:8080" -Method POST `
  -ContentType "application/json" `
  -Body '{"prompt":"How many units do I have?","user_id":1034747}'
```

---

### 1c. Run the full stack locally (UI + proxy)

The local proxy serves the UI and forwards `/agent/chat` calls to the live AgentCore Runtime.

```powershell
cd <repo-root>
$env:AWS_PROFILE = "DeveloperAdmin-440124919638"
python local/local_proxy.py
```

Then open **http://localhost:8000** in your browser.

> The proxy calls the deployed AgentCore Runtime directly — it does **not** require a local agent or MCP server to be running.

---

## 2. Deploy the Agent to AgentCore Runtime

The agent is deployed using the AgentCore CLI + CDK.

### Prerequisites

```powershell
npm install -g aws-cdk          # if not already installed
$env:AWS_PROFILE = "DeveloperAdmin-440124919638"
```

### Deploy

```powershell
cd agentcore/cdk
npm install

# Deploy everything (Lambda, API Gateway, IAM, AgentCore Runtime)
node node_modules/aws-cdk/bin/cdk deploy --all --require-approval never
```

This deploys:
- **NokeAgent AgentCore Runtime** (`NokeAgent_NokeAgent-*`) from `app/NokeAgent/`
- **Lambda** (`chat_proxy.py`) behind **API Gateway** for UI access
- **IAM policies** granting Lambda permission to invoke the runtime

### Re-deploy after code changes

Any change to `app/NokeAgent/` requires a redeploy:

```powershell
cd agentcore/cdk
node node_modules/aws-cdk/bin/cdk deploy --all --require-approval never
```

### Key resources after deployment

| Resource | Value |
|---|---|
| Runtime ARN | `arn:aws:bedrock-agentcore:us-east-2:440124919638:runtime/NokeAgent_NokeAgent-tm7hzt7fsf` |
| Gateway ID | `nokeagent-nokemcpgateway-f1kx7iz7lg` |
| Gateway URL | `https://nokeagent-nokemcpgateway-f1kx7iz7lg.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp` |
| API Gateway URL | `https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat` |

### Test the deployed runtime directly

```powershell
python tests/test_e2e.py
```

---

## 3. Deploy the MCP Server to EKS

The MCP server runs as a Kubernetes deployment in the `noke-mcp` namespace on the `smartentry-blue` EKS cluster.

### Prerequisites

- Docker Desktop
- `kubectl` configured (see step 1 below)
- ECR push access

### Step 1 — Configure kubectl

```powershell
$env:AWS_PROFILE = "DeveloperAdmin-440124919638"
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" eks update-kubeconfig `
    --name smartentry-blue --region us-east-2
```

### Step 2 — Build and push the Docker image

```powershell
cd eks

# Default tag is V3.0.0; pass -Tag to override
.\deployment\ecr-push.ps1 -Tag "V3.0.0"
```

This builds from `eks/` (copies `mcp_server/` only — no agent code) and pushes to:
```
440124919638.dkr.ecr.us-east-2.amazonaws.com/noke-fm-mcp-server:<tag>
```

### Step 3 — Update the image tag (if changed)

Edit [`eks/deployment/k8s/deployment.yaml`](eks/deployment/k8s/deployment.yaml):
```yaml
image: 440124919638.dkr.ecr.us-east-2.amazonaws.com/noke-fm-mcp-server:V3.0.0
```

### Step 4 — Apply Kubernetes manifests

```powershell
cd eks
kubectl apply -f deployment/k8s/namespace.yaml
kubectl apply -f deployment/k8s/service-account.yaml
kubectl apply -f deployment/k8s/secret.yaml.template    # update secrets first!
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/deployment.yaml
kubectl apply -f deployment/k8s/service.yaml
kubectl apply -f deployment/k8s/ingress.yaml
```

Or for a rolling update (manifests already applied, just changing image):
```powershell
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/deployment.yaml
kubectl rollout status deployment/noke-mcp -n noke-mcp --timeout=120s
```

### Step 5 — Verify

```powershell
kubectl get pods -n noke-mcp
Invoke-RestMethod -Uri "https://mcp.smartentry.noke.dev/health"
```

Expected health response:
```json
{ "status": "ok" }
```

### Kubernetes secrets (first-time setup only)

Before deploying for the first time, copy `secret.yaml.template` to `secret.yaml`, fill in the base64-encoded values, and apply:
```powershell
# Encode a secret value:
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("your-password"))

kubectl apply -f deployment/k8s/secret.yaml     # never commit this file
```

---

## 4. End-to-End Architecture Flow

```
1. User opens  http://localhost:8000  (local dev)
   or the deployed static UI served via a browser.

2. User types a message → JS calls:
     POST https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat
     Headers: Authorization: Bearer <NOKE_JWT>
     Body:    { "message": "How many units do I have?", "user_id": 1034747 }

3. API Gateway → Lambda (lambda/chat_proxy.py)
   • Validates the request shape
   • Calls  bedrock-agentcore:InvokeAgentRuntime  on the NokeAgent runtime
   • Returns  { answer, conversation_id, user_id, site_id }

4. AgentCore Runtime — NokeAgent  (app/NokeAgent/main.py → graph.py)
   • Receives payload: { prompt, session_id, user_id }
   • LangGraph classifies intent (units / locks / locks_to_units / schema / general)
   • Calls the matching MCP tool via the AgentCore Gateway (SigV4)

5. AgentCore Gateway — NokeMCPGateway
   • Receives a JSON-RPC tools/call request (streamable-http)
   • Routes to target:  NokeMCPEksTarget  →  https://mcp.smartentry.noke.dev/mcp-http/
   • Tool names are prefixed:  NokeMCPEksTarget___get_units  (stripped by agent)

6. EKS MCP Server  (eks/mcp_server/main.py)
   • FastMCP handles the streamable-http tool call
   • Validates user access (JWT or user_id scoping)
   • Executes SQL against RDS Aurora MySQL

7. Response bubbles back:
   RDS → EKS MCP → Gateway → AgentCore (LLM formats answer) → Lambda → API GW → UI
```

### AWS Resources

| Resource | ID / ARN |
|---|---|
| EKS cluster | `smartentry-blue` (us-east-2) |
| EKS namespace | `noke-mcp` |
| EKS ingress host | `mcp.smartentry.noke.dev` |
| ECR repository | `noke-fm-mcp-server` |
| Current EKS image | `V3.0.0` |
| AgentCore Runtime | `NokeAgent_NokeAgent-tm7hzt7fsf` |
| AgentCore Gateway | `nokeagent-nokemcpgateway-f1kx7iz7lg` |
| API Gateway URL | `https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat` |
| RDS endpoint | `noke-mysql-cluster.cluster-cmftlirsxmms.us-east-2.rds.amazonaws.com` |
| AWS Account | `440124919638` / `us-east-2` |
| AWS Profile | `DeveloperAdmin-440124919638` |

---

## Quick Reference

```powershell
# ── Local: MCP server ──────────────────────────────────────────────────────
cd eks && python -m uvicorn mcp_server.main:app --reload --port 8000

# ── Local: Agent dev server ────────────────────────────────────────────────
cd app/NokeAgent && agentcore dev

# ── Local: UI + proxy (calls live AgentCore) ──────────────────────────────
python local/local_proxy.py          # open http://localhost:8000

# ── Test: DB connectivity ──────────────────────────────────────────────────
cd eks && python ../tests/test_connection.py

# ── Test: JWT generation ───────────────────────────────────────────────────
cd eks && python ../tests/test_jwt.py

# ── Test: Full E2E ─────────────────────────────────────────────────────────
python tests/test_e2e.py

# ── Deploy: EKS MCP server ─────────────────────────────────────────────────
cd eks && .\deployment\ecr-push.ps1 -Tag "V3.0.0"
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/deployment.yaml

# ── Deploy: AgentCore Runtime ──────────────────────────────────────────────
cd agentcore/cdk && node node_modules/aws-cdk/bin/cdk deploy --all --require-approval never
```
