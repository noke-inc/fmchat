"""
local_proxy.py — Local development proxy for the UI

Two modes — selected automatically based on LOCAL_AGENT_URL env var:

  LOCAL mode  (agentcore dev server):
      $env:LOCAL_AGENT_URL = "http://localhost:8080/invocations"
      python local_proxy.py
      → POSTs directly to the local agentcore dev server.
      → No AWS credentials needed for the agent call itself.

  DEPLOYED mode  (AWS AgentCore Runtime via boto3 SigV4):
      $env:AWS_PROFILE = "DeveloperAdmin-440124919638"
      python local_proxy.py
      → Calls the deployed NokeAgent AgentCore runtime.

In both modes, open http://localhost:8000 in your browser.

Endpoints:
    GET  /           → serves ui/index.html
    GET  /app.js     → serves ui/app.js
    GET  /styles.css → serves ui/styles.css
    POST /agent/chat → proxies to agent (local dev server or deployed runtime)
"""

import base64
import json
import os
import sys
import uuid
import logging
import re
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import boto3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("proxy")

# Test user override for local proxy runs.
# If LOCAL_TEST_USER_ID is set, it takes precedence over UI/JWT user_id in both
# LOCAL and DEPLOYED proxy modes so one place controls test identity.
LOCAL_TEST_USER_ID = int(os.getenv("LOCAL_TEST_USER_ID", "1032127"))
FORCE_TEST_USER_ID = "LOCAL_TEST_USER_ID" in os.environ


