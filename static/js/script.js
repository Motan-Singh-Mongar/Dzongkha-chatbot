"use strict";

const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const errorBox = document.getElementById("errorBox");
const banner = document.getElementById("statusBanner");

let history = [];   // English-only history sent to the backend: [{role, content}]
let busy = false;

const SOURCE_LABELS = {
  library: "Predefined reply",
  knowledge_base: "Knowledge base",
  ai: "AI answer",
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;   // textContent => no HTML injection
  return node;
}

function scrollToBottom() { chatEl.scrollTop = chatEl.scrollHeight; }

function showError(msg) { errorBox.textContent = msg; errorBox.hidden = !msg; }

function addUserMessage(text) {
  const wrap = el("div", "msg user");
  wrap.appendChild(el("div", "bubble", text));
  chatEl.appendChild(wrap); scrollToBottom();
}

function addWelcome() {
  const wrap = el("div", "msg bot");
  const bubble = el("div", "bubble");
  bubble.appendChild(el("p", "dz", "ཀུ་ཟུ་ཟང་པོ་ལགས།"));
  bubble.lastChild.lang = "dz";
  bubble.appendChild(el("p", "", "Welcome! Ask me a question in English and I will answer in Dzongkha."));
  wrap.appendChild(bubble); chatEl.appendChild(wrap);
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = el("textarea"); ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand("copy"); ta.remove();
  }
  const old = btn.textContent; btn.textContent = "Copied!";
  setTimeout(() => (btn.textContent = old), 1200);
}

function addBotMessage(data) {
  const wrap = el("div", "msg bot");
  const bubble = el("div", "bubble");
  const dz = el("p", "dz", data.dzongkha); dz.lang = "dz";
  bubble.appendChild(dz);
  wrap.appendChild(bubble);

  const meta = el("div", "meta");
  let label = SOURCE_LABELS[data.source] || "Reply";
  if (data.machine_translated) label += " · machine-translated";
  label += data.reviewed ? " · reviewed" : " · unreviewed";
  meta.appendChild(el("span", "badge", label));

  const copyBtn = el("button", "link-btn", "Copy"); copyBtn.type = "button";
  copyBtn.addEventListener("click", () => copyText(data.dzongkha, copyBtn));
  meta.appendChild(copyBtn);

  const engBtn = el("button", "link-btn", "Show English"); engBtn.type = "button";
  const eng = el("div", "english", data.english); eng.hidden = true;
  engBtn.addEventListener("click", () => {
    eng.hidden = !eng.hidden; engBtn.textContent = eng.hidden ? "Show English" : "Hide English";
  });
  meta.appendChild(engBtn);

  wrap.appendChild(meta); wrap.appendChild(eng);
  chatEl.appendChild(wrap); scrollToBottom();
}

function addTyping() {
  const wrap = el("div", "msg bot"); wrap.id = "typing";
  const bubble = el("div", "bubble typing");
  bubble.setAttribute("aria-label", "Chatbot is typing");
  bubble.append(el("span"), el("span"), el("span"));
  wrap.appendChild(bubble); chatEl.appendChild(wrap); scrollToBottom();
}
function removeTyping() { const t = document.getElementById("typing"); if (t) t.remove(); }

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value; inputEl.disabled = value;
  document.querySelectorAll(".chip").forEach((c) => (c.disabled = value));
  sendBtn.textContent = value ? "Thinking..." : "Send";
  if (!value) inputEl.focus();
}

async function sendMessage(text) {
  text = (text || "").trim();
  if (busy) return;
  if (!text) { showError("Please type a message first."); return; }
  showError("");
  addUserMessage(text);
  inputEl.value = ""; autoGrow();
  setBusy(true); addTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Server error (${res.status})`);
    removeTyping(); addBotMessage(data);
    history.push({ role: "user", content: text }, { role: "assistant", content: data.english });
    history = history.slice(-12);   // frontend keeps only the most recent turns
  } catch (err) {
    removeTyping();
    showError(err instanceof TypeError
      ? "Cannot reach the local server. Is `python app.py` still running?"
      : err.message);
  } finally {
    setBusy(false);
  }
}

function autoGrow() { inputEl.style.height = "auto"; inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px"; }

sendBtn.addEventListener("click", () => sendMessage(inputEl.value));
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(inputEl.value); }
});
inputEl.addEventListener("input", autoGrow);
document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => sendMessage(c.textContent)));
clearBtn.addEventListener("click", () => {
  history = []; chatEl.textContent = ""; showError(""); addWelcome(); inputEl.focus();
});

// Poll model status so the user knows when the AI models are ready.
async function pollHealth() {
  try {
    const s = await (await fetch("/api/health")).json();
    const states = [s.llm, s.translator];
    if (states.includes("error")) {
      const details = Object.values(s.errors || {}).join(" | ");
      banner.textContent = "Model problem: " + details; banner.hidden = false; return;
    }
    if (states.every((x) => x === "ready")) { banner.hidden = true; return; }
    banner.textContent = `Loading AI models... (chat model: ${s.llm}, translator: ${s.translator}). ` +
      "Greetings work already; other questions need the models.";
    banner.hidden = false;
    setTimeout(pollHealth, 3000);
  } catch { setTimeout(pollHealth, 5000); }
}

addWelcome();
pollHealth();
