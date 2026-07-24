# app/NokeAgent/main.py
# Local FastAPI server — serves the chat UI and routes messages through agent_graph.py
# Run: python main.py   (from app/NokeAgent/ directory)
# Open: http://localhost:9000

import asyncio
import base64
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

# ─── Path injection — must match agent_graph.py ───────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MCP_DIR  = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "eks", "mcp_server"))
for _p in (_MCP_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(_THIS_DIR, ".env"), override=True)

# ─── Hardcoded JWT — update this when you get a fresh portal token ────────────
# Paste your current portal JWT here. The server extracts user_id and company
# from it, then queries users_roles to get the full authorized site list.
HARDCODED_JWT = os.getenv(
    "NOKE_UI_JWT",
    (
        "eyJhbGciOiJOT0tFIiwidHlwIjoiSldUIn0.eyJhbGciOiJOT0tFIiwiY29tcGFueSI6IjEwMDAyNDEiLCJjdXJyZW50U2l0ZSI6MjIyMzM5MSwiZGV2aWNlSWQiOiIiLCJleHAiOjE3ODQ2NjE4MzAsImlzcyI6Im5va2UuY29tIiwibm9rZVVzZXIiOjEwNTQxMzUsInNlc3Npb25TYWx0IjoiICIsInRva2VuVHlwZSI6IndlYiJ9.NTQ1ODlkNGU5NGFjODdiYTc2Y2Q5M2IzNjJiZmI3NjI5YzY5N2M1NTJiNGNmZGViNjk3ZDZlOGI4ZjIyYmVhMA"
    ),
)

# Make the same JWT available to OutboundAPIRouter via env var
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", HARDCODED_JWT)

def _decode_jwt(token: str) -> dict:
    try:
        part = token.split(".")[1]
        padded = part + "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return {}

_CLAIMS      = _decode_jwt(HARDCODED_JWT)
JWT_USER_ID  = int(_CLAIMS.get("nokeUser", 1034747))
JWT_COMPANY  = int(str(_CLAIMS.get("company", "1000245")))

# ─── Lazy imports (after path setup) ─────────────────────────────────────────
import data_retrieval_engine
from agent_graph import agent_brain_app
from langchain_core.messages import HumanMessage
from db import execute_query  # eks/mcp_server/db.py (already on sys.path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# ─── Resolve authorized sites from users_roles table (same as db_user.py) ────
def _load_user_sites(user_id: int) -> list:
    """Query users_roles to get all site IDs authorized for this JWT user."""
    try:
        rows = execute_query(
            "SELECT site_id FROM users_roles WHERE user_id = %s",
            (user_id,),
        )
        sites = [int(r["site_id"]) for r in rows if r.get("site_id") is not None]
        if sites:
            return sites
    except Exception as exc:
        print(f"⚠️  Could not load user sites from DB: {exc}", flush=True)
    # Fallback to JWT currentSite if DB query fails
    fallback = _CLAIMS.get("currentSite")
    return [int(fallback)] if fallback else []

JWT_SITES = _load_user_sites(JWT_USER_ID)
print(f"   Authorized sites for user {JWT_USER_ID}: {JWT_SITES}", flush=True)

# ─── Static UI directory ──────────────────────────────────────────────────────
UI_DIR = Path(_THIS_DIR).parent.parent / "ui"

# ─── In-memory session store ──────────────────────────────────────────────────
sessions: Dict[str, Dict[str, Any]] = {}


def _new_session(site_id: int) -> Dict[str, Any]:
    """Fresh AgentState — mirrors session_rolling_state in agent_graph.py __main__."""
    return {
        "messages":               [],
        "user_id":                JWT_USER_ID,
        "company_id":             [JWT_COMPANY],
        "site_id":                JWT_SITES,        # full authorized fence
        "active_session_company": [],
        "active_session_site":    [site_id],         # pre-select → skips disambiguation menu
        "discovered_company_ids": [],
        "discovered_site_ids":    [],
        "metadata_names_map":     {},
        "pending_user_query":     None,
        "awaiting_site_selection": False,
        "active_mutation_intent": None,
        "gathered_form_payload":  {},
    }


