const sessionId = localStorage.getItem("session_id") || crypto.randomUUID();
localStorage.setItem("session_id", sessionId);

const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const modelSelect = document.getElementById("model-select");
const statusDot = document.getElementById("status-dot");
const banner = document.getElementById("banner");
const clearBtn = document.getElementById("clear-btn");

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function showBanner(msg) {
  banner.textContent = msg;
  banner.classList.remove("hidden");
}
function hideBanner() {
  banner.classList.add("hidden");
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.ollama_running) {
      statusDot.className = "dot online";
      hideBanner();
      modelSelect.innerHTML = "";
      (data.models.length ? data.models : ["(no models pulled yet)"]).forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
      });
    } else {
      statusDot.className = "dot offline";
      showBanner("Ollama isn't running. Start it with `ollama serve` and refresh this page.");
    }
  } catch (e) {
    statusDot.className = "dot offline";
    showBanner("Can't reach the local server. Is app.py still running?");
  }
}

async function loadHistory() {
  const res = await fetch(`/api/history/${sessionId}`);
  const history = await res.json();
  history.forEach((m) => addMessage(m.role, m.content));
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  addMessage("user", text);
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;

  const assistantDiv = addMessage("assistant", "");
  assistantDiv.classList.add("typing");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message: text,
        model: modelSelect.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      assistantDiv.textContent = `⚠️ ${err.error || "Something went wrong."}`;
      assistantDiv.classList.remove("typing");
      sendBtn.disabled = false;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop();

      for (const part of parts) {
        const line = part.replace(/^data:\s*/, "");
        if (line === "[DONE]") continue;
        try {
          const payload = JSON.parse(line);
          if (payload.token) {
            assistantDiv.textContent += payload.token;
            chat.scrollTop = chat.scrollHeight;
          }
          if (payload.error) {
            assistantDiv.textContent += `\n⚠️ ${payload.error}`;
          }
        } catch (_) { /* ignore partial chunk */ }
      }
    }
  } catch (err) {
    assistantDiv.textContent = "⚠️ Lost connection to the local server.";
  } finally {
    assistantDiv.classList.remove("typing");
    sendBtn.disabled = false;
    input.focus();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

clearBtn.addEventListener("click", async () => {
  await fetch(`/api/clear/${sessionId}`, { method: "POST" });
  chat.innerHTML = "";
});

loadStatus();
loadHistory();
setInterval(loadStatus, 15000);
