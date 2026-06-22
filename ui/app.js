// Chat endpoint config
const AGENT_CHAT_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? `${window.location.origin}/agent/chat`
    : "https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat";

// Local MCP server (used to fetch real site list)
const LOCAL_MCP_URL = "http://localhost:8000/mcp-http/";

// Hardcoded NOKE JWT for testing — replace with a fresh portal token if expired.
const HARDCODED_NOKE_JWT = "eyJhbGciOiJOT0tFIiwidHlwIjoiSldUIn0.eyJhbGciOiJOT0tFIiwiY29tcGFueSI6IjEwMDAyMzMiLCJjdXJyZW50U2l0ZSI6MjIyMzM2MiwiZGV2aWNlSWQiOiIiLCJleHAiOjE3ODA2MDk0NjEsImlzcyI6Im5va2UuY29tIiwibm9rZVVzZXIiOjEwMzQ3NDcsInNlc3Npb25TYWx0IjoiICIsInRva2VuVHlwZSI6IndlYiJ9.MTUxOTI3NGNiNzYxYjMzZDhlYjM3Y2EzYWU4ZWZkN2I3NTViY2NjMDk0ZjM4OWViZmZmYWUwZDBlYjVhMGMxOA";

document.addEventListener("DOMContentLoaded", () => {
  const launcher   = document.getElementById("chat-launcher");
  const panel      = document.getElementById("chat-panel");
  const closeBtn   = document.getElementById("chat-close");
  const form       = document.getElementById("chat-form");
  const input      = document.getElementById("chat-input");
  const log        = document.getElementById("chat-log");
  const siteSelect = document.getElementById("site-select");

  let conversationId = null;
  let selectedSiteId = null;

  // ── JWT decode ──────────────────────────────────────────────────────────────
  function decodeJwtPayload(token) {
    try {
      const parts = token.split(".");
      if (parts.length !== 3) return null;
      const pad = parts[1] + "=".repeat((4 - parts[1].length % 4) % 4);
      return JSON.parse(atob(pad.replace(/-/g, "+").replace(/_/g, "/")));
    } catch { return null; }
  }

  const JWT_CLAIMS   = decodeJwtPayload(HARDCODED_NOKE_JWT) || {};
  const JWT_USER_ID  = JWT_CLAIMS.nokeUser   || null;
  const JWT_COMPANY  = JWT_CLAIMS.company    || null;   // company_uuid
  const JWT_SITE_ID  = JWT_CLAIMS.currentSite || null;

  // ── Context bar (shows what will be sent to the agent) ─────────────────────
  function renderContextBar() {
    let bar = document.getElementById("context-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "context-bar";
      bar.style.cssText =
        "font-size:11px;color:#666;padding:4px 12px;background:#f5f5f5;" +
        "border-bottom:1px solid #ddd;display:flex;gap:16px;flex-wrap:wrap;";
      panel.querySelector(".chat-header").insertAdjacentElement("afterend", bar);
    }
    const siteId = selectedSiteId || JWT_SITE_ID || "—";
    bar.innerHTML =
      `<span>👤 user_id: <b>${JWT_USER_ID || "—"}</b></span>` +
      `<span>🏢 company: <b>${JWT_COMPANY || "—"}</b></span>` +
      `<span>📍 site_id: <b>${siteId}</b></span>`;
  }

  // ── MCP tool call helper ────────────────────────────────────────────────────
  let _mcpSessionId = null;

  async function mcpCall(method, params, reqId = 1) {
    const body = JSON.stringify({ jsonrpc: "2.0", id: reqId, method, params });
    const headers = { "Content-Type": "application/json", "Accept": "application/json, text/event-stream" };
    if (_mcpSessionId) headers["mcp-session-id"] = _mcpSessionId;
    const res = await fetch(LOCAL_MCP_URL, { method: "POST", headers, body });
    const sid = res.headers.get("mcp-session-id");
    if (sid) _mcpSessionId = sid;
    const text = await res.text();
    if (text.trim().startsWith("{")) return JSON.parse(text);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) return JSON.parse(line.slice(6));
    }
    return {};
  }

  async function fetchSitesFromMCP() {
    if (!JWT_USER_ID) return null;
    try {
      // Initialize MCP session
      await mcpCall("initialize", {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "noke-ui", version: "1" },
      }, 1);
      // Call search_records for the site entity scoped to this user
      const resp = await mcpCall("tools/call", {
        name: "search_records",
        arguments: { user_id: JWT_USER_ID, entity: "site", columns: ["id", "name"], limit: 50 },
      }, 2);
      const content = resp?.result?.content || [];
      if (content.length) {
        const parsed = JSON.parse(content[0].text || "{}");
        const results = parsed.results || [];
        return results.map((s) => ({ id: s.id, name: s.name }));
      }
    } catch (e) {
      console.warn("Could not fetch sites from MCP:", e.message);
    }
    return null;   // null = MCP unavailable, fall back to mock
  }

  // ── Site selector ───────────────────────────────────────────────────────────
  const FALLBACK_SITES = [
    { id: 2223362, name: "Sugar Hill 1 (fallback)" },
    { id: 2223395, name: "Sugar Hill 2 (fallback)" },
  ];

  async function initializeSiteSelector() {
    if (!siteSelect) return;

    siteSelect.innerHTML = '<option value="">Loading sites…</option>';
    siteSelect.disabled  = true;

    let sites = null;
    if (JWT_USER_ID) {
      sites = await fetchSitesFromMCP();
    }
    if (!sites) {
      console.warn("MCP site fetch failed — using fallback list");
      sites = FALLBACK_SITES;
    }

    siteSelect.innerHTML = '<option value="">-- Select a site --</option>';
    sites.forEach((s) => {
      const opt = document.createElement("option");
      opt.value       = s.id;
      opt.textContent = s.name;
      siteSelect.appendChild(opt);
    });
    siteSelect.disabled = false;

    // Restore last selection or pre-select JWT site
    const saved = localStorage.getItem("noke_selected_site_id");
    const preselectId = saved || String(JWT_SITE_ID || "");
    if (preselectId && sites.some((s) => String(s.id) === preselectId)) {
      siteSelect.value = preselectId;
      selectedSiteId   = parseInt(preselectId);
    }
    renderContextBar();
  }

  if (siteSelect) {
    siteSelect.addEventListener("change", (e) => {
      selectedSiteId = e.target.value ? parseInt(e.target.value) : null;
      if (selectedSiteId) localStorage.setItem("noke_selected_site_id", String(selectedSiteId));
      renderContextBar();
    });
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  function stripThinking(text) {
    return text ? String(text).replace(/<thinking>[\s\S]*?<\/thinking>/gi, "").trim() : text;
  }

  function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function appendMeta(text) {
    const div = document.createElement("div");
    div.className = "msg meta";
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  // ── Send message ─────────────────────────────────────────────────────────────
  async function sendMessage(message) {
    const headers = {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${HARDCODED_NOKE_JWT}`,
    };

    const payload = {
      message,
      user_id:      JWT_USER_ID,
      company_uuid: JWT_COMPANY,
      site_id:      selectedSiteId || JWT_SITE_ID,
    };
    if (conversationId) payload.conversation_id = conversationId;

    const res = await fetch(AGENT_CHAT_URL, { method: "POST", headers, body: JSON.stringify(payload) });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body}`);
    }
    const data = await res.json();
    conversationId = data.conversation_id || conversationId;
    return data;
  }

  // ── Event listeners ──────────────────────────────────────────────────────────
  launcher.addEventListener("click", () => {
    panel.classList.remove("hidden");
    initializeSiteSelector();
    if (!log.children.length) {
      appendMeta("Connected to MCP test endpoint");
      appendMessage("ai", "Welcome. Select a site above and ask about units, locks, or other Smart Entry data.");
    }
    input.focus();
  });

  closeBtn.addEventListener("click", () => panel.classList.add("hidden"));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    if (!selectedSiteId && !JWT_SITE_ID) {
      appendMessage("meta", "Please select a site from the dropdown above before sending a message.");
      return;
    }

    appendMessage("user", message);
    input.value = "";
    try {
      appendMeta("Thinking…");
      const result = await sendMessage(message);
      const reply = stripThinking(result.answer || result.result || "(No answer returned)");
      const last = log.lastElementChild;
      if (last && last.classList.contains("meta") && last.textContent === "Thinking…") last.remove();
      appendMessage("ai", reply);
    } catch (err) {
      const last = log.lastElementChild;
      if (last && last.classList.contains("meta") && last.textContent === "Thinking…") last.remove();
      appendMessage("meta", `Error: ${err.message}`);
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  console.log("fm-chat UI initialized", { user_id: JWT_USER_ID, company: JWT_COMPANY, site_id: JWT_SITE_ID });
});