def _sync_session(session: Dict, output: Dict) -> None:
    """Sync graph output back into rolling session — mirrors main loop in agent_graph.py."""
    if output.get("messages"):
        session["messages"] = output["messages"]
    for key, default in [
        ("active_session_company", []),
        ("active_session_site",    []),
        ("discovered_site_ids",    []),
        ("discovered_company_ids", []),
        ("metadata_names_map",     {}),
    ]:
        session[key] = output.get(key) or default

    session["pending_user_query"]     = output.get("pending_user_query")
    session["awaiting_site_selection"] = bool(output.get("awaiting_site_selection", False))
    session["active_mutation_intent"] = output.get("active_mutation_intent")
    session["gathered_form_payload"]  = output.get("gathered_form_payload") or {}

    # Clear form state after successful dispatch
    if session["active_mutation_intent"] == "FORM_COMPLETE":
        session["active_mutation_intent"] = None
        session["gathered_form_payload"]  = {}


# ─── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="Noke Agent Local UI")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ─── Request / Response models ────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    site_id: int
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str


# ─── Static file routes ───────────────────────────────────────────────────────
@app.get("/")
def serve_index():
    return FileResponse(UI_DIR / "index.html")

@app.get("/app.js")
def serve_js():
    return FileResponse(UI_DIR / "app.js", media_type="application/javascript")

@app.get("/styles.css")
def serve_css():
    return FileResponse(UI_DIR / "styles.css", media_type="text/css")


# ─── GET /api/sites — returns site names for the JWT fence ───────────────────
@app.get("/api/sites")
def get_sites():
    try:
        ids_sql = ", ".join(f"'{s}'" for s in JWT_SITES)
        rows = data_retrieval_engine.execute_query(
            f"SELECT id, name FROM sites WHERE id IN ({ids_sql});", {}
        )
        sites = []
        for row in rows:
            if isinstance(row, dict):
                sites.append({"id": row["id"], "name": row["name"].strip()})
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                sites.append({"id": row[0], "name": str(row[1]).strip()})
        return JSONResponse({"sites": sites})
    except Exception as exc:
        return JSONResponse({"sites": [], "error": str(exc)}, status_code=500)


# ─── POST /agent/chat — main chat endpoint ────────────────────────────────────
@app.post("/agent/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    conv_id = req.conversation_id or f"ui-{uuid.uuid4().hex[:8]}"

    if conv_id not in sessions:
        sessions[conv_id] = _new_session(req.site_id)

    session = sessions[conv_id]
    session["messages"].append(HumanMessage(content=req.message))

    # Run synchronous graph invoke in thread pool (avoids blocking the event loop)
    try:
        output = await asyncio.to_thread(agent_brain_app.invoke, session)
    except Exception:
        return ChatResponse(
            answer="An error occurred processing your request. Please try again.",
            conversation_id=conv_id,
        )

    _sync_session(session, output)

    # Extract last AI message text
    answer = ""
    if output.get("messages"):
        last = output["messages"][-1]
        raw  = last.content
        if isinstance(raw, list):
            answer = " ".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in raw
            ).strip()
        else:
            answer = str(raw)

    answer = re.sub(r"<thinking>.*?</thinking>", "", answer, flags=re.DOTALL | re.IGNORECASE).strip()
    return ChatResponse(answer=answer, conversation_id=conv_id)


# ─── DELETE /api/session/{conv_id} — clear a session ─────────────────────────
@app.delete("/api/session/{conv_id}")
def clear_session(conv_id: str):
    sessions.pop(conv_id, None)
    return {"status": "cleared", "conversation_id": conv_id}


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀  Noke Agent UI  →  http://localhost:8080\n")
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
