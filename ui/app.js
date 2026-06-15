// Chat endpoint config
const AGENT_CHAT_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000/agent/chat"
    : "https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat";

// Hardcoded NOKE JWT for testing — replace with a fresh portal token if expired.
const HARDCODED_NOKE_JWT = "eyJhbGciOiJOT0tFIiwidHlwIjoiSldUIn0.eyJhbGciOiJOT0tFIiwiY29tcGFueSI6IjEwMDAyMzMiLCJjdXJyZW50U2l0ZSI6MjIyMzM2MiwiZGV2aWNlSWQiOiIiLCJleHAiOjE3ODA2MDk0NjEsImlzcyI6Im5va2UuY29tIiwibm9rZVVzZXIiOjEwMzQ3NDcsInNlc3Npb25TYWx0IjoiICIsInRva2VuVHlwZSI6IndlYiJ9.MTUxOTI3NGNiNzYxYjMzZDhlYjM3Y2EzYWU4ZWZkN2I3NTViY2NjMDk0ZjM4OWViZmZmYWUwZDBlYjVhMGMxOA";

document.addEventListener("DOMContentLoaded", () => {
  const launcher = document.getElementById("chat-launcher");
  const panel = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const log = document.getElementById("chat-log");
  const siteSelect = document.getElementById("site-select");

  let conversationId = null;
  let selectedSiteId = null;

function stripThinking(text) {
  if (!text) return text;
  return String(text).replace(/<thinking>[\s\S]*?<\/thinking>/gi, "").trim();
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

function decodeJwtPayload(token) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

// Mock sites for initial testing — replace with real MCP /api/sites call later
const MOCK_SITES = [
  { id: 1, name: "Main Facility" },
  { id: 2, name: "Satellite Location" },
  { id: 2223362, name: "Test Site" },
];

function initializeSiteSelector() {
  if (!siteSelect) return;
  const claims = decodeJwtPayload(HARDCODED_NOKE_JWT);
  const companyUuid = claims ? claims.company : null;
  // TODO: fetch real sites: GET /api/sites?company_uuid=... when MCP is deployed
  siteSelect.innerHTML = '<option value="">-- Select a site --</option>';
  MOCK_SITES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name;
    siteSelect.appendChild(opt);
  });

  const saved = localStorage.getItem("noke_selected_site_id");
  if (saved && MOCK_SITES.some((s) => s.id === parseInt(saved))) {
    siteSelect.value = saved;
    selectedSiteId = parseInt(saved);
  }
}

if (siteSelect) {
  siteSelect.addEventListener("change", (e) => {
    selectedSiteId = e.target.value ? parseInt(e.target.value) : null;
    if (selectedSiteId) localStorage.setItem("noke_selected_site_id", selectedSiteId);
  });
}

async function sendMessage(message) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${HARDCODED_NOKE_JWT}`,
  };

  const payload = { message };
  if (conversationId) payload.conversation_id = conversationId;
  if (selectedSiteId) payload.site_id = selectedSiteId;

  const res = await fetch(AGENT_CHAT_URL, { method: "POST", headers, body: JSON.stringify(payload) });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  const data = await res.json();
  conversationId = data.conversation_id || conversationId;
  return data;
}

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
  if (!HARDCODED_NOKE_JWT || HARDCODED_NOKE_JWT === "REPLACE_WITH_REAL_NOKE_JWT") {
    appendMessage("meta", "Set HARDCODED_NOKE_JWT in ui/app.js before testing.");
    return;
  }
  if (!selectedSiteId) {
    appendMessage("meta", "Please select a site from the dropdown above before sending a message.");
    return;
  }

  appendMessage("user", message);
  input.value = "";
  try {
    appendMeta("Thinking...");
    const result = await sendMessage(message);
    const reply = stripThinking(result.answer || result.result || "(No answer returned)");
    const last = log.lastElementChild;
    if (last && last.classList.contains("meta") && last.textContent === "Thinking...") last.remove();
    appendMessage("ai", reply);
  } catch (err) {
    const last = log.lastElementChild;
    if (last && last.classList.contains("meta") && last.textContent === "Thinking...") last.remove();
    appendMessage("meta", `Error: ${err.message}`);
  }
});

// Submit on Enter; use Shift+Enter for a newline
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

  console.log("fm-chat UI initialized");
});
