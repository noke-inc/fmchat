// app.js — Noke Smart Entry AI chat UI
// Connects to the local FastAPI server (main.py) at the same origin.

const AGENT_CHAT_URL = `${window.location.origin}/agent/chat`;
const SITES_URL      = `${window.location.origin}/api/sites`;

// ─── State ────────────────────────────────────────────────────────────────────
let conversationId   = null;
let selectedSiteId   = null;
let selectedSiteName = null;

// ─── DOM refs ─────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const launcher       = document.getElementById("chat-launcher");
  const panel          = document.getElementById("chat-panel");
  const closeBtn       = document.getElementById("chat-close");
  const form           = document.getElementById("chat-form");
  const input          = document.getElementById("chat-input");
  const log            = document.getElementById("chat-log");
  const siteHeader     = document.getElementById("site-header");
  const siteHeaderName = document.getElementById("site-header-name");
  const sitePicker     = document.getElementById("site-picker");
  const siteButtons    = document.getElementById("site-buttons");
  const clearBtn       = document.getElementById("clear-session-btn");
  const sendBtn        = document.getElementById("send-btn");
  const subtitle       = document.getElementById("header-subtitle");

  // ─── Site picker ─────────────────────────────────────────────────────────
  async function loadSites() {
    siteButtons.innerHTML = '<span class="site-loading">Loading sites…</span>';
    try {
      const res   = await fetch(SITES_URL);
      const data  = await res.json();
      const sites = data.sites || [];

      siteButtons.innerHTML = "";
      if (!sites.length) {
        siteButtons.innerHTML = '<span class="site-loading">No sites available.</span>';
        return;
      }
      sites.forEach(site => {
        const btn = document.createElement("button");
        btn.type        = "button";
        btn.className   = "site-btn";
        btn.textContent = site.name;
        btn.addEventListener("click", () => selectSite(site.id, site.name));
        siteButtons.appendChild(btn);
      });
    } catch (err) {
      siteButtons.innerHTML = `<span class="site-loading">Could not load sites: ${err.message}</span>`;
    }
  }

  function selectSite(id, name) {
    selectedSiteId   = id;
    selectedSiteName = name;

    // Show site name bar + clear button
    siteHeaderName.textContent = `📍 ${name}`;
    siteHeader.classList.remove("hidden");

    // Hide site picker
    sitePicker.style.display = "none";

    // Update subtitle
    subtitle.textContent = name;

    // Enable chat input
    input.disabled  = false;
    sendBtn.disabled = false;
    input.focus();

    // Welcome message
    appendMessage("ai", `👋 Welcome! I'm your Smart Entry AI assistant for ${name}.\n\nI can help you:\n• Look up unit statuses and details\n• Check active rentals and tenant info\n• Assign users to available units\n\nHow can I help you today?`);
  }

  // ─── Session reset ────────────────────────────────────────────────────────
  async function resetSession() {
    if (conversationId) {
      try { await fetch(`${window.location.origin}/api/session/${conversationId}`, { method: "DELETE" }); }
      catch (_) {}
    }
    conversationId   = null;
    selectedSiteId   = null;
    selectedSiteName = null;

    log.innerHTML = "";
    siteHeader.classList.add("hidden");
    subtitle.textContent = "Select a site to begin";
    sitePicker.style.display = "";
    input.disabled   = true;
    sendBtn.disabled = true;
    input.value      = "";

    await loadSites();
  }

  clearBtn.addEventListener("click", resetSession);

  // ─── Render helpers ───────────────────────────────────────────────────────

  /** Convert **bold** and [text](url) markdown to HTML */
  function renderMarkdown(text) {
    return text
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  /** Parse a unit-options block from the agent message.
   *  Returns { cleanText, options: [{id, name}] }
   *  Options come from lines like: -> Select Target ID Identifier: '3185445' (5104)
   */
  function parseAgentMessage(raw) {
    const unitOptions = [];
    const actionOptions = [];

    // Extract unit option lines
    const optRe = /->.*?'(\d+)'\s*\(([^)]+)\)/g;
    let m;
    while ((m = optRe.exec(raw)) !== null) {
      unitOptions.push({ id: m[1], name: m[2].trim() });
    }

    // Extract confirmation action lines
    const actionRe = /->\s*Action:\s*'([^']+)'\s*\(([^)]+)\)/g;
    while ((m = actionRe.exec(raw)) !== null) {
      actionOptions.push({ value: m[1].trim(), label: m[2].trim() });
    }

    let clean = raw
      // Strip MISSING REQUIRED PARAMETERS header line
      .replace(/⚠️\s*MISSING REQUIRED PARAMETERS FOR TRANSACTION TRACK\s*'[^']*':\s*\n?/gi, "")
      // Strip "Remaining fields needed: [...]" line
      .replace(/Remaining fields needed:\s*\[[^\]]*\]\s*\n?/g, "")
      // Strip "Available Selection Resource Records Choices:" header
      .replace(/Available Selection Resource Records Choices:\s*\n?/g, "")
      // Strip "Confirmation Actions:" header
      .replace(/Confirmation Actions:\s*\n?/gi, "")
      // Strip all unit option lines
      .replace(/\s*->.*?'\d+'.*\n?/g, "")
      // Strip all action option lines
      .replace(/\s*->\s*Action:\s*'[^']+'\s*\([^)]+\)\s*\n?/g, "")
      // Strip leading/trailing blank lines
      .replace(/^\n+/, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    return { clean, unitOptions, actionOptions };
  }

  function appendMessage(role, rawText) {
    const { clean, unitOptions, actionOptions } = role === "ai"
      ? parseAgentMessage(rawText || "")
      : { clean: rawText, unitOptions: [], actionOptions: [] };

    if (clean) {
      const div = document.createElement("div");
      div.className = `msg ${role}`;
      div.innerHTML = renderMarkdown(
        clean.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
             .replace(/\n/g, "<br>")
      );
      log.appendChild(div);
    }

    // Render unit buttons (names only — IDs never shown)
    if (unitOptions.length > 0) {
      const wrap = document.createElement("div");
      wrap.className = "unit-options";
      const label = document.createElement("p");
      label.className = "unit-options-label";
      label.textContent = "Select an available unit:";
      wrap.appendChild(label);

      unitOptions.forEach(opt => {
        const btn = document.createElement("button");
        btn.type      = "button";
        btn.className = "unit-btn";
        btn.textContent = opt.name;
        btn.addEventListener("click", () => {
          // Show unit name in chat, send the internal ID to the agent
          appendUserMessage(opt.name);
          submitToAgent(opt.id);
          wrap.remove();
        });
        wrap.appendChild(btn);
      });
      log.appendChild(wrap);
    }

      // Render transaction confirmation action buttons.
      if (actionOptions.length > 0) {
        const wrap = document.createElement("div");
        wrap.className = "mutation-actions";

        const label = document.createElement("p");
        label.className = "mutation-actions-label";
        label.textContent = "Choose an action:";
        wrap.appendChild(label);

        actionOptions.forEach(opt => {
          const actionValue = String(opt.value || "").toUpperCase();
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = `action-btn ${actionValue === "CANCEL" ? "cancel" : "proceed"}`;
          btn.textContent = opt.label;
          btn.addEventListener("click", () => {
            appendUserMessage(opt.label);
            submitToAgent(actionValue || opt.label);
            wrap.remove();
          });
          wrap.appendChild(btn);
        });

        log.appendChild(wrap);
      }

    log.scrollTop = log.scrollHeight;
  }

  function appendMeta(text) {
    const div = document.createElement("div");
    div.className   = "msg meta";
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className   = "msg user";
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  // ─── Send message ─────────────────────────────────────────────────────────
  async function submitToAgent(messageToSend) {
    const thinking = appendMeta("Thinking…");
    try {
      const res = await fetch(AGENT_CHAT_URL, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          message:         messageToSend,
          site_id:         selectedSiteId,
          conversation_id: conversationId,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      conversationId = data.conversation_id || conversationId;
      thinking.remove();
      if (data.answer && data.answer.trim()) {
        appendMessage("ai", data.answer);
      }
    } catch (err) {
      thinking.remove();
      appendMeta(`Error: ${err.message}`);
    }
  }

  // ─── Form submit ──────────────────────────────────────────────────────────
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || !selectedSiteId) return;
    input.value = "";
    appendUserMessage(message);
    await submitToAgent(message);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });

  // ─── Panel open / close ───────────────────────────────────────────────────
  launcher.addEventListener("click", async () => {
    panel.classList.remove("hidden");
    if (!selectedSiteId && !log.children.length) {
      await loadSites();
    }
  });

  closeBtn.addEventListener("click", () => panel.classList.add("hidden"));
});