def _strip_thinking(text: object) -> str:
    """Remove model reasoning tags before returning text to the UI."""
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", str(text), flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def _decode_jwt_claims(token: str) -> dict:
    """Decode a JWT payload without signature verification (for extracting context claims)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return {}


def _extract_context(req_body: dict, authorization: str) -> tuple[int, int | None, str | None]:
    """Return (user_id, site_id, company_uuid) from request body, falling back to JWT claims."""
    # 1. Decode JWT for fallback values
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    claims = _decode_jwt_claims(token) if token else {}

    jwt_user_id     = claims.get("nokeUser")
    jwt_site_id     = claims.get("currentSite")
    jwt_company     = str(claims.get("company", "")) or None

    # 2. If LOCAL_TEST_USER_ID is explicitly provided, force it in both modes.
    if FORCE_TEST_USER_ID:
        user_id = LOCAL_TEST_USER_ID
    # 3. Otherwise, keep previous behavior.
    elif LOCAL_AGENT_URL:
        user_id = LOCAL_TEST_USER_ID
    else:
        user_id = int(req_body.get("user_id") or jwt_user_id or LOCAL_TEST_USER_ID)
    site_id_raw = req_body.get("site_id") or jwt_site_id
    site_id     = int(site_id_raw) if site_id_raw is not None else None
    company_uuid = str(req_body.get("company_uuid") or jwt_company or "")
    company_uuid = company_uuid or None

    return user_id, site_id, company_uuid

# ── Config ─────────────────────────────────────────────────────────────────────
PROFILE         = os.getenv("AWS_PROFILE", "DeveloperAdmin-440124919638")
REGION          = "us-east-2"
AGENT_ARN       = "arn:aws:bedrock-agentcore:us-east-2:440124919638:runtime/NokeAgent_NokeAgent-tm7hzt7fsf"
LOCAL_AGENT_URL = os.getenv("LOCAL_AGENT_URL", "").strip()   # e.g. http://localhost:8080/invocations
# Default to 9000 so it does not conflict with local MCP on 8000.
PORT            = int(os.getenv("LOCAL_PROXY_PORT", "9000"))
UI_DIR          = Path(__file__).parent.parent / "ui"

# ── boto3 client — only initialised when NOT in local mode ────────────────────
_client = None
if not LOCAL_AGENT_URL:
    try:
        session = boto3.Session(profile_name=PROFILE, region_name=REGION)
        _client = session.client("bedrock-agentcore")
        log.info("DEPLOYED mode — AWS session: profile=%s  region=%s", PROFILE, REGION)
    except Exception as e:
        log.error("Failed to create boto3 session: %s", e)
        sys.exit(1)
else:
    log.info("LOCAL mode — forwarding to agentcore dev server: %s", LOCAL_AGENT_URL)


def call_agent(
    prompt: str,
    user_id: int = LOCAL_TEST_USER_ID,
    site_id: int | None = None,
    company_uuid: str | None = None,
    session_id: str | None = None,
    authorization: str = "",
) -> tuple[dict, str]:
    """Call the agent and return (parsed_response, session_id)."""
    sid = session_id or f"ui-{uuid.uuid4().hex[:8]}"

    agent_payload: dict = {
        "prompt":       prompt,
        "session_id":   sid,
        "user_id":      user_id,
        "site_id":      site_id,
        "company_uuid": company_uuid,
    }
    # Forward the JWT so AGENT_AUTH_ENABLED=true works locally too.
    if authorization:
        agent_payload["authorization"] = authorization

    if LOCAL_AGENT_URL:
        # ── Local agentcore dev server ─────────────────────────────────────────
        body = json.dumps(agent_payload).encode()
        req = urllib.request.Request(
            LOCAL_AGENT_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        log.info("→ local dev  session=%s  prompt=%r", sid, prompt[:80])
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read()
            log.error("← local dev  HTTP %s: %s", e.code, raw[:200])
        log.info("← local dev  bytes=%d", len(raw))
        return json.loads(raw.decode()), sid

    else:
        # ── Deployed AgentCore Runtime (SigV4 via boto3) ──────────────────────
        body = json.dumps(agent_payload).encode()
        log.info("→ AgentCore  session=%s  prompt=%r", sid, prompt[:80])
        resp = _client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            qualifier="DEFAULT",
            payload=body,
        )
        raw = resp.get("response").read()
        log.info("← AgentCore  status=%s  bytes=%d", resp.get("statusCode"), len(raw))
        return json.loads(raw.decode()), sid


MIME = {
    ".html": "text/html",
    ".js":   "application/javascript",
    ".css":  "text/css",
}


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("HTTP  " + fmt, *args)

    # ── Static file serving ────────────────────────────────────────────────────
    def _serve_file(self, rel_path: str):
        full = UI_DIR / rel_path
        if not full.exists():
            self.send_error(404, f"Not found: {rel_path}")
            return
        ext  = full.suffix
        mime = MIME.get(ext, "application/octet-stream")
        data = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        # Allow browser to load local files without CORS issues
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            self._serve_file("index.html")
        elif path == "/app.js":
            self._serve_file("app.js")
        elif path == "/styles.css":
            self._serve_file("styles.css")
        else:
            self.send_error(404)

    # ── CORS preflight ─────────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ── POST /agent/chat ───────────────────────────────────────────────────────
    def do_POST(self):
        if self.path.split("?")[0] != "/agent/chat":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._json_error(400, "Invalid JSON body")
            return

        message = req.get("message", "").strip()
        if not message:
            self._json_error(400, "'message' field is required")
            return

        # Extract conversation_id to reuse as session_id for memory continuity
        session_id = req.get("conversation_id") or None

        # Forward Authorization header so AGENT_AUTH_ENABLED=true is testable locally
        authorization = (
            self.headers.get("Authorization")
            or self.headers.get("authorization")
            or ""
        )

        user_id, site_id, company_uuid = _extract_context(req, authorization)
        log.info(
            "context  user_id=%s  site_id=%s  company_uuid=%s",
            user_id, site_id, company_uuid,
        )

        try:
            result, used_sid = call_agent(
                prompt=message,
                user_id=user_id,
                site_id=site_id,
                company_uuid=company_uuid,
                session_id=session_id,
                authorization=authorization,
            )
        except Exception as e:
            log.exception("AgentCore call failed: %s", e)
            self._json_error(500, f"AgentCore error: {e}")
            return
        # NokeAgent returns {"answer": "...", ...} or {"result": "..."} or a raw string
        answer = (
            result.get("answer")
            or result.get("result")
            or result.get("response")
            or str(result)
        )
        answer = _strip_thinking(answer)

        response_payload = json.dumps({
            "answer":          answer,
            "conversation_id": used_sid,
            "user_id":         user_id,
            "site_id":         site_id,
            "company_uuid":    company_uuid,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_payload)

    def _json_error(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), ProxyHandler)
    log.info("Proxy listening on http://localhost:%d", PORT)
    log.info("Open browser    → http://localhost:%d", PORT)
    if LOCAL_AGENT_URL:
        log.info("Agent target    → LOCAL  %s", LOCAL_AGENT_URL)
    else:
        log.info("Agent target    → DEPLOYED  %s", AGENT_ARN)
        log.info("AWS Profile     → %s", PROFILE)
    log.info("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
