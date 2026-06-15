// Chat endpoint config
// LOCAL  (EKS server):          http://localhost:8000/agent/chat https://mcp.smartentry.noke.dev/agent/chat
// DEPLOYED (Lambda + API GW):   https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat
const AGENT_CHAT_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000/agent/chat"
    : "https://5u39ntjwyj.execute-api.us-east-2.amazonaws.com/chat";
console.log("fm-chat ui build 20260604-1 loaded");

function stripThinking(text) {
  if (!text) return text;
  return String(text).replace(/<thinking>[\s\S]*?<\/thinking>/gi, "").trim();
}

// Hardcoded NOKE JWT for testing — replace with a fresh portal token if expired.
// Auth is enabled on the server so JWT is validated. User ID: 1034747, Site ID: 2223362
// In production the portal provides this dynamically.
const HARDCODED_NOKE_JWT = "eyJhbGciOiJOT0tFIiwidHlwIjoiSldUIn0.eyJhbGciOiJOT0tFIiwiY29tcGFueSI6IjEwMDAyMzMiLCJjdXJyZW50U2l0ZSI6MjIyMzM2MiwiZGV2aWNlSWQiOiIiLCJleHAiOjE3ODA2MDk0NjEsImlzcyI6Im5va2UuY29tIiwibm9rZVVzZXIiOjEwMzQ3NDcsInNlc3Npb25TYWx0IjoiICIsInRva2VuVHlwZSI6IndlYiJ9.MTUxOTI3NGNiNzYxYjMzZDhlYjM3Y2EzYWU4ZWZkN2I3NTViY2NjMDk0ZjM4OWViZmZmYWUwZDBlYjVhMGMxOA";

const launcher = document.getElementById("chat-launcher");
const panel = document.getElementById("chat-panel");
const closeBtn = document.getElementById("chat-close");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const log = document.getElementById("chat-log");

let conversationId = null;

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

async function sendMessage(message) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${HARDCODED_NOKE_JWT}`,
  };

  const payload = { message };
  if (conversationId) payload.conversation_id = conversationId;

  const res = await fetch(AGENT_CHAT_URL, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body}`);
  }

  const data = await res.json();
  conversationId = data.conversation_id || conversationId;
  return data;
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

launcher.addEventListener("click", () => {
  panel.classList.remove("hidden");
  if (!log.children.length) {
    appendMeta("Connected to MCP test endpoint");
    appendMessage("ai", "Welcome. Ask about units, locks, or other Smart Entry data.");
    // const claims = decodeJwtPayload(HARDCODED_NOKE_JWT);
    // if (claims) {
    //   appendMeta(
    //     `Token claims -> user: ${claims.nokeUser ?? "?"}, site: ${claims.currentSite ?? "?"}, company: ${claims.company ?? "?"}`
    //   );
    // }
  }
  input.focus();
});

closeBtn.addEventListener("click", () => {
  panel.classList.add("hidden");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  if (!HARDCODED_NOKE_JWT || HARDCODED_NOKE_JWT === "REPLACE_WITH_REAL_NOKE_JWT") {
    appendMessage("meta", "Set HARDCODED_NOKE_JWT in ui/app.js before testing.");
    return;
  }

  appendMessage("user", message);
  input.value = "";

  try {
    appendMeta("Thinking...");
    const result = await sendMessage(message);
    const reply = stripThinking(result.answer || "(No answer returned)");

    // Remove trailing 'Thinking...' meta if still present at end.
    const last = log.lastElementChild;
    if (last && last.classList.contains("meta") && last.textContent === "Thinking...") {
      last.remove();
    }

    appendMessage("ai", reply);
    //appendMeta(`Server context -> user_id: ${result.user_id ?? "?"}, site_id: ${result.site_id ?? "?"}`);
  } catch (err) {
    const last = log.lastElementChild;
    if (last && last.classList.contains("meta") && last.textContent === "Thinking...") {
      last.remove();
    }
    appendMessage("meta", `Error: ${err.message}`);
  }
});

// Submit on Enter; use Shift+Enter for a newline in the textarea.
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});
