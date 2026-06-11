"""
local_proxy.py — Local development proxy for the UI

Bridges the static HTML UI (which calls POST http://localhost:8000/agent/chat)
to the deployed AWS Bedrock AgentCore NokeAgent runtime via boto3 SigV4.

Usage:
    $env:AWS_PROFILE = "DeveloperAdmin-440124919638"
    python local_proxy.py

Then open: http://localhost:8000
The chat UI will be served at http://localhost:8000 and calls will be proxied
to the NokeAgent AgentCore runtime automatically.

Endpoints:
    GET  /           → serves ui/index.html
    GET  /app.js     → serves ui/app.js
    GET  /styles.css → serves ui/styles.css
    POST /agent/chat → proxies to AgentCore NokeAgent runtime
"""

import json
import os
import sys
import uuid
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import boto3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("proxy")

# ── Config ─────────────────────────────────────────────────────────────────────
PROFILE   = os.getenv("AWS_PROFILE", "DeveloperAdmin-440124919638")
REGION    = "us-east-2"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-2:440124919638:runtime/NokeAgent_NokeAgent-tm7hzt7fsf"
PORT      = 8000
UI_DIR    = Path(__file__).parent / "ui"

# ── boto3 AgentCore client ─────────────────────────────────────────────────────
try:
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    _client = session.client("bedrock-agentcore")
    log.info("AWS session: profile=%s  region=%s", PROFILE, REGION)
except Exception as e:
    log.error("Failed to create boto3 session: %s", e)
    sys.exit(1)


def call_agent(prompt: str, user_id: int = 1034747, session_id: str | None = None) -> dict:
    """Invoke NokeAgent runtime and return parsed JSON response."""
    sid = session_id or f"ui-{uuid.uuid4().hex[:8]}"
    payload = json.dumps({
        "prompt":     prompt,
        "session_id": sid,
        "user_id":    user_id,
    }).encode()

    log.info("→ AgentCore  session=%s  prompt=%r", sid, prompt[:80])
    resp = _client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN,
        qualifier="DEFAULT",
        payload=payload,
    )
    body = resp.get("response").read()
    log.info("← AgentCore  status=%s  bytes=%d", resp.get("statusCode"), len(body))
    return json.loads(body.decode()), sid


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

        try:
            result, used_sid = call_agent(
                prompt=message,
                user_id=1034747,
                session_id=session_id,
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

        response_payload = json.dumps({
            "answer":          answer,
            "conversation_id": used_sid,
            "user_id":         1034747,
            "site_id":         None,
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
    log.info("Open browser → http://localhost:%d", PORT)
    log.info("Agent ARN    → %s", AGENT_ARN)
    log.info("AWS Profile  → %s", PROFILE)
    log.info("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
