// Local test config
// AGENT_CHAT_URL: the /agent/chat endpoint on the MCP server
// For local dev:  http://localhost:8000/agent/chat
// For production: https://mcp.smartentry.noke.dev/agent/chat
const AGENT_CHAT_URL = "http://localhost:8000/agent/chat";

// Hardcoded NOKE JWT for testing — replace with a fresh portal token if expired.
// Auth is enabled on the server so JWT is validated. User ID: 1034747, Site ID: 2223362
// In production the portal provides this dynamically.
const HARDCODED_NOKE_JWT = "eyJhbGciOiJOT0tFIiwidHlwIjoiSldUIn0.eyJhbGciOiJOT0tFIiwiY29tcGFueSI6IjEwMDAyMzMiLCJjdXJyZW50U2l0ZSI6MjIyMzM2MiwiZGV2aWNlSWQiOiIiLCJleHAiOjE3ODA1MjQ5MjgsImlzcyI6Im5va2UuY29tIiwibm9rZVVzZXIiOjEwMzQ3NDcsInNlc3Npb25TYWx0IjoiICIsInRva2VuVHlwZSI6IndlYiJ9.NTI3OWZmOGQ4NDk5YzdjYzE3NmM5NGMyNGNmZDdmYTQwZGNmNWVjZTZkYmUwMjIyZGEzMzg0MDJjYTkxZTE2MQ";

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
  return data.answer || "(No answer returned)";
}

launcher.addEventListener("click", () => {
  panel.classList.remove("hidden");
  if (!log.children.length) {
    appendMeta("Connected to MCP test endpoint");
    appendMessage("ai", "Welcome. Ask about units, locks, or other Smart Entry data.");
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
    const reply = await sendMessage(message);

    // Remove trailing 'Thinking...' meta if still present at end.
    const last = log.lastElementChild;
    if (last && last.classList.contains("meta") && last.textContent === "Thinking...") {
      last.remove();
    }

    appendMessage("ai", reply);
  } catch (err) {
    const last = log.lastElementChild;
    if (last && last.classList.contains("meta") && last.textContent === "Thinking...") {
      last.remove();
    }
    appendMessage("meta", `Error: ${err.message}`);
  }
});