// Local MCP server (used to fetch real site list)
const LOCAL_MCP_URL = "http://localhost:8000/mcp-http/";

// Hardcoded NOKE JWT for testing — replace with a fresh portal token if expired.
const HARDCODED_NOKE_JWT = "eyJhbGciOiJOT0tFIiwidHlwIjoiSldUIn0.eyJhbGciOiJOT0tFIiwiY29tcGFueSI6IjIiLCJjdXJyZW50U2l0ZSI6MTUsImRldmljZUlkIjoiIiwiZXhwIjoxNzg0NTYzOTYwLCJpc3MiOiJub2tlLmNvbSIsIm5va2VVc2VyIjoxMDM0NzQ3LCJzZXNzaW9uU2FsdCI6IiAiLCJ0b2tlblR5cGUiOiJ3ZWIifQ.MTA0MDI1NjQ2Zjk5NjlhYjdmYzIxY2U4NDJhYWY1NGRiODM0MzdjMWM4NzQwM2VlMDhmMDgxNjcwMjhkZWJmNg";

document.addEventListener("DOMContentLoaded", () => {
  const launcher   = document.getElementById("chat-launcher");
  const panel      = document.getElementById("chat-panel");
  const closeBtn   = document.getElementById("chat-close");
  const form       = document.getElementById("chat-form");
  const input      = document.getElementById("chat-input");
  const log        = document.getElementById("chat-log");
  const siteSelect = document.getElementById("site-select");

  // Guard: this legacy flow expects a site <select>; skip it for current button-based UI.
  if (!siteSelect) {
    return;
  }

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
